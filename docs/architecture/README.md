# 架構文件導覽 (Architecture Documentation)

本目錄包含 Agent 系統的完整架構設計文件。

## 文件索引

### 核心文件

1. **[overview.md](./overview.md)** - 系統架構總覽
   - 系統簡介與核心架構
   - 主要元件說明
   - 連線機制與使用者隔離
   - 安裝部署流程
   - 資料收集與擴展性設計

2. **[server.md](./server.md)** - Server 端設計
   - 技術架構與核心模組
   - Web UI、REST API 設計
   - WebSocket 連線管理
   - Heartbeat 監控機制
   - Inventory 處理與下載服務
   - 多 Pod 架構支援

3. **[client.md](./client.md)** - Client 端設計
   - Golang 實作架構
   - 設定管理與 WebSocket Client
   - 心跳機制與 Inventory 收集器
   - 自動重連機制
   - 交叉編譯與日誌管理

### 協定與通訊

4. **[protocol-websocket.md](./protocol-websocket.md)** - WebSocket 協定
   - 連線建立與認證流程
   - 訊息格式與類型定義
   - Heartbeat、Inventory、Command 協定
   - 連線管理與錯誤處理
   - 效能考量與監控

### 安裝與分發

5. **[install-distribution.md](./install-distribution.md)** - 安裝分發設計
   - 安裝流程與檔案結構
   - install.sh 腳本設計
   - run.sh 與 svc.sh 設計
   - Binary 版本管理
   - 安裝腳本產生與升級機制

### 資料層

6. **[data-model.md](./data-model.md)** - 資料模型設計
   - 資料庫表結構設計
   - Redis 資料結構
   - 資料庫索引策略
   - ORM 模型範例
   - 資料保留與備份策略

### 基礎設施

7. **[kubernetes.md](./kubernetes.md)** - Kubernetes 部署
   - 完整 K8s 資源定義
   - Deployment、Service、Ingress 設定
   - Redis 與 PostgreSQL 部署
   - HPA 與 NetworkPolicy
   - WebSocket 與 TLS 注意事項
   - 部署順序與故障排查

### 安全性

8. **[security.md](./security.md)** - 安全性設計
   - 傳輸層安全 (TLS/WSS)
   - 認證與授權機制
   - 輸入驗證與資料保護
   - 網路安全與審計監控
   - 安全檢查清單與最佳實踐

## 快速導覽

### 如果您想了解...

- **系統整體架構**: 從 [overview.md](./overview.md) 開始
- **如何實作 Server**: 閱讀 [server.md](./server.md)
- **如何實作 Client**: 閱讀 [client.md](./client.md)
- **WebSocket 通訊細節**: 參考 [protocol-websocket.md](./protocol-websocket.md)
- **如何部署安裝**: 查看 [install-distribution.md](./install-distribution.md)
- **資料庫設計**: 參考 [data-model.md](./data-model.md)
- **Kubernetes 部署**: 查看 [kubernetes.md](./kubernetes.md)
- **安全性考量**: 閱讀 [security.md](./security.md)

## 架構圖總覽

```
┌─────────────────────────────────────────────────────────────┐
│                      Internet (HTTPS/WSS)                   │
└───────────────────────────┬─────────────────────────────────┘
                            │
                ┌───────────▼──────────┐
                │   Ingress (TLS)      │
                └───────────┬──────────┘
                            │
                ┌───────────▼──────────┐
                │   Server Pods        │
                │   - Web UI           │
                │   - REST API         │
                │   - WebSocket        │
                └───┬──────────────┬───┘
                    │              │
        ┌───────────▼───┐    ┌────▼──────────┐
        │     Redis     │    │   PostgreSQL  │
        │  (Presence)   │    │  (Persistent) │
        └───────────────┘    └───────────────┘
                    │
                    │ WSS
                    │
    ┌───────────────┼───────────────┐
    │               │               │
┌───▼───┐       ┌───▼───┐      ┌───▼───┐
│Client │       │Client │      │Client │
│(Agent)│       │(Agent)│      │(Agent)│
└───────┘       └───────┘      └───────┘
```

## 系統特點

### 核心功能
- ✅ Python Server + Golang Client
- ✅ Kubernetes + Ingress + TLS
- ✅ WebSocket (WSS) 長連線
- ✅ Heartbeat 15s / Offline timeout 60s
- ✅ 使用者資料隔離
- ✅ 多平台 Agent 支援

### 安裝方式
- ✅ install.sh 腳本安裝 (不使用 curl | sh)
- ✅ run.sh 前景執行
- ✅ svc.sh 管理 systemd service
- ✅ 版本化 Binary 管理

### 資料收集
- ✅ OS + CPU + Disk + IP + Memory
- ✅ Latest + History 儲存
- ✅ 通用欄位 + Raw/Payload 擴充
- ✅ 支援多種 OS/架構

### 高可用性
- ✅ 多 Pod 部署
- ✅ Redis Presence 策略
- ✅ WebSocket 自動重連
- ✅ 水平擴展支援

## 技術堆疊

### Server 端
- Python 3.9+
- FastAPI / Flask
- SQLAlchemy (PostgreSQL/MySQL)
- Redis
- asyncio

### Client 端
- Golang 1.20+
- gorilla/websocket
- gopsutil
- viper

### 基礎設施
- Kubernetes
- Ingress (Nginx)
- PostgreSQL
- Redis
- Docker

## 開發規範

### 編碼標準
- Server: PEP 8 (Python)
- Client: Go Standard Style
- 註解: 繁體中文 + 英文術語

### Git Workflow
- main: 主要分支
- develop: 開發分支
- feature/*: 功能分支
- hotfix/*: 修復分支

### 版本管理
- 遵循語意化版本 (Semantic Versioning)
- 格式: vMAJOR.MINOR.PATCH
- 範例: v1.0.0, v1.1.0, v2.0.0

## 相關資源

### 內部連結
- [專案 README](../../README.md)
- [部署指南](../deployment/README.md) (待建立)
- [API 文件](../api/README.md) (待建立)

### 外部資源
- [FastAPI 文件](https://fastapi.tiangolo.com/)
- [Gorilla WebSocket](https://github.com/gorilla/websocket)
- [Kubernetes 文件](https://kubernetes.io/docs/)
- [PostgreSQL 文件](https://www.postgresql.org/docs/)

## 貢獻指南

如需更新或改進文件，請：
1. 建立新分支
2. 修改對應文件
3. 提交 Pull Request
4. 等待審核

## 授權

本文件為專案內部文件，僅供團隊成員參考使用。

---

最後更新: 2024-02-05
維護者: Development Team
