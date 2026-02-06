# Client 端設計 (Client-Side Design)

## 技術架構

### 程式語言與套件
- **語言**: Golang 1.20+
- **WebSocket**: gorilla/websocket
- **系統資訊**: gopsutil
- **設定管理**: viper
- **日誌**: logrus 或 zap

### 編譯與部署
- **編譯**: 交叉編譯多平台 binary
- **版本管理**: 語意化版本 (Semantic Versioning)
- **檔案命名**: `agent-{OS}-{ARCH}-{VERSION}`

### 支援平台
```
OS:
- linux (amd64, arm64, 386)
- darwin (amd64, arm64)
- windows (amd64, 386)

範例:
- agent-linux-amd64-v1.0.0
- agent-darwin-arm64-v1.0.0
- agent-windows-amd64-v1.0.0.exe
```

## 核心模組

### 1. 主程式架構
```
cmd/agent/
├── main.go              # 程式進入點
└── version.go           # 版本資訊

internal/agent/
├── config/
│   └── config.go        # 設定管理
├── websocket/
│   ├── client.go        # WebSocket Client
│   └── handler.go       # 訊息處理
├── heartbeat/
│   └── heartbeat.go     # 心跳機制
├── inventory/
│   ├── collector.go     # 資訊收集
│   ├── os.go           # OS 資訊
│   ├── cpu.go          # CPU 資訊
│   ├── memory.go       # 記憶體資訊
│   ├── disk.go         # 磁碟資訊
│   └── network.go      # 網路資訊
├── terminal/
│   └── executor.go      # 終端機執行器
└── runner/
    └── runner.go        # 執行管理
```

### 2. 設定管理
```go
// config/config.go
package config

type Config struct {
    // Server 連線資訊
    ServerURL      string `mapstructure:"server_url"`
    ClientID       string `mapstructure:"client_id"`
    ClientToken    string `mapstructure:"client_token"`
    
    // WebSocket 設定
    WSScheme       string `mapstructure:"ws_scheme"` // wss
    WSPath         string `mapstructure:"ws_path"`   // /ws
    
    // 心跳設定
    HeartbeatInterval int `mapstructure:"heartbeat_interval"` // 15 seconds
    ReconnectInterval int `mapstructure:"reconnect_interval"` // 5 seconds
    
    // Inventory 設定
    CollectInterval   int `mapstructure:"collect_interval"`   // 60 seconds
    
    // 日誌設定
    LogLevel       string `mapstructure:"log_level"`
    LogFile        string `mapstructure:"log_file"`
}

func LoadConfig(configPath string) (*Config, error) {
    // 載入設定檔
    viper.SetConfigFile(configPath)
    viper.SetConfigType("yaml")
    
    // 設定預設值
    viper.SetDefault("heartbeat_interval", 15)
    viper.SetDefault("reconnect_interval", 5)
    viper.SetDefault("collect_interval", 60)
    viper.SetDefault("log_level", "info")
    
    if err := viper.ReadInConfig(); err != nil {
        return nil, err
    }
    
    var config Config
    if err := viper.Unmarshal(&config); err != nil {
        return nil, err
    }
    
    return &config, nil
}
```

**設定檔範例 (config.yaml)**:
```yaml
server_url: "agent.myelintek.com"
client_id: "client-uuid-xxxx"
client_token: "token-xxxx-xxxx"
ws_scheme: "wss"
ws_path: "/ws"
heartbeat_interval: 15
reconnect_interval: 5
collect_interval: 60
log_level: "info"
log_file: "/var/log/agent/agent.log"
```

