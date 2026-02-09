#!/bin/bash
# Deploy Agent Monitor Server to Local Kubernetes
# Usage: ./deploy.sh [command]
# Commands: build, deploy, delete, status, logs, port-forward

set -e

NAMESPACE="agent-system"
IMAGE_NAME="agent-server"
IMAGE_TAG="latest"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}==>${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}Warning:${NC} $1"
}

print_error() {
    echo -e "${RED}Error:${NC} $1"
}

# Check if kubectl is available
check_kubectl() {
    if ! command -v kubectl &> /dev/null; then
        print_error "kubectl is not installed"
        exit 1
    fi
}

# Check if docker is available
check_docker() {
    if ! command -v docker &> /dev/null; then
        print_error "docker is not installed"
        exit 1
    fi
}

# Detect Kubernetes environment (minikube, kind, or other)
detect_k8s_env() {
    if command -v minikube &> /dev/null && minikube status &> /dev/null; then
        echo "minikube"
    elif command -v kind &> /dev/null && kind get clusters 2>/dev/null | grep -q .; then
        echo "kind"
    else
        echo "other"
    fi
}

# Build Docker image
build_image() {
    print_status "Building container image..."
    
    K8S_ENV=$(detect_k8s_env)
    
    if [ "$K8S_ENV" == "minikube" ]; then
        print_status "Using minikube's Docker daemon..."
        check_docker
        eval $(minikube docker-env)
        docker build -t ${IMAGE_NAME}:${IMAGE_TAG} .
    elif [ "$K8S_ENV" == "kind" ]; then
        print_status "Building image for kind..."
        check_docker
        docker build -t ${IMAGE_NAME}:${IMAGE_TAG} .
        
        # Get the kind cluster name
        CLUSTER_NAME=$(kind get clusters 2>/dev/null | head -1)
        if [ -n "$CLUSTER_NAME" ]; then
            print_status "Loading image into kind cluster: $CLUSTER_NAME"
            kind load docker-image ${IMAGE_NAME}:${IMAGE_TAG} --name $CLUSTER_NAME
        fi
    else
        # Check for nerdctl (for containerd/k8s clusters)
        if command -v nerdctl &> /dev/null; then
            print_status "Using nerdctl to build image for containerd..."
            # Build using nerdctl with k8s.io namespace (used by kubernetes)
            sudo nerdctl --namespace k8s.io build -t ${IMAGE_NAME}:${IMAGE_TAG} .
            print_status "Image built in k8s.io namespace"
        elif command -v docker &> /dev/null; then
            print_warning "Using docker, you may need to load the image into containerd"
            docker build -t ${IMAGE_NAME}:${IMAGE_TAG} .
            print_status "To load into containerd: docker save ${IMAGE_NAME}:${IMAGE_TAG} | sudo ctr -n k8s.io image import -"
        else
            print_error "No container build tool found (docker, nerdctl)"
            exit 1
        fi
    fi
    
    print_status "Container image built successfully"
}

# Deploy to Kubernetes
deploy() {
    print_status "Deploying to Kubernetes..."
    check_kubectl
    
    # 1. Create namespace
    print_status "Creating namespace..."
    kubectl apply -f k8s/namespace.yaml
    
    # 2. Create ConfigMap and Secret
    print_status "Creating ConfigMap and Secret..."
    kubectl apply -f k8s/configmap.yaml
    kubectl apply -f k8s/secret.yaml
    
    # 3. Deploy PostgreSQL
    print_status "Deploying PostgreSQL..."
    kubectl apply -f k8s/postgres.yaml
    
    # 4. Deploy Redis
    print_status "Deploying Redis..."
    kubectl apply -f k8s/redis.yaml
    
    # 5. Wait for databases to be ready
    print_status "Waiting for databases to be ready..."
    kubectl wait --for=condition=ready pod -l app=postgres -n ${NAMESPACE} --timeout=120s || true
    kubectl wait --for=condition=ready pod -l app=redis -n ${NAMESPACE} --timeout=60s || true
    
    # 6. Deploy Server
    print_status "Deploying Agent Server..."
    kubectl apply -f k8s/deployment.yaml
    
    # 7. Create Service
    print_status "Creating Service..."
    kubectl apply -f k8s/service.yaml
    
    # 8. Create Ingress (optional)
    print_status "Creating Ingress..."
    kubectl apply -f k8s/ingress.yaml || print_warning "Ingress creation failed (ingress controller may not be installed)"
    
    print_status "Deployment completed!"
    echo ""
    print_status "To check status: $0 status"
    print_status "To access the service: $0 port-forward"
}

