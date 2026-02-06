# Kubernetes 部署設計 (Kubernetes Deployment Design)

## 架構概覽

```
┌─────────────────────────────────────────────────┐
│              External Traffic                   │
│        (https://agent.myelintek.com)              │
└───────────────────┬─────────────────────────────┘
                    │
        ┌───────────▼──────────┐
        │   Ingress Controller │
        │   (nginx/traefik)    │
        │   - TLS Termination  │
        │   - Load Balancing   │
        └───────────┬──────────┘
                    │
        ┌───────────▼──────────┐
        │   Service (ClusterIP)│
        └───────────┬──────────┘
                    │
    ┌───────────────┼───────────────┐
    │               │               │
┌───▼───┐       ┌───▼───┐      ┌───▼───┐
│ Pod 1 │       │ Pod 2 │      │ Pod N │
│ Server│       │ Server│      │ Server│
└───┬───┘       └───┬───┘      └───┬───┘
    │               │               │
    └───────────────┼───────────────┘
                    │
        ┌───────────▼──────────┐
        │   Redis Service      │
        └───────────┬──────────┘
                    │
        ┌───────────▼──────────┐
        │   Database Service   │
        └──────────────────────┘
```

## Namespace

```yaml
# namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: agent-system
  labels:
    name: agent-system
```

## ConfigMap

```yaml
# configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: agent-server-config
  namespace: agent-system
data:
  SERVER_HOST: "0.0.0.0"
  SERVER_PORT: "8080"
  SERVER_URL: "https://agent.myelintek.com"
  
  # Redis
  REDIS_HOST: "redis-service"
  REDIS_PORT: "6379"
  REDIS_DB: "0"
  
  # WebSocket
  WS_HEARTBEAT_INTERVAL: "15"
  WS_OFFLINE_TIMEOUT: "60"
  
  # Binary Storage
  BINARY_STORAGE_PATH: "/storage/binaries"
  
  # Logging
  LOG_LEVEL: "info"
```

## Secret

```yaml
# secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: agent-server-secret
  namespace: agent-system
type: Opaque
stringData:
  # Database
  DATABASE_URL: "postgresql://user:password@postgres-service:5432/agentdb"
  
  # Security
  SECRET_KEY: "your-secret-key-change-in-production"
  JWT_ALGORITHM: "HS256"
  
  # Redis Password (if needed)
  REDIS_PASSWORD: ""
```

## PersistentVolumeClaim

```yaml
# pvc.yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: agent-binaries-pvc
  namespace: agent-system
spec:
  accessModes:
    - ReadWriteMany  # 多個 Pod 共享
  storageClassName: standard  # 根據環境調整
  resources:
    requests:
      storage: 50Gi  # 儲存 Agent Binary
```

## Deployment

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: agent-server
  namespace: agent-system
  labels:
    app: agent-server
spec:
  replicas: 2  # 至少 2 個副本以實現高可用性
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0  # 確保始終有 Pod 在運行
  selector:
    matchLabels:
      app: agent-server
  template:
    metadata:
      labels:
        app: agent-server
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "8080"
        prometheus.io/path: "/metrics"
    spec:
      containers:
      - name: server
        image: your-registry/agent-server:v1.0.0
        imagePullPolicy: Always
        ports:
        - name: http
          containerPort: 8080
          protocol: TCP
        
        # 環境變數
        env:
        - name: POD_ID
          valueFrom:
            fieldRef:
              fieldPath: metadata.name
        - name: POD_IP
          valueFrom:
            fieldRef:
              fieldPath: status.podIP
        
        # ConfigMap 環境變數
        envFrom:
        - configMapRef:
            name: agent-server-config
        - secretRef:
            name: agent-server-secret
        
        # 資源限制
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "2000m"
        
        # Volume 掛載
        volumeMounts:
        - name: binaries
          mountPath: /storage/binaries
        - name: logs
          mountPath: /var/log/agent
        
        # 健康檢查
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 3
        
        readinessProbe:
          httpGet:
            path: /readiness
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 5
          timeoutSeconds: 3
          failureThreshold: 2
        
        # 優雅關閉
        lifecycle:
          preStop:
            exec:
              command: ["/bin/sh", "-c", "sleep 10"]
      
      # Volumes
      volumes:
      - name: binaries
        persistentVolumeClaim:
          claimName: agent-binaries-pvc
      - name: logs
        emptyDir: {}
      
      # 優雅關閉時間
      terminationGracePeriodSeconds: 30