### 3. WebSocket Client
```go
// websocket/client.go
package websocket

import (
    "github.com/gorilla/websocket"
    "time"
)

type WSClient struct {
    config     *config.Config
    conn       *websocket.Conn
    connected  bool
    stopChan   chan struct{}
    logger     *logrus.Logger
}

func NewWSClient(cfg *config.Config) *WSClient {
    return &WSClient{
        config:    cfg,
        connected: false,
        stopChan:  make(chan struct{}),
        logger:    logrus.New(),
    }
}

func (c *WSClient) Connect() error {
    // 建立 WebSocket 連線
    url := fmt.Sprintf("%s://%s%s/%s?token=%s",
        c.config.WSScheme,
        c.config.ServerURL,
        c.config.WSPath,
        c.config.ClientID,
        c.config.ClientToken,
    )
    
    dialer := websocket.Dialer{
        HandshakeTimeout: 10 * time.Second,
    }
    
    conn, _, err := dialer.Dial(url, nil)
    if err != nil {
        return fmt.Errorf("failed to connect: %w", err)
    }
    
    c.conn = conn
    c.connected = true
    c.logger.Info("WebSocket connected")
    
    // 啟動接收訊息的 goroutine
    go c.readMessages()
    
    return nil
}

func (c *WSClient) Disconnect() {
    if c.conn != nil {
        c.conn.Close()
        c.connected = false
        c.logger.Info("WebSocket disconnected")
    }
}

func (c *WSClient) SendMessage(msgType string, data interface{}) error {
    if !c.connected {
        return fmt.Errorf("not connected")
    }
    
    message := Message{
        Type:      msgType,
        Data:      data,
        Timestamp: time.Now().Unix(),
    }
    
    return c.conn.WriteJSON(message)
}

func (c *WSClient) readMessages() {
    defer c.Disconnect()
    
    for {
        select {
        case <-c.stopChan:
            return
        default:
            var msg Message
            err := c.conn.ReadJSON(&msg)
            if err != nil {
                c.logger.Errorf("Read error: %v", err)
                return
            }
            
            // 處理接收到的訊息
            c.handleMessage(&msg)
        }
    }
}

func (c *WSClient) handleMessage(msg *Message) {
    switch msg.Type {
    case "ping":
        // 回應 pong
        c.SendMessage("pong", nil)
    case "command":
        // 處理 Server 下發的命令
        c.handleCommand(msg.Data)
    case "config_update":
        // 更新設定
        c.handleConfigUpdate(msg.Data)
    default:
        c.logger.Warnf("Unknown message type: %s", msg.Type)
    }
}
```

### 4. 心跳機制
```go
// heartbeat/heartbeat.go
package heartbeat

import (
    "time"
)

type Heartbeat struct {
    wsClient  *websocket.WSClient
    interval  time.Duration
    stopChan  chan struct{}
    logger    *logrus.Logger
}

func NewHeartbeat(wsClient *websocket.WSClient, interval int) *Heartbeat {
    return &Heartbeat{
        wsClient: wsClient,
        interval: time.Duration(interval) * time.Second,
        stopChan: make(chan struct{}),
        logger:   logrus.New(),
    }
}

func (h *Heartbeat) Start() {
    ticker := time.NewTicker(h.interval)
    defer ticker.Stop()
    
    h.logger.Infof("Heartbeat started (interval: %v)", h.interval)
    
    for {
        select {
        case <-ticker.C:
            // 發送心跳
            h.sendHeartbeat()
        case <-h.stopChan:
            h.logger.Info("Heartbeat stopped")
            return
        }
    }
}

func (h *Heartbeat) Stop() {
    close(h.stopChan)
}

func (h *Heartbeat) sendHeartbeat() {
    heartbeatData := map[string]interface{}{
        "timestamp": time.Now().Unix(),
        "status":    "alive",
    }
    
    err := h.wsClient.SendMessage("heartbeat", heartbeatData)
    if err != nil {
        h.logger.Errorf("Failed to send heartbeat: %v", err)
    } else {
        h.logger.Debug("Heartbeat sent")
    }
}
```

