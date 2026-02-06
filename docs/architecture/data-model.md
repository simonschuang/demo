# 資料模型設計 (Data Model Design)

## 資料庫選擇

建議使用 **PostgreSQL** 或 **MySQL**，兩者皆支援完整的 ACID 特性和 JSON 欄位類型。

## 資料表結構

### 1. users (使用者表)

```sql
CREATE TABLE users (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username            VARCHAR(255) UNIQUE NOT NULL,
    email               VARCHAR(255) UNIQUE NOT NULL,
    password_hash       VARCHAR(255) NOT NULL,
    api_token           VARCHAR(255) UNIQUE,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login_at       TIMESTAMP,
    is_active           BOOLEAN DEFAULT TRUE,
    
    INDEX idx_username (username),
    INDEX idx_email (email),
    INDEX idx_api_token (api_token)
);
```

**欄位說明**:
- `id`: 使用者唯一識別碼 (UUID)
- `username`: 使用者名稱
- `email`: 電子郵件
- `password_hash`: 密碼雜湊 (bcrypt)
- `api_token`: API Token (用於安裝時認證)
- `created_at`: 建立時間
- `updated_at`: 更新時間
- `last_login_at`: 最後登入時間
- `is_active`: 是否啟用

### 2. clients (Client 註冊表)

```sql
CREATE TABLE clients (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    hostname            VARCHAR(255),
    client_token        VARCHAR(255) UNIQUE NOT NULL,
    status              VARCHAR(50) DEFAULT 'offline',
    
    -- 基本資訊
    os                  VARCHAR(50),
    platform            VARCHAR(100),
    arch                VARCHAR(50),
    agent_version       VARCHAR(50),
    
    -- 時間記錄
    registered_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    first_connected_at  TIMESTAMP,
    last_connected_at   TIMESTAMP,
    last_seen           TIMESTAMP,
    
    -- 連線資訊
    ip_address          VARCHAR(45),
    
    INDEX idx_user_id (user_id),
    INDEX idx_status (status),
    INDEX idx_client_token (client_token),
    INDEX idx_last_seen (last_seen)
);
```

**欄位說明**:
- `id`: Client 唯一識別碼 (UUID)
- `user_id`: 所屬使用者 ID
- `hostname`: 主機名稱
- `client_token`: Client 認證 Token
- `status`: 狀態 (online/offline)
- `os`: 作業系統 (linux/darwin/windows)
- `platform`: 平台資訊 (ubuntu/centos/macos 等)
- `arch`: 架構 (amd64/arm64/386)
- `agent_version`: Agent 版本
- `registered_at`: 註冊時間
- `first_connected_at`: 首次連線時間
- `last_connected_at`: 最後連線時間
- `last_seen`: 最後看到時間 (心跳更新)
- `ip_address`: IP 位址

### 3. inventory_latest (最新 Inventory)

```sql
CREATE TABLE inventory_latest (
    id                  BIGSERIAL PRIMARY KEY,
    client_id           UUID UNIQUE NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    
    -- 通用欄位
    hostname            VARCHAR(255),
    os                  VARCHAR(50),
    platform            VARCHAR(100),
    arch                VARCHAR(50),
    
    -- CPU 資訊
    cpu_count           INTEGER,
    cpu_model           VARCHAR(255),
    cpu_usage_percent   DECIMAL(5,2),
    
    -- Memory 資訊
    memory_total        BIGINT,
    memory_used         BIGINT,
    memory_free         BIGINT,
    memory_usage_percent DECIMAL(5,2),
    
    -- Disk 資訊
    disk_total          BIGINT,
    disk_used           BIGINT,
    disk_free           BIGINT,
    disk_usage_percent  DECIMAL(5,2),
    
    -- Network 資訊
    ip_addresses        TEXT[],
    mac_addresses       TEXT[],
    
    -- 時間戳記
    collected_at        TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- 原始資料 (JSON)
    raw_data            JSONB,
    
    INDEX idx_client_id (client_id),
    INDEX idx_updated_at (updated_at)
);
```

**欄位說明**:
- `id`: 記錄 ID
- `client_id`: 對應的 Client ID
- 通用欄位: hostname, os, platform, arch
- CPU 欄位: 數量、型號、使用率
- Memory 欄位: 總量、已用、可用、使用率
- Disk 欄位: 總量、已用、可用、使用率
- Network 欄位: IP 位址列表、MAC 位址列表
- `collected_at`: 資料收集時間
- `updated_at`: 記錄更新時間
- `raw_data`: 原始完整資料 (JSONB 格式)

