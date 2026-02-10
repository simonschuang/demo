# Server 端設計 (Server-Side Design)

## 技術架構

### 程式語言與框架
- **語言**: Python 3.9+
- **Web 框架**: FastAPI (推薦) 或 Flask
- **WebSocket**: FastAPI WebSocket 或 Socket.IO
- **ORM**: SQLAlchemy
- **Cache**: Redis (redis-py)
- **非同步**: asyncio

### 部署架構
- **容器化**: Docker
- **編排**: Kubernetes
- **副本數**: 2+ (高可用性)
- **對外服務**: Ingress (HTTPS/WSS)

## 核心模組

### 1. Web UI 模組
```
/web
├── static/          # 靜態檔案 (CSS, JS, images)
├── templates/       # HTML 模板
├── routes/
│   ├── auth.py     # 登入/登出
│   ├── dashboard.py # 儀表板
│   ├── clients.py  # Client 管理
│   ├── download.py # 安裝檔下載
│   └── terminal.py # 遠端終端機
```

**功能**:
- 使用者登入/登出
- Dashboard (顯示 online/offline clients)
- Client 列表與詳細資訊
- Inventory 資訊展示
- 歷史資料查詢
- 安裝檔下載頁面
- **遠端終端機存取** (Remote Terminal)

**使用者隔離**:
```python
@router.get("/clients")
async def get_clients(user: User = Depends(get_current_user)):
    return db.query(Client).filter(Client.user_id == user.id).all()
```

### 2. REST API 模組
```
/api/v1
├── auth/           # 認證 API
├── clients/        # Client CRUD
├── inventory/      # Inventory 查詢
├── download/       # 下載安裝檔
├── terminal/       # 終端機管理
└── metrics/        # 統計資訊
```

**主要 Endpoints**:
- `POST /api/v1/auth/login` - 使用者登入
- `POST /api/v1/auth/logout` - 使用者登出
- `GET /api/v1/clients` - 取得 Client 列表
- `GET /api/v1/clients/{client_id}` - 取得 Client 詳細資訊
- `GET /api/v1/clients/{client_id}/inventory` - 取得 Inventory
- `GET /api/v1/clients/{client_id}/inventory/history` - 取得歷史記錄
- `GET /api/v1/download/install.sh` - 下載安裝腳本
- `GET /api/v1/download/agent/{os}/{arch}/{version}` - 下載 Agent Binary
- `GET /api/v1/terminal/sessions` - 取得終端機 Sessions
- `GET /api/v1/terminal/sessions/{session_id}/logs` - 取得終端機日誌

### 3. WebSocket 連線管理模組
```python
# websocket_manager.py
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.redis_client = redis.Redis(...)
    
    async def connect(self, client_id: str, websocket: WebSocket):
        """建立 WebSocket 連線"""
        await websocket.accept()
        self.active_connections[client_id] = websocket
        # 更新 Redis 在線狀態
        await self.redis_client.hset(
            f"client:{client_id}",
            mapping={
                "status": "online",
                "last_heartbeat": time.time(),
                "pod_id": os.environ.get("POD_ID")
            }
        )
        await self.redis_client.expire(f"client:{client_id}", 120)
    
    async def disconnect(self, client_id: str):
        """斷線處理"""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        # 從 Redis 移除或標記為 offline
        await self.redis_client.hset(
            f"client:{client_id}",
            "status",
            "offline"
        )
    
    async def handle_heartbeat(self, client_id: str):
        """處理心跳"""
        await self.redis_client.hset(
            f"client:{client_id}",
            "last_heartbeat",
            time.time()
        )
        await self.redis_client.expire(f"client:{client_id}", 120)
```

**WebSocket Endpoint**:
```python
@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str, token: str):
    # 驗證 token
    if not verify_token(token):
        await websocket.close(code=1008)
        return
    
    manager = ConnectionManager()
    await manager.connect(client_id, websocket)
    
    try:
        while True:
            data = await websocket.receive_json()
            await handle_message(client_id, data)
    except WebSocketDisconnect:
        await manager.disconnect(client_id)
```