### 5. Inventory 收集器
```go
// inventory/collector.go
package inventory

import (
    "github.com/shirou/gopsutil/v3/cpu"
    "github.com/shirou/gopsutil/v3/mem"
    "github.com/shirou/gopsutil/v3/disk"
    "github.com/shirou/gopsutil/v3/host"
    "github.com/shirou/gopsutil/v3/net"
)

type Inventory struct {
    // 通用欄位
    Hostname      string                 `json:"hostname"`
    OS            string                 `json:"os"`
    Platform      string                 `json:"platform"`
    Arch          string                 `json:"arch"`
    CollectedAt   int64                  `json:"collected_at"`
    
    // CPU
    CPUCount      int                    `json:"cpu_count"`
    CPUModel      string                 `json:"cpu_model"`
    
    // Memory
    MemoryTotal   uint64                 `json:"memory_total"`
    MemoryUsed    uint64                 `json:"memory_used"`
    
    // Disk
    DiskTotal     uint64                 `json:"disk_total"`
    DiskUsed      uint64                 `json:"disk_used"`
    
    // Network
    IPAddresses   []string               `json:"ip_addresses"`
    MACAddresses  []string               `json:"mac_addresses"`
    
    // 擴充欄位 (Raw Data)
    RawData       map[string]interface{} `json:"raw_data"`
}

type Collector struct {
    logger *logrus.Logger
}

func NewCollector() *Collector {
    return &Collector{
        logger: logrus.New(),
    }
}

func (c *Collector) Collect() (*Inventory, error) {
    inv := &Inventory{
        CollectedAt: time.Now().Unix(),
        RawData:     make(map[string]interface{}),
    }
    
    // 收集 Host 資訊
    if err := c.collectHostInfo(inv); err != nil {
        c.logger.Errorf("Failed to collect host info: %v", err)
    }
    
    // 收集 CPU 資訊
    if err := c.collectCPUInfo(inv); err != nil {
        c.logger.Errorf("Failed to collect CPU info: %v", err)
    }
    
    // 收集 Memory 資訊
    if err := c.collectMemoryInfo(inv); err != nil {
        c.logger.Errorf("Failed to collect memory info: %v", err)
    }
    
    // 收集 Disk 資訊
    if err := c.collectDiskInfo(inv); err != nil {
        c.logger.Errorf("Failed to collect disk info: %v", err)
    }
    
    // 收集 Network 資訊
    if err := c.collectNetworkInfo(inv); err != nil {
        c.logger.Errorf("Failed to collect network info: %v", err)
    }
    
    return inv, nil
}

func (c *Collector) collectHostInfo(inv *Inventory) error {
    hostInfo, err := host.Info()
    if err != nil {
        return err
    }
    
    inv.Hostname = hostInfo.Hostname
    inv.OS = hostInfo.OS
    inv.Platform = hostInfo.Platform
    inv.Arch = hostInfo.KernelArch
    
    // 儲存完整資訊到 RawData
    inv.RawData["host"] = hostInfo
    
    return nil
}

func (c *Collector) collectCPUInfo(inv *Inventory) error {
    cpuInfo, err := cpu.Info()
    if err != nil {
        return err
    }
    
    inv.CPUCount = len(cpuInfo)
    if len(cpuInfo) > 0 {
        inv.CPUModel = cpuInfo[0].ModelName
    }
    
    inv.RawData["cpu"] = cpuInfo
    
    return nil
}

func (c *Collector) collectMemoryInfo(inv *Inventory) error {
    memInfo, err := mem.VirtualMemory()
    if err != nil {
        return err
    }
    
    inv.MemoryTotal = memInfo.Total
    inv.MemoryUsed = memInfo.Used
    
    inv.RawData["memory"] = memInfo
    
    return nil
}

func (c *Collector) collectDiskInfo(inv *Inventory) error {
    parts, err := disk.Partitions(false)
    if err != nil {
        return err
    }
    
    var totalDisk, usedDisk uint64
    diskDetails := []map[string]interface{}{}
    
    for _, part := range parts {
        usage, err := disk.Usage(part.Mountpoint)
        if err != nil {
            continue
        }
        
        totalDisk += usage.Total
        usedDisk += usage.Used
        
        diskDetails = append(diskDetails, map[string]interface{}{
            "device":     part.Device,
            "mountpoint": part.Mountpoint,
            "fstype":     part.Fstype,
            "total":      usage.Total,
            "used":       usage.Used,
        })
    }
    
    inv.DiskTotal = totalDisk
    inv.DiskUsed = usedDisk
    inv.RawData["disks"] = diskDetails
    
    return nil
}

func (c *Collector) collectNetworkInfo(inv *Inventory) error {
    interfaces, err := net.Interfaces()
    if err != nil {
        return err
    }
    
    ipAddrs := []string{}
    macAddrs := []string{}
    
    for _, iface := range interfaces {
        if len(iface.Addrs) > 0 {
            for _, addr := range iface.Addrs {
                ipAddrs = append(ipAddrs, addr.Addr)
            }
        }
        if iface.HardwareAddr != "" {
            macAddrs = append(macAddrs, iface.HardwareAddr)
        }
    }
    
    inv.IPAddresses = ipAddrs
    inv.MACAddresses = macAddrs
    inv.RawData["network"] = interfaces
    
    return nil
}
```