**raw_data 結構範例**:
```json
{
    "host": {
        "hostname": "server-01",
        "uptime": 3600,
        "boot_time": 1234567890,
        "procs": 150,
        "os": "linux",
        "platform": "ubuntu",
        "platform_version": "22.04",
        "kernel_version": "5.15.0-58-generic",
        "kernel_arch": "x86_64"
    },
    "cpu": [
        {
            "cpu": 0,
            "model_name": "Intel(R) Xeon(R) CPU E5-2680 v4",
            "mhz": 2400.0,
            "cache_size": 35840,
            "cores": 14
        }
    ],
    "memory": {
        "total": 34359738368,
        "available": 17179869184,
        "used": 17179869184,
        "used_percent": 50.0,
        "free": 17179869184
    },
    "disks": [
        {
            "device": "/dev/sda1",
            "mountpoint": "/",
            "fstype": "ext4",
            "total": 1099511627776,
            "used": 549755813888,
            "free": 549755813888,
            "used_percent": 50.0
        }
    ],
    "network": [
        {
            "name": "eth0",
            "mtu": 1500,
            "hardwareaddr": "00:0a:95:9d:68:16",
            "flags": ["up", "broadcast", "multicast"],
            "addrs": [
                {
                    "addr": "192.168.1.100/24"
                }
            ]
        }
    ]
}
```

### 4. inventory_history (Inventory 歷史記錄)

```sql
CREATE TABLE inventory_history (
    id                  BIGSERIAL PRIMARY KEY,
    client_id           UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    
    -- 通用欄位
    hostname            VARCHAR(255),
    os                  VARCHAR(50),
    platform            VARCHAR(100),
    arch                VARCHAR(50),
    
    -- CPU 資訊
    cpu_count           INTEGER,
    cpu_model           VARCHAR(255),
    
    -- Memory 資訊
    memory_total        BIGINT,
    memory_used         BIGINT,
    
    -- Disk 資訊
    disk_total          BIGINT,
    disk_used           BIGINT,
    
    -- Network 資訊
    ip_addresses        TEXT[],
    mac_addresses       TEXT[],
    
    -- 變更類型
    change_type         VARCHAR(50),
    change_summary      TEXT,
    
    -- 時間戳記
    collected_at        TIMESTAMP NOT NULL,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- 原始資料 (JSON)
    raw_data            JSONB,
    
    INDEX idx_client_id (client_id),
    INDEX idx_collected_at (collected_at),
    INDEX idx_created_at (created_at)
);
```

**欄位說明**:
- 與 inventory_latest 類似，但儲存歷史記錄
- `change_type`: 變更類型 (hardware_change, network_change, etc.)
- `change_summary`: 變更摘要
- `collected_at`: 原始收集時間
- `created_at`: 寫入歷史記錄時間

**變更類型 (change_type)**:
- `hardware_change`: 硬體變更 (CPU, Memory, Disk)
- `network_change`: 網路變更 (IP, MAC)
- `os_change`: 作業系統變更
- `periodic_snapshot`: 定期快照

### 5. agent_versions (Agent 版本管理)

```sql
CREATE TABLE agent_versions (
    id                  SERIAL PRIMARY KEY,
    version             VARCHAR(50) UNIQUE NOT NULL,
    release_date        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_latest           BOOLEAN DEFAULT FALSE,
    
    -- 版本資訊
    changelog           TEXT,
    min_server_version  VARCHAR(50),
    
    -- 下載統計
    download_count      INTEGER DEFAULT 0,
    
    -- 二進位檔案資訊 (JSON)
    binaries            JSONB,
    
    INDEX idx_version (version),
    INDEX idx_is_latest (is_latest)
);
```

**binaries 結構範例**:
```json
{
    "linux-amd64": {
        "filename": "agent-linux-amd64-v1.0.0",
        "size": 12345678,
        "sha256": "1234567890abcdef...",
        "path": "/storage/binaries/v1.0.0/agent-linux-amd64"
    },
    "linux-arm64": {
        "filename": "agent-linux-arm64-v1.0.0",
        "size": 12345678,
        "sha256": "abcdef1234567890...",
        "path": "/storage/binaries/v1.0.0/agent-linux-arm64"
    },
    "darwin-amd64": {...},
    "darwin-arm64": {...},
    "windows-amd64": {...}
}
```

