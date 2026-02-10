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
        # For containerd/k8s clusters, use docker and import to containerd
        if command -v docker &> /dev/null; then
            print_status "Building image with docker..."
            sudo docker build -t ${IMAGE_NAME}:${IMAGE_TAG} .
            
            print_status "Importing image into containerd k8s.io namespace..."
            sudo docker save ${IMAGE_NAME}:${IMAGE_TAG} | sudo ctr -n k8s.io image import -
            print_status "Image imported to containerd"
        else
            print_error "Docker is not installed"
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
    
    # 5. Create Releases PVC
    print_status "Creating Releases storage..."
    kubectl apply -f k8s/releases-pvc.yaml || print_warning "Releases PVC creation failed"
    
    # 6. Wait for databases to be ready
    print_status "Waiting for databases to be ready..."
    kubectl wait --for=condition=ready pod -l app=postgres -n ${NAMESPACE} --timeout=120s || true
    kubectl wait --for=condition=ready pod -l app=redis -n ${NAMESPACE} --timeout=60s || true
    
    # 7. Deploy Server
    print_status "Deploying Agent Server..."
    kubectl apply -f k8s/deployment.yaml
    
    # 8. Create Service
    print_status "Creating Service..."
    kubectl apply -f k8s/service.yaml
    
    # 9. Create Ingress (optional)
    print_status "Creating Ingress..."
    kubectl apply -f k8s/ingress.yaml || print_warning "Ingress creation failed (ingress controller may not be installed)"
    
    print_status "Deployment completed!"
    echo ""
    print_status "To check status: $0 status"
    print_status "To access the service: $0 port-forward"
    print_status "To build and upload agent releases: $0 releases v0.1.0"
}

# Delete deployment
delete_deployment() {
    print_status "Deleting deployment..."
    check_kubectl
    
    kubectl delete -f k8s/ingress.yaml --ignore-not-found
    kubectl delete -f k8s/service.yaml --ignore-not-found
    kubectl delete -f k8s/deployment.yaml --ignore-not-found
    kubectl delete -f k8s/releases-pvc.yaml --ignore-not-found
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

# Build and upload agent releases
build_releases() {
    VERSION="${2:-v0.1.0}"
    print_status "Building agent releases ${VERSION}..."
    
    # Check if Go is installed
    if ! command -v go &> /dev/null; then
        print_error "Go is not installed"
        exit 1
    fi
    
    # Run the build-release script
    if [ -f "./build-release.sh" ]; then
        chmod +x ./build-release.sh
        ./build-release.sh "${VERSION}"
    else
        print_error "build-release.sh not found"
        exit 1
    fi
    
    print_status "Releases built successfully"
}

# Upload releases to Kubernetes pod
upload_releases() {
    VERSION="${2:-v0.1.0}"
    print_status "Uploading releases to Kubernetes..."
    check_kubectl
    
    # Get the pod name
    POD_NAME=$(kubectl get pods -n ${NAMESPACE} -l app=agent-server -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
    
    if [ -z "$POD_NAME" ]; then
        print_error "No agent-server pod found. Deploy first."
        exit 1
    fi
    
    RELEASES_DIR="./releases/${VERSION}"
    if [ ! -d "$RELEASES_DIR" ]; then
        print_error "Releases directory not found: $RELEASES_DIR"
        print_error "Run: $0 build-releases ${VERSION}"
        exit 1
    fi
    
    # Copy releases to pod
    print_status "Copying releases to pod ${POD_NAME}..."
    
    # Create directory in pod
    kubectl exec -n ${NAMESPACE} ${POD_NAME} -- mkdir -p /app/releases/${VERSION}
    
    # Copy each file
    for file in ${RELEASES_DIR}/*.zip ${RELEASES_DIR}/checksums.txt; do
        if [ -f "$file" ]; then
            filename=$(basename "$file")
            print_status "Uploading ${filename}..."
            kubectl cp "$file" "${NAMESPACE}/${POD_NAME}:/app/releases/${VERSION}/${filename}"
        fi
    done
    
    # Create/update latest symlink
    kubectl exec -n ${NAMESPACE} ${POD_NAME} -- rm -f /app/releases/latest
    kubectl exec -n ${NAMESPACE} ${POD_NAME} -- ln -s /app/releases/${VERSION} /app/releases/latest
    
    print_status "Releases uploaded successfully"
    
    # List uploaded files
    kubectl exec -n ${NAMESPACE} ${POD_NAME} -- ls -la /app/releases/${VERSION}/
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
    build-releases)
        build_releases "$@"
        ;;
    upload-releases)
        upload_releases "$@"
        ;;
    releases)
        build_releases "$@"
        upload_releases "$@"
        ;;
    all)
        build_image
        deploy
        ;;
    *)
        echo "Usage: $0 {build|deploy|delete|status|logs|port-forward|restart|build-releases|upload-releases|releases|all}"
        echo ""
        echo "Commands:"
        echo "  build            - Build Docker image"
        echo "  deploy           - Deploy to Kubernetes"
        echo "  delete           - Delete deployment"
        echo "  status           - Show deployment status"
        echo "  logs             - Show agent-server logs"
        echo "  port-forward     - Forward port 8080 for local access"
        echo "  restart          - Restart agent-server deployment"
        echo "  build-releases   - Build agent releases (e.g., $0 build-releases v0.1.0)"
        echo "  upload-releases  - Upload releases to Kubernetes pod"
        echo "  releases         - Build and upload releases"
        echo "  all              - Build and deploy"
        exit 1
        ;;
esac