### 6. 主執行邏輯
```go
// cmd/agent/main.go
package main

import (
    "flag"
    "os"
    "os/signal"
    "syscall"
    "time"
)

func main() {
    configPath := flag.String("config", "/etc/agent/config.yaml", "Config file path")
    flag.Parse()
    
    // 載入設定
    cfg, err := config.LoadConfig(*configPath)
    if err != nil {
        log.Fatalf("Failed to load config: %v", err)
    }
    
    // 建立 WebSocket Client
    wsClient := websocket.NewWSClient(cfg)
    
    // 建立 Inventory Collector
    collector := inventory.NewCollector()
    
    // 建立 Heartbeat
    hb := heartbeat.NewHeartbeat(wsClient, cfg.HeartbeatInterval)
    
    // 連線到 Server (支援重連)
    for {
        err := wsClient.Connect()
        if err == nil {
            break
        }
        log.Errorf("Failed to connect: %v, retrying in %d seconds...", 
            err, cfg.ReconnectInterval)
        time.Sleep(time.Duration(cfg.ReconnectInterval) * time.Second)
    }
    
    // 啟動 Heartbeat
    go hb.Start()
    
    // 啟動 Inventory 收集
    go func() {
        ticker := time.NewTicker(time.Duration(cfg.CollectInterval) * time.Second)
        defer ticker.Stop()
        
        for range ticker.C {
            inv, err := collector.Collect()
            if err != nil {
                log.Errorf("Failed to collect inventory: %v", err)
                continue
            }
            
            // 發送 Inventory 到 Server
            wsClient.SendMessage("inventory", inv)
        }
    }()
    
    // 等待中斷信號
    sigChan := make(chan os.Signal, 1)
    signal.Notify(sigChan, os.Interrupt, syscall.SIGTERM)
    <-sigChan
    
    // 優雅關閉
    log.Info("Shutting down...")
    hb.Stop()
    wsClient.Disconnect()
    log.Info("Goodbye!")
}
```

## 自動重連機制

```go
// 在 WebSocket Client 中實作重連邏輯
func (c *WSClient) RunWithReconnect() {
    for {
        // 嘗試連線
        err := c.Connect()
        if err != nil {
            c.logger.Errorf("Connection failed: %v", err)
            time.Sleep(time.Duration(c.config.ReconnectInterval) * time.Second)
            continue
        }
        
        // 連線成功，等待斷線
        c.waitForDisconnect()
        
        // 斷線後等待一段時間再重連
        c.logger.Info("Reconnecting...")
        time.Sleep(time.Duration(c.config.ReconnectInterval) * time.Second)
    }
}
```