### 6. audit_logs (審計日誌)

```sql
CREATE TABLE audit_logs (
    id                  BIGSERIAL PRIMARY KEY,
    user_id             UUID REFERENCES users(id) ON DELETE SET NULL,
    client_id           UUID REFERENCES clients(id) ON DELETE SET NULL,
    
    -- 事件資訊
    event_type          VARCHAR(100) NOT NULL,
    event_action        VARCHAR(100) NOT NULL,
    event_result        VARCHAR(50),
    
    -- 詳細資訊
    ip_address          VARCHAR(45),
    user_agent          TEXT,
    details             JSONB,
    
    -- 時間戳記
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_user_id (user_id),
    INDEX idx_client_id (client_id),
    INDEX idx_event_type (event_type),
    INDEX idx_created_at (created_at)
);
```

**事件類型 (event_type)**:
- `user.login`: 使用者登入
- `user.logout`: 使用者登出
- `client.register`: Client 註冊
- `client.connect`: Client 連線
- `client.disconnect`: Client 斷線
- `inventory.update`: Inventory 更新
- `command.execute`: 命令執行

## Redis 資料結構

### 1. Client Presence (在線狀態)

```
Key: client:{client_id}
Type: Hash
TTL: 120 seconds (自動過期)

Fields:
- status: "online" | "offline"
- last_heartbeat: timestamp
- pod_id: server pod ID
- connected_at: timestamp
- ip_address: client IP

Example:
HSET client:550e8400-e29b-41d4-a716-446655440000 \
    status "online" \
    last_heartbeat "1234567890" \
    pod_id "pod-abc123" \
    connected_at "1234567890" \
    ip_address "192.168.1.100"

EXPIRE client:550e8400-e29b-41d4-a716-446655440000 120
```

### 2. User Active Clients (使用者的在線 Clients)

```
Key: user:{user_id}:clients
Type: Set
TTL: None (手動管理)

Members: client_id 列表

Example:
SADD user:123e4567-e89b-12d3-a456-426614174000:clients \
    "550e8400-e29b-41d4-a716-446655440000" \
    "660e8400-e29b-41d4-a716-446655440001"
```

### 3. Pod Connections (Pod 的連線列表)

```
Key: pod:{pod_id}:connections
Type: Set
TTL: None (手動管理)

Members: client_id 列表

Example:
SADD pod:pod-abc123:connections \
    "550e8400-e29b-41d4-a716-446655440000" \
    "660e8400-e29b-41d4-a716-446655440001"
```

### 4. WebSocket Session

```
Key: session:{client_id}
Type: Hash
TTL: 7200 seconds (2 hours)

Fields:
- user_id: 所屬使用者 ID
- authenticated: true/false
- auth_time: 認證時間

Example:
HSET session:550e8400-e29b-41d4-a716-446655440000 \
    user_id "123e4567-e89b-12d3-a456-426614174000" \
    authenticated "true" \
    auth_time "1234567890"
```

## 資料庫索引策略

### 必要索引
```sql
-- clients 表
CREATE INDEX idx_clients_user_status ON clients(user_id, status);
CREATE INDEX idx_clients_last_seen ON clients(last_seen DESC);

-- inventory_latest 表
CREATE INDEX idx_inventory_client_updated ON inventory_latest(client_id, updated_at);

-- inventory_history 表
CREATE INDEX idx_history_client_collected ON inventory_history(client_id, collected_at DESC);
CREATE INDEX idx_history_change_type ON inventory_history(change_type);

-- audit_logs 表
CREATE INDEX idx_audit_user_created ON audit_logs(user_id, created_at DESC);
CREATE INDEX idx_audit_event_created ON audit_logs(event_type, created_at DESC);
```

### JSONB 索引 (PostgreSQL)
```sql
-- 為 raw_data 中的特定欄位建立索引
CREATE INDEX idx_inventory_raw_os ON inventory_latest ((raw_data->>'host'->>'os'));
CREATE INDEX idx_inventory_raw_platform ON inventory_latest ((raw_data->>'host'->>'platform'));

-- GIN 索引用於全文搜尋
CREATE INDEX idx_inventory_raw_gin ON inventory_latest USING GIN (raw_data);
```