# Delete deployment
delete_deployment() {
    print_status "Deleting deployment..."
    check_kubectl
    
    kubectl delete -f k8s/ingress.yaml --ignore-not-found
    kubectl delete -f k8s/service.yaml --ignore-not-found
    kubectl delete -f k8s/deployment.yaml --ignore-not-found
    kubectl delete -f k8s/redis.yaml --ignore-not-found
    kubectl delete -f k8s/postgres.yaml --ignore-not-found
    kubectl delete -f k8s/secret.yaml --ignore-not-found
    kubectl delete -f k8s/configmap.yaml --ignore-not-found
    kubectl delete namespace ${NAMESPACE} --ignore-not-found
    
    print_status "Deployment deleted"
}

# Show status
show_status() {
    print_status "Deployment Status:"
    check_kubectl
    
    echo ""
    echo "=== Namespace ==="
    kubectl get namespace ${NAMESPACE} 2>/dev/null || echo "Namespace not found"
    
    echo ""
    echo "=== Pods ==="
    kubectl get pods -n ${NAMESPACE} -o wide 2>/dev/null || echo "No pods found"
    
    echo ""
    echo "=== Services ==="
    kubectl get svc -n ${NAMESPACE} 2>/dev/null || echo "No services found"
    
    echo ""
    echo "=== Ingress ==="
    kubectl get ingress -n ${NAMESPACE} 2>/dev/null || echo "No ingress found"
    
    echo ""
    echo "=== Deployments ==="
    kubectl get deployments -n ${NAMESPACE} 2>/dev/null || echo "No deployments found"
}

# Show logs
show_logs() {
    print_status "Showing agent-server logs..."
    check_kubectl
    
    POD=$(kubectl get pods -n ${NAMESPACE} -l app=agent-server -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
    
    if [ -z "$POD" ]; then
        print_error "No agent-server pod found"
        exit 1
    fi
    
    kubectl logs -f $POD -n ${NAMESPACE}
}

# Port forward for local access
port_forward() {
    print_status "Setting up port forwarding..."
    print_status "Access the service at http://localhost:8080"
    check_kubectl
    
    kubectl port-forward svc/agent-server-service 8080:80 -n ${NAMESPACE}
}

# Restart deployment
restart() {
    print_status "Restarting agent-server deployment..."
    check_kubectl
    
    kubectl rollout restart deployment/agent-server -n ${NAMESPACE}
    kubectl rollout status deployment/agent-server -n ${NAMESPACE}
    
    print_status "Restart completed"
}

# Main
case "$1" in
    build)
        build_image
        ;;
    deploy)
        deploy
        ;;
    delete)
        delete_deployment
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs
        ;;
    port-forward|pf)
        port_forward
        ;;
    restart)
        restart
        ;;
    all)
        build_image
        deploy
        ;;
    *)
        echo "Usage: $0 {build|deploy|delete|status|logs|port-forward|restart|all}"
        echo ""
        echo "Commands:"
        echo "  build        - Build Docker image"
        echo "  deploy       - Deploy to Kubernetes"
        echo "  delete       - Delete deployment"
        echo "  status       - Show deployment status"
        echo "  logs         - Show agent-server logs"
        echo "  port-forward - Forward port 8080 for local access"
        echo "  restart      - Restart agent-server deployment"
        echo "  all          - Build and deploy"
        exit 1
        ;;
esac