### 4. Heartbeat 監控模組
```python
# heartbeat_monitor.py
import asyncio

class HeartbeatMonitor:
    def __init__(self, redis_client, db_session):
        self.redis = redis_client
        self.db = db_session
        self.check_interval = 10  # 每 10 秒檢查一次
        self.offline_timeout = 60  # 60 秒無心跳視為離線
    
    async def start(self):
        """啟動心跳監控"""
        while True:
            await self.check_clients_status()
            await asyncio.sleep(self.check_interval)
    
    async def check_clients_status(self):
        """檢查所有 clients 的狀態"""
        current_time = time.time()
        
        # 從 Redis 取得所有 client 的心跳資訊
        for key in self.redis.scan_iter("client:*"):
            client_data = self.redis.hgetall(key)
            last_heartbeat = float(client_data.get("last_heartbeat", 0))
            
            if current_time - last_heartbeat > self.offline_timeout:
                # 標記為 offline
                client_id = key.decode().split(":")[1]
                await self.mark_offline(client_id)
    
    async def mark_offline(self, client_id: str):
        """標記 Client 為離線"""
        # 更新 Redis
        self.redis.hset(f"client:{client_id}", "status", "offline")
        
        # 更新資料庫
        client = self.db.query(Client).filter(Client.id == client_id).first()
        if client:
            client.status = "offline"
            client.last_seen = datetime.utcnow()
            self.db.commit()
```

### 5. Inventory 處理模組
```python
# inventory_handler.py
class InventoryHandler:
    def __init__(self, db_session):
        self.db = db_session
    
    async def update_inventory(self, client_id: str, inventory_data: dict):
        """更新 Inventory 資訊"""
        client = self.db.query(Client).filter(Client.id == client_id).first()
        
        # 檢查是否有變更
        if self.has_changed(client.latest_inventory, inventory_data):
            # 將舊資料移到 history
            if client.latest_inventory:
                history = InventoryHistory(
                    client_id=client_id,
                    inventory_data=client.latest_inventory,
                    collected_at=client.inventory_updated_at
                )
                self.db.add(history)
            
            # 更新 latest
            client.latest_inventory = inventory_data
            client.inventory_updated_at = datetime.utcnow()
            self.db.commit()
    
    def has_changed(self, old_data: dict, new_data: dict) -> bool:
        """檢查資料是否有變更"""
        if not old_data:
            return True
        
        # 比較關鍵欄位
        key_fields = ["os_info", "cpu_info", "memory_total", "disk_total"]
        for field in key_fields:
            if old_data.get(field) != new_data.get(field):
                return True
        
        return False
```

### 6. 下載服務模組
```python
# download_service.py
@router.get("/download/install.sh")
async def download_install_script(
    user: User = Depends(get_current_user)
):
    """下載安裝腳本"""
    # 產生包含 user token 的安裝腳本
    script = generate_install_script(
        user_token=user.api_token,
        server_url=settings.SERVER_URL
    )
    
    return Response(
        content=script,
        media_type="text/x-shellscript",
        headers={
            "Content-Disposition": "attachment; filename=install.sh"
        }
    )

@router.get("/download/agent/{os}/{arch}/{version}")
async def download_agent_binary(
    os: str,
    arch: str,
    version: str,
    token: str
):
    """下載 Agent Binary"""
    # 驗證 token
    if not verify_token(token):
        raise HTTPException(status_code=401)
    
    # 取得 binary 檔案路徑
    binary_path = f"/storage/binaries/{version}/agent-{os}-{arch}"
    
    if not os.path.exists(binary_path):
        raise HTTPException(status_code=404)
    
    return FileResponse(
        binary_path,
        media_type="application/octet-stream",
        filename=f"agent-{os}-{arch}"
    )
```

### 7. 遠端終端機代理模組

