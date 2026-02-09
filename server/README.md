# Agent Monitor Server

Python FastAPI 後端服務，用於 Agent 監控平台。

## 版本

當前版本: **v1.0.0**

檢查版本:
```bash
# API endpoint
curl http://localhost:8080/api/v1/version

# 或透過 Makefile
make version
```

## 需求

- Python 3.9+
- SQLite (測試) 或 PostgreSQL (生產環境)
- Redis (可選，用於多 Pod 狀態共享)

## 快速開始

### 1. 建立虛擬環境

```bash
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# 或
venv\Scripts\activate  # Windows
```

### 2. 安裝依賴

```bash
pip install -r requirements.txt
# 或使用 Makefile
make install
```

### 3. 設定環境變數

```bash
# 使用 SQLite (測試)
export DATABASE_URL="sqlite+aiosqlite:///./test.db"

# 或使用 PostgreSQL (生產環境)
# export DATABASE_URL="postgresql+asyncpg://user:password@localhost:5432/agentdb"

# Redis (可選)
export REDIS_HOST="localhost"
export REDIS_PORT="6379"

# Security
export SECRET_KEY="your-super-secret-key-change-in-production"
```

或者複製 `.env.example` 為 `.env` 並修改設定：

```bash
cp .env.example .env
# 編輯 .env 檔案
```

### 4. 啟動服務

```bash
# 開發模式 (自動重載)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
# 或使用 Makefile
make dev

# 生產模式
uvicorn app.main:app --host 0.0.0.0 --port 8080 --workers 4
# 或使用 Makefile
make run
```

## 生產環境部署

### 設定版本號

```bash
# 使用 Makefile 設定版本
make set-version VERSION=1.0.0

# 或手動編輯 app/__init__.py
__version__ = "1.0.0"
__build_time__ = "2026-02-09 00:00:00 UTC"
```

### Docker 部署

```bash
# 建立 Docker image
make build-docker VERSION=1.0.0

# 或手動
docker build -t agent-monitor-server:1.0.0 .
```

### 5. 存取服務

- **Web UI**: http://localhost:8080
- **API Docs (Swagger)**: http://localhost:8080/docs
- **API Docs (ReDoc)**: http://localhost:8080/redoc

## 測試

### 執行單元測試

```bash
export DATABASE_URL="sqlite+aiosqlite:///./test.db"
python -m pytest tests/ -v
```

### 手動測試 API

#### 1. 註冊使用者

```bash
curl -X POST http://localhost:8080/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","email":"admin@example.com","password":"admin123"}'
```

#### 2. 登入取得 Token

```bash
curl -X POST http://localhost:8080/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'
```

#### 3. 建立 Client

```bash
curl -X POST http://localhost:8080/api/v1/clients \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <YOUR_TOKEN>" \
  -d '{"hostname":"test-client","os":"linux","platform":"ubuntu","arch":"amd64","agent_version":"1.0.0"}'
```

#### 4. 查看 Client 列表

```bash
curl http://localhost:8080/api/v1/clients \
  -H "Authorization: Bearer <YOUR_TOKEN>"
```

#### 5. 查看 Client Inventory

```bash
curl http://localhost:8080/api/v1/inventory/<CLIENT_ID> \
  -H "Authorization: Bearer <YOUR_TOKEN>"
```

## API 端點

### 認證 API

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/register` | 註冊新使用者 |
| POST | `/api/v1/auth/login` | 使用者登入 |
| GET | `/api/v1/auth/me` | 取得當前使用者資訊 |

### Client API

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/clients` | 取得 Client 列表 |
| POST | `/api/v1/clients` | 建立新 Client |
| GET | `/api/v1/clients/{client_id}` | 取得 Client 詳細資訊 |
| DELETE | `/api/v1/clients/{client_id}` | 刪除 Client |
| POST | `/api/v1/clients/{client_id}/regenerate-token` | 重新產生 Client Token |

### Inventory API

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/inventory/{client_id}` | 取得最新 Inventory |
| GET | `/api/v1/inventory/{client_id}/history` | 取得 Inventory 歷史記錄 |

### WebSocket

| Endpoint | Description |
|----------|-------------|
| `ws://localhost:8080/ws/{client_id}?token=<CLIENT_TOKEN>` | Client WebSocket 連線 |

## 專案結構

```
server/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI 應用程式入口
│   ├── config.py            # 設定管理
│   ├── database.py          # 資料庫連線
│   ├── auth.py              # JWT 認證
│   ├── redis_client.py      # Redis 客戶端
│   ├── models/              # SQLAlchemy 模型
│   │   ├── user.py
│   │   ├── client.py
│   │   └── inventory.py
│   ├── schemas/             # Pydantic Schemas
│   │   ├── user.py
│   │   ├── client.py
│   │   └── inventory.py
│   ├── api/                 # REST API 路由
│   │   ├── auth.py
│   │   ├── clients.py
│   │   └── inventory.py
│   └── websocket/           # WebSocket 處理
│       ├── manager.py
│       └── handler.py
├── web/                     # 前端網頁
│   ├── static/
│   └── templates/
├── tests/                   # 測試檔案
├── requirements.txt
├── .env.example
└── README.md
```

## Docker 部署

```bash
# 建立 Docker 映像
docker build -t agent-server .

# 執行容器
docker run -d \
  -p 8080:8080 \
  -e DATABASE_URL="postgresql+asyncpg://user:pass@db:5432/agentdb" \
  -e REDIS_HOST="redis" \
  -e SECRET_KEY="your-secret-key" \
  agent-server
```

## 功能特色

- ✅ JWT Token 認證
- ✅ WebSocket 長連線支援
- ✅ Client Heartbeat 監控
- ✅ 系統 Inventory 收集
- ✅ 使用者資料隔離
- ✅ Redis 狀態快取 (可選)
- ✅ 自動 API 文件 (Swagger/ReDoc)