## ORM 模型範例 (Python SQLAlchemy)

### User Model
```python
from sqlalchemy import Column, String, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid

class User(Base):
    __tablename__ = 'users'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(255), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    api_token = Column(String(255), unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login_at = Column(DateTime)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    clients = relationship("Client", back_populates="user")
```

### Client Model
```python
class Client(Base):
    __tablename__ = 'clients'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'))
    hostname = Column(String(255))
    client_token = Column(String(255), unique=True, nullable=False)
    status = Column(String(50), default='offline')
    
    os = Column(String(50))
    platform = Column(String(100))
    arch = Column(String(50))
    agent_version = Column(String(50))
    
    registered_at = Column(DateTime, default=datetime.utcnow)
    first_connected_at = Column(DateTime)
    last_connected_at = Column(DateTime)
    last_seen = Column(DateTime)
    
    ip_address = Column(String(45))
    
    # Relationships
    user = relationship("User", back_populates="clients")
    inventory = relationship("InventoryLatest", back_populates="client", uselist=False)
    history = relationship("InventoryHistory", back_populates="client")
```

### InventoryLatest Model
```python
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

class InventoryLatest(Base):
    __tablename__ = 'inventory_latest'
    
    id = Column(BigInteger, primary_key=True)
    client_id = Column(UUID(as_uuid=True), ForeignKey('clients.id', ondelete='CASCADE'), unique=True)
    
    hostname = Column(String(255))
    os = Column(String(50))
    platform = Column(String(100))
    arch = Column(String(50))
    
    cpu_count = Column(Integer)
    cpu_model = Column(String(255))
    cpu_usage_percent = Column(Numeric(5, 2))
    
    memory_total = Column(BigInteger)
    memory_used = Column(BigInteger)
    memory_free = Column(BigInteger)
    memory_usage_percent = Column(Numeric(5, 2))
    
    disk_total = Column(BigInteger)
    disk_used = Column(BigInteger)
    disk_free = Column(BigInteger)
    disk_usage_percent = Column(Numeric(5, 2))
    
    ip_addresses = Column(ARRAY(String))
    mac_addresses = Column(ARRAY(String))
    
    collected_at = Column(DateTime)
    updated_at = Column(DateTime, default=datetime.utcnow)
    
    raw_data = Column(JSONB)
    
    # Relationships
    client = relationship("Client", back_populates="inventory")
```

## 資料保留策略

### Inventory History
- 保留 90 天的詳細歷史記錄
- 90 天後只保留每月快照
- 1 年後只保留每季快照

```sql
-- 清理 90 天前的非快照記錄
DELETE FROM inventory_history 
WHERE collected_at < NOW() - INTERVAL '90 days'
  AND change_type != 'periodic_snapshot';

-- 清理 1 年前的非季度快照記錄
DELETE FROM inventory_history 
WHERE collected_at < NOW() - INTERVAL '1 year'
  AND change_type = 'periodic_snapshot'
  AND EXTRACT(MONTH FROM collected_at) NOT IN (1, 4, 7, 10);
```

### Audit Logs
- 保留 180 天的審計日誌
- 重要事件 (如安全相關) 永久保留

```sql
-- 清理 180 天前的一般日誌
DELETE FROM audit_logs 
WHERE created_at < NOW() - INTERVAL '180 days'
  AND event_type NOT LIKE 'security.%';
```

## 備份策略

### 每日備份
```bash
# 完整備份
pg_dump -U postgres agentdb > backup_$(date +%Y%m%d).sql

# 壓縮備份
pg_dump -U postgres agentdb | gzip > backup_$(date +%Y%m%d).sql.gz
```

### 持續歸檔 (WAL)
```sql
-- postgresql.conf
archive_mode = on
archive_command = 'cp %p /backup/archive/%f'
```

## 效能優化建議

1. **分區表** (Partitioning)
   - inventory_history 按月分區
   - audit_logs 按月分區

2. **連線池** (Connection Pooling)
   - 使用 PgBouncer 或 SQLAlchemy Pool

3. **查詢優化**
   - 使用 EXPLAIN ANALYZE 分析慢查詢
   - 適當使用索引
   - 避免 N+1 查詢問題

4. **快取策略**
   - Redis 快取熱門查詢結果
   - 設定合理的 TTL