```python
# terminal_proxy.py
@router.websocket("/terminal/{client_id}")
async def terminal_websocket(
    websocket: WebSocket,
    client_id: str,
    token: str,
    current_user: User = Depends(get_current_user_from_token)
):
    """Terminal WebSocket endpoint"""
    # 驗證使用者權限
    client = await verify_client_access(client_id, current_user.id)
    if not client:
        await websocket.close(code=1008, reason="Unauthorized")
        return
    
    # 檢查 Client 是否在線
    if not await is_client_online(client_id):
        await websocket.close(code=1008, reason="Client offline")
        return
    
    await terminal_proxy.handle_terminal_connection(
        websocket,
        client_id,
        current_user
    )
```

**功能**:
- 建立 Web UI 到 Client 的終端機代理連線
- 驗證使用者權限和 Client 狀態
- 轉發終端機輸入/輸出
- 管理終端機 Session
- 記錄審計日誌

**詳細設計**: 參考 [遠端終端機存取設計](./remote-terminal.md)

## 多 Pod 架構支援

### Redis Presence 策略
```python
# 每個 Pod 處理自己的 WebSocket 連線
# Redis 儲存所有 clients 的狀態

# Client 連線時
redis.hset(f"client:{client_id}", {
    "status": "online",
    "pod_id": POD_ID,
    "connected_at": timestamp,
    "last_heartbeat": timestamp
})

# 查詢 Client 狀態時 (任何 Pod 都可查詢)
client_status = redis.hget(f"client:{client_id}", "status")
pod_id = redis.hget(f"client:{client_id}", "pod_id")
```

### Session 處理
- WebSocket 連線由單一 Pod 處理
- Redis 儲存 client 在哪個 Pod
- 需要推送訊息時，透過 Redis Pub/Sub 通知對應 Pod

## 設定檔範例

```python
# config.py
from pydantic import BaseSettings

class Settings(BaseSettings):
    # Server
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8080
    SERVER_URL: str = "https://mon.myelintek.com"
    
    # Database
    DATABASE_URL: str = "postgresql://user:pass@db:5432/agentdb"
    
    # Redis
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    
    # WebSocket
    WS_HEARTBEAT_INTERVAL: int = 15
    WS_OFFLINE_TIMEOUT: int = 60
    
    # Security
    SECRET_KEY: str = "your-secret-key"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440
    
    # Binary Storage
    BINARY_STORAGE_PATH: str = "/storage/binaries"
    
    class Config:
        env_file = ".env"
```

## 啟動流程

```python
# main.py
import uvicorn
from fastapi import FastAPI
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 啟動時
    monitor = HeartbeatMonitor(redis_client, db_session)
    asyncio.create_task(monitor.start())
    
    yield
    
    # 關閉時
    await redis_client.close()
    await db_session.close()

app = FastAPI(lifespan=lifespan)

# 註冊路由
app.include_router(web_routes)
app.include_router(api_routes, prefix="/api/v1")

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.SERVER_HOST,
        port=settings.SERVER_PORT,
        workers=1  # WebSocket 需要使用單一 worker
    )
```

## 效能考量

### 連線管理
- 每個 Pod 建議支援 10,000+ 同時連線
- 使用 asyncio 處理並發
- WebSocket 連線保持輕量

### 資料庫查詢
- 使用索引加速查詢 (user_id, client_id)
- Inventory 大量資料考慮分頁
- History 查詢使用時間範圍限制

### Redis 使用
- Heartbeat 資料使用 TTL 自動過期
- 避免儲存大量資料在 Redis
- 使用 Pipeline 批次操作

## 監控與日誌

### 日誌記錄
```python
import logging

logger = logging.getLogger(__name__)

# 連線事件
logger.info(f"Client {client_id} connected from {ip}")

# 心跳事件
logger.debug(f"Heartbeat received from {client_id}")

# 錯誤事件
logger.error(f"Failed to process inventory for {client_id}: {error}")
```

### 健康檢查
```python
@app.get("/health")
async def health_check():
    # 檢查資料庫連線
    # 檢查 Redis 連線
    return {"status": "healthy"}

@app.get("/readiness")
async def readiness_check():
    # 檢查是否準備好接受流量
    return {"status": "ready"}
```

### Metrics
- 在線 Client 數量
- WebSocket 連線數
- API 請求數與延遲
- 資料庫查詢效能
- Redis 操作效能