## 終端機執行器

### Terminal Executor 模組

```go
// internal/agent/terminal/executor.go
package terminal

import (
    "os/exec"
    "github.com/creack/pty"
)

type TerminalExecutor struct {
    sessions map[string]*TerminalSession
    wsClient *websocket.WSClient
}

type TerminalSession struct {
    SessionID string
    PTY       *os.File
    Cmd       *exec.Cmd
    Rows      int
    Cols      int
}

func (te *TerminalExecutor) HandleTerminalCommand(command map[string]interface{}) error {
    sessionID := command["session_id"].(string)
    cmd := command["command"].(string)
    
    switch cmd {
    case "init":
        return te.initTerminal(sessionID, params)
    case "input":
        return te.handleInput(sessionID, params)
    case "resize":
        return te.resizeTerminal(sessionID, params)
    case "close":
        return te.closeTerminal(sessionID)
    }
    return nil
}

func (te *TerminalExecutor) initTerminal(sessionID string, params map[string]interface{}) error {
    // 建立 PTY (Pseudo-Terminal)
    cmd := exec.Command(shell)
    ptmx, err := pty.Start(cmd)
    if err != nil {
        return err
    }
    
    // 啟動 goroutine 讀取輸出
    go te.readOutput(sessionID, ptmx)
    
    return nil
}
```

**功能**:
- 建立和管理 PTY (Pseudo-Terminal)
- 處理終端機輸入/輸出
- 支援終端機大小調整
- 自動清理終端機 Session

**支援的 Shell**:
- Linux/macOS: `/bin/bash`, `/bin/sh`, `/bin/zsh`
- Windows: `cmd.exe`, `powershell.exe`

**詳細設計**: 參考 [遠端終端機存取設計](./remote-terminal.md)

## 編譯與部署

### 交叉編譯腳本
```bash
#!/bin/bash
# build.sh

VERSION="v1.0.0"
PLATFORMS=(
    "linux/amd64"
    "linux/arm64"
    "linux/386"
    "darwin/amd64"
    "darwin/arm64"
    "windows/amd64"
    "windows/386"
)

for PLATFORM in "${PLATFORMS[@]}"; do
    IFS='/' read -ra PARTS <<< "$PLATFORM"
    GOOS="${PARTS[0]}"
    GOARCH="${PARTS[1]}"
    
    OUTPUT="agent-${GOOS}-${GOARCH}-${VERSION}"
    if [ "$GOOS" = "windows" ]; then
        OUTPUT="${OUTPUT}.exe"
    fi
    
    echo "Building for ${GOOS}/${GOARCH}..."
    GOOS=$GOOS GOARCH=$GOARCH go build -o "dist/${OUTPUT}" cmd/agent/main.go
done

echo "Build complete!"
```

## 日誌管理

```go
// 設定日誌輸出
func setupLogger(cfg *config.Config) *logrus.Logger {
    logger := logrus.New()
    
    // 設定日誌級別
    level, err := logrus.ParseLevel(cfg.LogLevel)
    if err != nil {
        level = logrus.InfoLevel
    }
    logger.SetLevel(level)
    
    // 設定輸出格式
    logger.SetFormatter(&logrus.JSONFormatter{
        TimestampFormat: time.RFC3339,
    })
    
    // 設定輸出目標
    if cfg.LogFile != "" {
        file, err := os.OpenFile(cfg.LogFile, 
            os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0666)
        if err == nil {
            logger.SetOutput(file)
        }
    }
    
    return logger
}
```

## 效能與資源使用

### 資源使用目標
- CPU 使用率: < 5% (idle 狀態)
- 記憶體使用: < 50 MB
- 網路頻寬: < 10 KB/s (心跳 + 定期回報)

### 優化建議
- 使用 goroutine 處理並發
- Inventory 收集使用快取，避免重複收集
- WebSocket 訊息使用壓縮 (可選)
- 日誌輪轉避免檔案過大
