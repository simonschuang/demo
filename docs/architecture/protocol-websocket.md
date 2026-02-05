# WebSocket 協定設計 (WebSocket Protocol Design)

## 連線建立

### WebSocket URL 格式
```
wss://{server_domain}/ws/{client_id}?token={auth_token}
```

**參數說明**:
- `server_domain`: Server 的網域名稱
- `client_id`: Client 的唯一識別碼 (UUID)
- `auth_token`: 認證 Token (由 Server 產生)

**範例**:
```
wss://agent.example.com/ws/550e8400-e29b-41d4-a716-446655440000?token=eyJhbGc...
```

### 連線流程

```
Client                                Server
  |                                      |
  |-------- WebSocket Handshake ------->|
  |         (with auth token)            |
  |                                      |
  |<------- 101 Switching Protocols ----|
  |          (connection accepted)       |
  |                                      |
  |<----------- welcome message ---------|
  |                                      |
  |-------- heartbeat (every 15s) ----->|
  |                                      |
  |<----------- heartbeat_ack -----------|
  |                                      |
```

### 認證失敗
如果認證失敗，Server 會立即關閉連線：
```
Close Code: 1008 (Policy Violation)
Close Reason: "Authentication failed"
```

## 訊息格式

### 基本訊息結構
所有訊息使用 JSON 格式：

```json
{
    "type": "message_type",
    "data": { ... },
    "timestamp": 1234567890,
    "message_id": "uuid-xxxx" (optional)
}
```

**欄位說明**:
- `type`: 訊息類型 (必填)
- `data`: 訊息內容，根據不同類型有不同結構 (必填)
- `timestamp`: Unix timestamp (必填)
- `message_id`: 訊息唯一識別碼，用於追蹤和回應 (選填)

## 訊息類型

### 1. Heartbeat (心跳)

#### Client -> Server
```json
{
    "type": "heartbeat",
    "data": {
        "status": "alive",
        "uptime": 3600
    },
    "timestamp": 1234567890
}
```

**data 欄位**:
- `status`: 狀態，固定為 "alive"
- `uptime`: Client 執行時間 (秒)

#### Server -> Client (heartbeat_ack)
```json
{
    "type": "heartbeat_ack",
    "data": {
        "server_time": 1234567890
    },
    "timestamp": 1234567890
}
```

**data 欄位**:
- `server_time`: Server 端時間，用於時間同步

### 2. Welcome (歡迎訊息)

#### Server -> Client (連線建立後立即發送)
```json
{
    "type": "welcome",
    "data": {
        "client_id": "550e8400-e29b-41d4-a716-446655440000",
        "server_version": "v1.0.0",
        "heartbeat_interval": 15,
        "inventory_interval": 60
    },
    "timestamp": 1234567890
}
```

**data 欄位**:
- `client_id`: Client 識別碼
- `server_version`: Server 版本
- `heartbeat_interval`: 建議的心跳間隔 (秒)
- `inventory_interval`: 建議的 Inventory 回報間隔 (秒)

### 3. Inventory (設備資訊)

#### Client -> Server
```json
{
    "type": "inventory",
    "data": {
        "hostname": "server-01",
        "os": "linux",
        "platform": "ubuntu",
        "arch": "amd64",
        "cpu_count": 8,
        "cpu_model": "Intel(R) Xeon(R) CPU E5-2680 v4",
        "memory_total": 34359738368,
        "memory_used": 17179869184,
        "disk_total": 1099511627776,
        "disk_used": 549755813888,
        "ip_addresses": ["192.168.1.100", "10.0.0.5"],
        "mac_addresses": ["00:0a:95:9d:68:16"],
        "raw_data": {
            "cpu": [...],
            "memory": {...},
            "disks": [...]
        }
    },
    "timestamp": 1234567890
}
```

**data 欄位** (詳見 data-model.md):
- `hostname`: 主機名稱
- `os`: 作業系統
- `platform`: 平台資訊
- `arch`: 架構
- `cpu_*`: CPU 相關資訊
- `memory_*`: 記憶體相關資訊
- `disk_*`: 磁碟相關資訊
- `ip_addresses`: IP 位址列表
- `mac_addresses`: MAC 位址列表
- `raw_data`: 原始詳細資料