```

## Service

```yaml
# service.yaml
apiVersion: v1
kind: Service
metadata:
  name: agent-server-service
  namespace: agent-system
  labels:
    app: agent-server
spec:
  type: ClusterIP
  ports:
  - name: http
    port: 80
    targetPort: 8080
    protocol: TCP
  selector:
    app: agent-server
  sessionAffinity: None  # WebSocket 使用 Redis 管理 session，不需要 sticky
```

## Ingress

```yaml
# ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: agent-server-ingress
  namespace: agent-system
  annotations:
    # TLS
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
    
    # Nginx Ingress 設定
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/force-ssl-redirect: "true"
    
    # WebSocket 支援
    nginx.ingress.kubernetes.io/websocket-services: "agent-server-service"
    
    # Timeout 設定 (WebSocket 長連線)
    nginx.ingress.kubernetes.io/proxy-read-timeout: "3600"
    nginx.ingress.kubernetes.io/proxy-send-timeout: "3600"
    nginx.ingress.kubernetes.io/proxy-connect-timeout: "300"
    
    # Body Size (for large inventory data)
    nginx.ingress.kubernetes.io/proxy-body-size: "10m"
    
    # CORS (如需要)
    nginx.ingress.kubernetes.io/enable-cors: "true"
    nginx.ingress.kubernetes.io/cors-allow-origin: "https://agent.myelintek.com"
    
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - agent.myelintek.com
    secretName: agent-tls-cert
  rules:
  - host: agent.myelintek.com
    http:
      paths:
      # WebSocket Path
      - path: /ws
        pathType: Prefix
        backend:
          service:
            name: agent-server-service
            port:
              number: 80
      # API Path
      - path: /api
        pathType: Prefix
        backend:
          service:
            name: agent-server-service
            port:
              number: 80
      # Web UI
      - path: /
        pathType: Prefix
        backend:
          service:
            name: agent-server-service
            port:
              number: 80
```

## Redis Deployment

```yaml
# redis-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
  namespace: agent-system
spec:
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
      - name: redis
        image: redis:7-alpine
        ports:
        - containerPort: 6379
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
        volumeMounts:
        - name: redis-data
          mountPath: /data
        command:
        - redis-server
        - --appendonly
        - "yes"
        - --maxmemory
        - "512mb"
        - --maxmemory-policy
        - "allkeys-lru"
      volumes:
      - name: redis-data
        emptyDir: {}

---
apiVersion: v1
kind: Service
metadata:
  name: redis-service
  namespace: agent-system
spec:
  type: ClusterIP
  ports:
  - port: 6379
    targetPort: 6379
  selector:
    app: redis
```

## Database (PostgreSQL)

```yaml
# postgres-deployment.yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: postgres
  namespace: agent-system
spec:
  serviceName: postgres-service
  replicas: 1
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
      - name: postgres
        image: postgres:15-alpine
        ports:
        - containerPort: 5432
        env:
        - name: POSTGRES_DB
          value: "agentdb"
        - name: POSTGRES_USER
          value: "postgres"
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: postgres-secret
              key: password
        - name: PGDATA
          value: /var/lib/postgresql/data/pgdata
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
        volumeMounts:
        - name: postgres-data
          mountPath: /var/lib/postgresql/data
  volumeClaimTemplates:
  - metadata:
      name: postgres-data
    spec:
      accessModes: ["ReadWriteOnce"]
      storageClassName: standard
      resources:
        requests:
          storage: 100Gi

---
apiVersion: v1
kind: Service
metadata:
  name: postgres-service
  namespace: agent-system
spec:
  type: ClusterIP
  ports:
  - port: 5432
    targetPort: 5432
  selector:
    app: postgres

---
apiVersion: v1
kind: Secret
metadata:
  name: postgres-secret
  namespace: agent-system
type: Opaque
stringData:
  password: "change-me-in-production"
```

## HorizontalPodAutoscaler

```yaml
# hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: agent-server-hpa
  namespace: agent-system
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: agent-server
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 50
        periodSeconds: 60
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
      - type: Percent
        value: 100
        periodSeconds: 30
```

## NetworkPolicy

```yaml
# networkpolicy.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: agent-server-netpol
  namespace: agent-system
