# 系統架構總覽 (System Architecture Overview)

## 系統簡介

本系統為一套 Client-Server 架構的 Agent 監控與管理平台，用於管理與監控分散在不同機器上的 Agent Client。系統採用現代化的雲原生架構設計，Server 端部署於 Kubernetes 叢集，Client 端為輕量級的 Agent 程式。

## 核心架構

```
┌─────────────────────────────────────────────────────────────┐
│                         Kubernetes                          │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                     Ingress                          │   │
│  │           (TLS Termination + Domain)                 │   │
│  └──────────────────┬──────────────────────────────────┘   │
│                     │                                        │
│  ┌──────────────────▼──────────────────────────────────┐   │
│  │              Server Pods (Python)                    │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐             │   │
│  │  │ Pod 1   │  │ Pod 2   │  │ Pod N   │             │   │
│  │  │ WebUI   │  │ WebUI   │  │ WebUI   │             │   │
│  │  │ REST API│  │ REST API│  │ REST API│             │   │
│  │  │ WebSocket│ │ WebSocket│ │ WebSocket│            │   │
│  │  └────┬────┘  └────┬────┘  └────┬────┘             │   │
│  └───────┼────────────┼────────────┼──────────────────┘   │
│          │            │            │                        │
│  ┌───────▼────────────▼────────────▼──────────────────┐   │
│  │              Redis (Presence)                        │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │           Database (PostgreSQL)                       │   │
│  │     (User, Client, Inventory, History)                │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                          │
                          │ WSS (WebSocket Secure)
                          │
         ┌────────────────┼────────────────┐
         │                │                │
    ┌────▼────┐      ┌────▼────┐     ┌────▼────┐
    │ Client  │      │ Client  │     │ Client  │
    │(Golang) │      │(Golang) │     │(Golang) │
    │ Agent   │      │ Agent   │     │ Agent   │
    └─────────┘      └─────────┘     └─────────┘
   Machine A        Machine B       Machine C
```

## 核心元件

### Server 端 (Python)
- **部署環境**: Kubernetes Pod
- **主要功能**:
  - Web UI 使用者介面
  - REST API 服務
  - WebSocket 長連線管理
  - Client 在線狀態管理
  - 設備資訊收集與儲存
  - 安裝檔案分發
  - **遠端終端機存取** (Remote Terminal Access)
- **對外服務**: 透過 Ingress 提供 HTTPS (TLS) 服務

### Client 端 (Golang)
- **部署環境**: 目標機器 (多種 OS/架構)
- **主要功能**:
  - WebSocket (wss) 長連線至 Server
  - 心跳機制 (Heartbeat: 15 秒)
  - 系統資訊收集 (Inventory)
  - 自動重連機制
  - **終端機命令執行** (Terminal Command Execution)
- **執行方式**: 
  - 前景執行 (run.sh)
  - 背景服務 (svc.sh + systemd)

### 共享元件
- **Redis**: 
  - Client 在線狀態 (Presence)
  - 多 Pod Session 共享
  - 心跳狀態快取
- **Database** (PostgreSQL):
  - 使用者資料
  - Client 註冊資訊
  - Inventory 資料 (最新 + 歷史)

## 連線機制

### WebSocket 長連線
- **協定**: WSS (WebSocket Secure over TLS)
- **連線方式**: Client 主動連接 Server
- **認證**: Token-based authentication
- **在線判定**: 必須維持 WebSocket 連線才算 online

### 心跳機制
- **Heartbeat Interval**: 15 秒
- **Offline Timeout**: 60 秒
- **機制**:
  - Client 每 15 秒發送心跳訊息
  - Server 更新 Redis 中的最後心跳時間
  - Server 定期檢查，超過 60 秒未收到心跳則標記為 offline

## 使用者隔離

每個使用者登入 Web UI 後：
- 只能看到自己安裝的 Clients
- 只能看到自己 Clients 的機器資訊
- 資料庫層面透過 user_id 進行資料隔離

## 安裝與部署

### Server 端
- Kubernetes Deployment + Service
- Ingress 設定 (domain + TLS)
- Redis Deployment
- Database (可使用 Kubernetes 內部或外部服務)

### Client 端
1. 使用者從 Web UI 下載 `install.sh`
2. 執行 `install.sh` 安裝 Agent (不使用 curl | sh pipe)
3. `install.sh` 會：
   - 下載對應 OS/ARCH 的 agent binary
   - 產生 `run.sh` (前景執行腳本)
   - 產生 `svc.sh` (systemd 服務管理腳本)
   - 註冊 Client 到 Server

## 資料收集

### Inventory 收集項目
- **基本資訊**: OS, CPU, Memory, Disk, IP
- **儲存策略**:
  - Latest: 最新的完整資訊
  - History: 歷史變更記錄
- **資料結構**: 
  - 通用欄位 (common fields)
  - Raw/Payload 擴充 (支援未來不同 OS/架構)

## 擴展性設計

### 多 Pod 支援
- 使用 Redis 作為分散式狀態儲存
- WebSocket 連線可分散到不同 Pod
- Session sticky 透過 Redis 實現

### 多平台支援
- Agent Binary 版本化管理
- 支援多種 OS (Linux, Windows, macOS)
- 支援多種架構 (amd64, arm64, etc.)

## 相關文件

- [Server 端設計](./server.md)
- [Client 端設計](./client.md)
- [WebSocket 協定](./protocol-websocket.md)
- [安裝分發設計](./install-distribution.md)
- [資料模型設計](./data-model.md)
- [Kubernetes 部署](./kubernetes.md)
- [安全性設計](./security.md)
- [遠端終端機存取](./remote-terminal.md)