#### Server -> Client (inventory_ack)
```json
{
    "type": "inventory_ack",
    "data": {
        "received": true,
        "changed": true
    },
    "timestamp": 1234567890
}
```

**data 欄位**:
- `received`: 是否成功接收
- `changed`: 資料是否有變更 (與上次相比)

### 4. Command (命令下發)

#### Server -> Client
```json
{
    "type": "command",
    "data": {
        "command": "update_config",
        "params": {
            "heartbeat_interval": 30,
            "collect_interval": 120
        }
    },
    "message_id": "cmd-uuid-xxxx",
    "timestamp": 1234567890
}
```

**支援的命令**:
- `update_config`: 更新設定
- `collect_inventory`: 立即收集 Inventory
- `restart`: 重啟 Agent
- `shutdown`: 關閉 Agent

#### Client -> Server (command_response)
```json
{
    "type": "command_response",
    "data": {
        "command": "update_config",
        "status": "success",
        "message": "Config updated successfully",
        "result": {...}
    },
    "message_id": "cmd-uuid-xxxx",
    "timestamp": 1234567890
}
```

**data 欄位**:
- `command`: 對應的命令名稱
- `status`: 執行狀態 ("success" / "error")
- `message`: 訊息說明
- `result`: 執行結果 (選填)

### 5. Ping/Pong (連線保持)

#### Server -> Client
```json
{
    "type": "ping",
    "data": {},
    "timestamp": 1234567890
}
```

#### Client -> Server
```json
{
    "type": "pong",
    "data": {},
    "timestamp": 1234567890
}
```

### 6. Error (錯誤訊息)

#### Server -> Client 或 Client -> Server
```json
{
    "type": "error",
    "data": {
        "code": "INVALID_MESSAGE",
        "message": "Invalid message format",
        "details": "..."
    },
    "timestamp": 1234567890
}
```

**錯誤代碼**:
- `AUTH_FAILED`: 認證失敗
- `INVALID_MESSAGE`: 訊息格式錯誤
- `INTERNAL_ERROR`: 內部錯誤
- `RATE_LIMIT`: 頻率限制
- `CLIENT_NOT_FOUND`: Client 不存在

### 7. Terminal (終端機訊息)

#### Server -> Client (terminal_command)
```json
{
    "type": "terminal_command",
    "data": {
        "session_id": "session-uuid-xxxx",
        "command": "init|input|resize|close",
        "params": {
            "rows": 24,
            "cols": 80,
            "input": "ls -la\n",
            "shell": "/bin/bash"
        }
    },
    "timestamp": 1234567890
}
```

**command 類型**:
- `init`: 初始化終端機
- `input`: 使用者輸入
- `resize`: 調整終端機大小
- `close`: 關閉終端機

#### Client -> Server (terminal_data)
```json
{
    "type": "terminal_data",
    "data": {
        "session_id": "session-uuid-xxxx",
        "output": "total 48\ndrwxr-xr-x 5 user user 4096...",
        "type": "output|error"
    },
    "timestamp": 1234567890
}
```

**data 欄位**:
- `session_id`: 終端機 Session ID
- `output`: 終端機輸出內容
- `type`: 輸出類型 (output 或 error)

**詳細設計**: 參考 [遠端終端機存取設計](./remote-terminal.md)

## 連線管理

### 連線狀態

```
States:
- DISCONNECTED: 未連線
- CONNECTING: 連線中
- CONNECTED: 已連線
- RECONNECTING: 重新連線中
```

### 心跳機制

**時間參數**:
- Heartbeat Interval: 15 秒
- Offline Timeout: 60 秒
- Reconnect Interval: 5 秒

**流程**:
1. Client 每 15 秒發送一次 heartbeat
2. Server 更新 Redis 中的 last_heartbeat 時間
3. Server 定期檢查 (每 10 秒)
4. 超過 60 秒未收到心跳 → 標記為 offline

### 斷線重連

**Client 端重連邏輯**:
```
1. 檢測到連線斷開
2. 等待 5 秒
3. 嘗試重新連線
4. 如果連線失敗，重複步驟 2-3
5. 最大重試次數: 無限制 (持續重試)
```