spec:
  podSelector:
    matchLabels:
      app: agent-server
  policyTypes:
  - Ingress
  - Egress
  ingress:
  # 允許從 Ingress 接收流量
  - from:
    - namespaceSelector:
        matchLabels:
          name: ingress-nginx
    ports:
    - protocol: TCP
      port: 8080
  egress:
  # 允許訪問 Redis
  - to:
    - podSelector:
        matchLabels:
          app: redis
    ports:
    - protocol: TCP
      port: 6379
  # 允許訪問 PostgreSQL
  - to:
    - podSelector:
        matchLabels:
          app: postgres
    ports:
    - protocol: TCP
      port: 5432
  # 允許 DNS 查詢
  - to:
    - namespaceSelector:
        matchLabels:
          name: kube-system
    ports:
    - protocol: UDP
      port: 53
  # 允許對外連線 (如需要)
  - to:
    - podSelector: {}
    ports:
    - protocol: TCP
      port: 443
```

## ServiceMonitor (Prometheus)

```yaml
# servicemonitor.yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: agent-server-monitor
  namespace: agent-system
  labels:
    app: agent-server
spec:
  selector:
    matchLabels:
      app: agent-server
  endpoints:
  - port: http
    path: /metrics
    interval: 30s
```

## 部署順序

```bash
# 1. 建立 Namespace
kubectl apply -f namespace.yaml

# 2. 建立 ConfigMap 和 Secret
kubectl apply -f configmap.yaml
kubectl apply -f secret.yaml

# 3. 部署 PostgreSQL
kubectl apply -f postgres-deployment.yaml

# 4. 部署 Redis
kubectl apply -f redis-deployment.yaml

# 5. 等待資料庫就緒
kubectl wait --for=condition=ready pod -l app=postgres -n agent-system --timeout=300s
kubectl wait --for=condition=ready pod -l app=redis -n agent-system --timeout=300s

# 6. 建立 PVC
kubectl apply -f pvc.yaml

# 7. 部署 Server
kubectl apply -f deployment.yaml

# 8. 建立 Service
kubectl apply -f service.yaml

# 9. 設定 Ingress
kubectl apply -f ingress.yaml

# 10. (選用) 設定 HPA
kubectl apply -f hpa.yaml

# 11. (選用) 設定 NetworkPolicy
kubectl apply -f networkpolicy.yaml
```

## 重要注意事項

### 1. WebSocket 設定
- **Proxy Timeout**: 必須設定足夠長的 timeout (建議 3600 秒以上)
- **Session Affinity**: 不需要設定，使用 Redis 管理 session
- **Connection Draining**: 確保 Pod 關閉前完成現有連線

### 2. TLS 設定
- 使用 Let's Encrypt 或其他 CA 簽發證書
- 確保 TLS 1.2+ 和強加密演算法
- 定期更新證書

### 3. 滾動更新策略
```yaml
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxSurge: 1         # 一次最多增加 1 個 Pod
    maxUnavailable: 0   # 確保始終有 Pod 在運行
```

### 4. 優雅關閉
```yaml
lifecycle:
  preStop:
    exec:
      command: ["/bin/sh", "-c", "sleep 10"]
terminationGracePeriodSeconds: 30
```

### 5. 資源限制
- 根據實際負載調整 CPU 和 Memory
- 設定合理的 requests 和 limits
- 監控資源使用情況

### 6. 監控與日誌
- 使用 Prometheus 監控
- 使用 ELK 或 Loki 收集日誌
- 設定告警規則

## 故障排查

### 查看 Pod 狀態
```bash
kubectl get pods -n agent-system
kubectl describe pod <pod-name> -n agent-system
```

### 查看 Pod 日誌
```bash
kubectl logs <pod-name> -n agent-system
kubectl logs <pod-name> -n agent-system --previous  # 查看前一個容器日誌
```

### 查看 Ingress
```bash
kubectl get ingress -n agent-system
kubectl describe ingress agent-server-ingress -n agent-system
```

### 測試連線
```bash
# 在 Pod 內測試
kubectl exec -it <pod-name> -n agent-system -- /bin/sh

# 測試 Redis 連線
redis-cli -h redis-service -p 6379 ping

# 測試 PostgreSQL 連線
psql -h postgres-service -U postgres -d agentdb
```

### WebSocket 測試
```bash
# 使用 wscat 測試 WebSocket
wscat -c "wss://agent.myelintek.com/ws/test-client-id?token=test-token"
```