**Exponential Backoff** (建議):
```
重連間隔: 5s → 10s → 20s → 40s → 60s (最大)
```

### 連線超時

**Kubernetes Ingress 設定**:
- Proxy Read Timeout: 3600s (1 小時)
- Proxy Send Timeout: 3600s (1 小時)
- WebSocket 連線建議保持長時間

## 訊息流程範例

### 完整連線與資料回報流程

```
Client                                    Server
  |                                          |
  |------- WebSocket Connect --------------->|
  |                                          |
  |<------------ Welcome --------------------|
  |                                          |
  |------- Heartbeat (15s) ---------------->|
  |                                          |
  |<------- Heartbeat ACK -------------------|
  |                                          |
  |------- Inventory (60s) ---------------->|
  |                                          |
  |<------- Inventory ACK -------------------|
  |                                          |
  |------- Heartbeat (15s) ---------------->|
  |                                          |
  |<------- Command: update_config ----------|
  |                                          |
  |------- Command Response ---------------->|
  |                                          |
  |------- Heartbeat (30s, updated) ------->|
  |                                          |
  ... continuous ...
```

### 斷線重連流程

```
Client                                    Server
  |                                          |
  |------- Heartbeat ---------------------->|
  |                                          |
  |  X  Connection Lost  X                   |
  |                                          |
  (wait 5s)                                  |
  |                                          |
  |------- Reconnect ---------------------->|
  |                                          |
  |<------- Welcome -------------------------|
  |                                          |
  |------- Heartbeat ---------------------->|
  |                                          |
```

## 效能考量

### 訊息大小限制
- 一般訊息: < 64 KB
- Inventory 訊息: < 1 MB
- 超過限制會被拒絕

### 頻率限制
- Heartbeat: 每 15 秒 (固定)
- Inventory: 每 60 秒 (建議)
- Command: 無限制 (Server 控制)
- 其他訊息: 最多 10 次/秒

### 壓縮
- 支援 Per-Message Deflate 壓縮 (選用)
- 建議在 Inventory 等大訊息時啟用

## 安全性

### 傳輸安全
- 必須使用 WSS (WebSocket Secure)
- TLS 1.2+
- 強加密演算法

### 認證
- Token-based 認證
- Token 需包含: client_id, user_id, expiry
- Token 應定期更換 (建議每 24 小時)

### 訊息驗證
- 檢查訊息格式
- 驗證 timestamp (避免 replay attack)
- 訊息大小限制

## 錯誤處理

### Client 端錯誤處理
```go
func handleError(err error) {
    switch {
    case errors.Is(err, websocket.ErrCloseSent):
        // 正常關閉
        log.Info("Connection closed normally")
    case isNetworkError(err):
        // 網路錯誤，嘗試重連
        log.Error("Network error, reconnecting...")
        reconnect()
    default:
        // 其他錯誤
        log.Errorf("Unexpected error: %v", err)
    }
}
```

### Server 端錯誤處理
```python
async def handle_message_error(client_id: str, error: Exception):
    if isinstance(error, ValidationError):
        # 訊息格式錯誤
        await send_error(client_id, "INVALID_MESSAGE", str(error))
    elif isinstance(error, DatabaseError):
        # 資料庫錯誤
        logger.error(f"Database error for {client_id}: {error}")
        await send_error(client_id, "INTERNAL_ERROR", "Database error")
    else:
        # 未知錯誤
        logger.error(f"Unknown error for {client_id}: {error}")
        await send_error(client_id, "INTERNAL_ERROR", "Unknown error")
```

## 監控與除錯

### 訊息日誌格式
```json
{
    "timestamp": "2024-01-01T00:00:00Z",
    "direction": "in|out",
    "client_id": "550e8400-e29b-41d4-a716-446655440000",
    "message_type": "heartbeat",
    "size": 128,
    "latency_ms": 50
}
```

### 監控指標
- 每秒訊息數 (messages/sec)
- 訊息延遲 (latency)
- 連線數 (active connections)
- 錯誤率 (error rate)
- 重連次數 (reconnection count)
