# 安裝分發設計 (Installation & Distribution Design)

## 安裝流程概覽

```
使用者登入 Web UI
        |
        v
下載 install.sh
        |
        v
執行 install.sh
        |
        ├─> 檢查系統環境 (OS, ARCH)
        ├─> 下載對應的 Agent Binary
        ├─> 產生設定檔 (config.yaml)
        ├─> 產生 run.sh (前景執行腳本)
        ├─> 產生 svc.sh (服務管理腳本)
        └─> 註冊 Client 到 Server
        |
        v
使用者選擇執行方式：
        ├─> ./run.sh (前景執行)
        └─> ./svc.sh install (安裝 systemd service)
```

## 檔案結構

### 安裝目錄結構
```
/opt/agent/              # 預設安裝目錄
├── bin/
│   └── agent           # Agent 執行檔
├── config/
│   └── config.yaml     # 設定檔
├── logs/
│   └── agent.log       # 日誌檔
├── scripts/
│   ├── run.sh          # 前景執行腳本
│   └── svc.sh          # 服務管理腳本
└── data/
    └── client_id.txt   # Client ID
```

## install.sh 設計

### 功能需求
1. **不使用** curl | sh pipe 安裝方式
2. 自動偵測 OS 和 ARCH
3. 下載對應的 Agent Binary
4. 產生設定檔和執行腳本
5. 註冊 Client 到 Server
6. 提供清楚的安裝進度和錯誤訊息

### 腳本範本

```bash
#!/bin/bash
# Agent Installation Script
# Version: 1.0.0
# Generated for user: {USER_ID}

set -e

# ==================== Configuration ====================
AGENT_VERSION="v1.0.0"
SERVER_URL="https://agent.example.com"
USER_TOKEN="{USER_TOKEN}"  # 由 Server 在產生腳本時嵌入
INSTALL_DIR="/opt/agent"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# ==================== Functions ====================

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

detect_os() {
    case "$(uname -s)" in
        Linux*)     OS="linux";;
        Darwin*)    OS="darwin";;
        MINGW*|MSYS*|CYGWIN*)    OS="windows";;
        *)          log_error "Unsupported OS: $(uname -s)";;
    esac
    echo "$OS"
}

detect_arch() {
    case "$(uname -m)" in
        x86_64)     ARCH="amd64";;
        aarch64|arm64)    ARCH="arm64";;
        i386|i686)  ARCH="386";;
        *)          log_error "Unsupported architecture: $(uname -m)";;
    esac
    echo "$ARCH"
}

check_requirements() {
    log_info "Checking requirements..."
    
    # Check if running as root or with sudo
    if [ "$EUID" -ne 0 ]; then 
        log_error "Please run as root or with sudo"
    fi
    
    # Check required commands
    for cmd in curl tar mkdir; do
        if ! command -v $cmd &> /dev/null; then
            log_error "Required command not found: $cmd"
        fi
    done
}

download_agent() {
    local os=$1
    local arch=$2
    local version=$3
    
    log_info "Downloading agent for ${os}/${arch} (${version})..."
    
    local binary_name="agent-${os}-${arch}"
    if [ "$os" = "windows" ]; then
        binary_name="${binary_name}.exe"
    fi
    
    local download_url="${SERVER_URL}/api/v1/download/agent/${os}/${arch}/${version}?token=${USER_TOKEN}"
    
    # Download binary
    if ! curl -L -f -o "${INSTALL_DIR}/bin/agent" "${download_url}"; then
        log_error "Failed to download agent binary"
    fi
    
    chmod +x "${INSTALL_DIR}/bin/agent"
    log_info "Agent binary downloaded successfully"
}

generate_client_id() {
    # Generate UUID for client_id
    if command -v uuidgen &> /dev/null; then
        CLIENT_ID=$(uuidgen | tr '[:upper:]' '[:lower:]')
    else
        CLIENT_ID="$(cat /proc/sys/kernel/random/uuid 2>/dev/null || echo $(date +%s%N | md5sum | cut -c1-32))"
    fi
    
    echo "$CLIENT_ID" > "${INSTALL_DIR}/data/client_id.txt"
    echo "$CLIENT_ID"
}

register_client() {
    local client_id=$1
    
    log_info "Registering client to server..."
    
    local hostname=$(hostname)
    local register_url="${SERVER_URL}/api/v1/clients/register"
    
    local response=$(curl -s -X POST "${register_url}" \
        -H "Authorization: Bearer ${USER_TOKEN}" \
        -H "Content-Type: application/json" \
        -d "{
            \"client_id\": \"${client_id}\",
            \"hostname\": \"${hostname}\",
            \"os\": \"${OS}\",
            \"arch\": \"${ARCH}\"
        }")
    
    if [ $? -ne 0 ]; then
        log_error "Failed to register client"
    fi
    
    # Extract client_token from response
    CLIENT_TOKEN=$(echo "$response" | grep -o '"token":"[^"]*' | cut -d'"' -f4)
    
    if [ -z "$CLIENT_TOKEN" ]; then
        log_error "Failed to get client token from server"
    fi
    
    log_info "Client registered successfully"
}

generate_config() {
    local client_id=$1
    local client_token=$2
    
    log_info "Generating configuration file..."
    
    cat > "${INSTALL_DIR}/config/config.yaml" <<EOF
# Agent Configuration
server_url: "${SERVER_URL##https://}"
client_id: "${client_id}"
client_token: "${client_token}"
ws_scheme: "wss"
ws_path: "/ws"

# Intervals (seconds)
heartbeat_interval: 15
reconnect_interval: 5
collect_interval: 60

# Logging
log_level: "info"
log_file: "${INSTALL_DIR}/logs/agent.log"
EOF
    
    log_info "Configuration file created"
}

generate_run_script() {
    log_info "Generating run.sh script..."
    
    cat > "${INSTALL_DIR}/scripts/run.sh" <<'EOF'
#!/bin/bash
# Agent Run Script (Foreground)

INSTALL_DIR="/opt/agent"
AGENT_BIN="${INSTALL_DIR}/bin/agent"
CONFIG_FILE="${INSTALL_DIR}/config/config.yaml"

# Check if agent binary exists
if [ ! -f "$AGENT_BIN" ]; then
    echo "Error: Agent binary not found at $AGENT_BIN"
    exit 1
fi

# Check if config file exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: Config file not found at $CONFIG_FILE"
    exit 1
fi

# Run agent
echo "Starting agent..."
"$AGENT_BIN" -config "$CONFIG_FILE"
EOF
    
    chmod +x "${INSTALL_DIR}/scripts/run.sh"
    log_info "run.sh created"
}

generate_svc_script() {
    log_info "Generating svc.sh script..."
    
    cat > "${INSTALL_DIR}/scripts/svc.sh" <<'EOF'
#!/bin/bash
# Agent Service Management Script

INSTALL_DIR="/opt/agent"
SERVICE_NAME="agent"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

case "$1" in
    install)
        echo "Installing ${SERVICE_NAME} service..."
        
        # Create systemd service file
        cat > "$SERVICE_FILE" <<SERVICEEOF
[Unit]
Description=Agent Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=${INSTALL_DIR}
ExecStart=${INSTALL_DIR}/bin/agent -config ${INSTALL_DIR}/config/config.yaml
Restart=always
RestartSec=5
StandardOutput=append:${INSTALL_DIR}/logs/agent.log
StandardError=append:${INSTALL_DIR}/logs/agent.log

[Install]
WantedBy=multi-user.target
SERVICEEOF
        
        # Reload systemd and enable service
        systemctl daemon-reload
        systemctl enable ${SERVICE_NAME}
        
        echo "${SERVICE_NAME} service installed successfully"
        echo "Use './svc.sh start' to start the service"
        ;;
        
    uninstall)
        echo "Uninstalling ${SERVICE_NAME} service..."
        systemctl stop ${SERVICE_NAME}
        systemctl disable ${SERVICE_NAME}
        rm -f "$SERVICE_FILE"
        systemctl daemon-reload
        echo "${SERVICE_NAME} service uninstalled"
        ;;
        
    start)
        echo "Starting ${SERVICE_NAME} service..."
        systemctl start ${SERVICE_NAME}
        systemctl status ${SERVICE_NAME}
        ;;
        
    stop)
        echo "Stopping ${SERVICE_NAME} service..."
        systemctl stop ${SERVICE_NAME}
        ;;
        
    restart)
        echo "Restarting ${SERVICE_NAME} service..."
        systemctl restart ${SERVICE_NAME}
        systemctl status ${SERVICE_NAME}
        ;;
        
    status)
        systemctl status ${SERVICE_NAME}
        ;;
        
    logs)
        tail -f ${INSTALL_DIR}/logs/agent.log
        ;;
        
    *)
        echo "Usage: $0 {install|uninstall|start|stop|restart|status|logs}"
        exit 1
        ;;
esac
EOF
    
    chmod +x "${INSTALL_DIR}/scripts/svc.sh"
    log_info "svc.sh created"
}

# ==================== Main Installation ====================

main() {
    echo "========================================"
    echo "  Agent Installation Script"
    echo "  Version: ${AGENT_VERSION}"
    echo "========================================"
    echo ""
    
    # Check requirements
    check_requirements
    
    # Detect system
    OS=$(detect_os)
    ARCH=$(detect_arch)
    log_info "Detected system: ${OS}/${ARCH}"
    
    # Create directories
    log_info "Creating installation directories..."
    mkdir -p "${INSTALL_DIR}"/{bin,config,logs,scripts,data}
    
    # Download agent binary
    download_agent "$OS" "$ARCH" "$AGENT_VERSION"
    
    # Generate client ID
    CLIENT_ID=$(generate_client_id)
    log_info "Generated Client ID: ${CLIENT_ID}"
    
    # Register client to server
    register_client "$CLIENT_ID"
    
    # Generate configuration
    generate_config "$CLIENT_ID" "$CLIENT_TOKEN"
    
    # Generate run scripts
    generate_run_script
    generate_svc_script
    
    echo ""
    echo "========================================"
    echo "  Installation Complete!"
    echo "========================================"
    echo ""
    echo "Installation directory: ${INSTALL_DIR}"
    echo "Client ID: ${CLIENT_ID}"
    echo ""
    echo "Next steps:"
    echo "  1. Run in foreground:"
    echo "     cd ${INSTALL_DIR}/scripts && ./run.sh"
    echo ""
    echo "  2. Or install as systemd service:"
    echo "     cd ${INSTALL_DIR}/scripts && ./svc.sh install"
    echo "     ./svc.sh start"
    echo ""
}

main "$@"
```

## run.sh 設計

### 功能
- 前景執行 Agent
- 輸出日誌到終端
- 支援 Ctrl+C 優雅關閉

### 使用方式
```bash
cd /opt/agent/scripts
./run.sh
```

## svc.sh 設計

### 功能
- 安裝/卸載 systemd service
- 啟動/停止/重啟服務
- 查看服務狀態
- 查看日誌

### 命令介面
```bash
./svc.sh install    # 安裝服務
./svc.sh uninstall  # 卸載服務
./svc.sh start      # 啟動服務
./svc.sh stop       # 停止服務
./svc.sh restart    # 重啟服務
./svc.sh status     # 查看狀態
./svc.sh logs       # 查看日誌
```

### systemd Service 設定
```ini
[Unit]
Description=Agent Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/agent
ExecStart=/opt/agent/bin/agent -config /opt/agent/config/config.yaml
Restart=always
RestartSec=5
StandardOutput=append:/opt/agent/logs/agent.log
StandardError=append:/opt/agent/logs/agent.log

[Install]
WantedBy=multi-user.target
```

## Binary 版本管理

### 檔案命名規則
```
agent-{os}-{arch}-{version}[.exe]

範例:
- agent-linux-amd64-v1.0.0
- agent-darwin-arm64-v1.0.0
- agent-windows-amd64-v1.0.0.exe
```

### 儲存目錄結構
```
/storage/binaries/
├── v1.0.0/
│   ├── agent-linux-amd64
│   ├── agent-linux-arm64
│   ├── agent-darwin-amd64
│   ├── agent-darwin-arm64
│   ├── agent-windows-amd64.exe
│   └── checksums.txt
├── v1.0.1/
│   └── ...
└── latest -> v1.0.1  # 符號連結
```

### Checksums 檔案
```
# checksums.txt
sha256:1234567890abcdef... agent-linux-amd64
sha256:abcdef1234567890... agent-linux-arm64
sha256:567890abcdef1234... agent-darwin-amd64
sha256:890abcdef1234567... agent-darwin-arm64
sha256:def1234567890abc... agent-windows-amd64.exe
```

## 安裝腳本產生 (Server 端)

### API Endpoint
```python
@router.get("/download/install.sh")
async def generate_install_script(
    user: User = Depends(get_current_user),
    version: str = "latest"
):
    """產生個人化的安裝腳本"""
    
    # 產生使用者專屬的 token
    user_token = generate_user_token(user.id)
    
    # 讀取腳本範本
    template = read_template("install.sh.template")
    
    # 替換變數
    script = template.format(
        AGENT_VERSION=version,
        SERVER_URL=settings.SERVER_URL,
        USER_TOKEN=user_token
    )
    
    return Response(
        content=script,
        media_type="text/x-shellscript",
        headers={
            "Content-Disposition": "attachment; filename=install.sh"
        }
    )
```

## Web UI 下載頁面

### 頁面元素
1. **版本選擇**: 下拉選單選擇 Agent 版本
2. **安裝說明**: 顯示安裝步驟
3. **下載按鈕**: 
   - 下載 install.sh
   - 顯示 curl 命令 (但不建議使用 pipe 執行)
4. **驗證說明**: 如何驗證腳本內容

### 範例 HTML
```html
<div class="download-section">
    <h2>下載 Agent 安裝腳本</h2>
    
    <div class="version-selector">
        <label>選擇版本:</label>
        <select id="version">
            <option value="latest">Latest (v1.0.0)</option>
            <option value="v1.0.0">v1.0.0</option>
        </select>
    </div>
    
    <div class="download-button">
        <button onclick="downloadInstallScript()">
            下載 install.sh
        </button>
    </div>
    
    <div class="installation-steps">
        <h3>安裝步驟:</h3>
        <ol>
            <li>下載 install.sh 到目標機器</li>
            <li>檢查腳本內容 (建議): <code>cat install.sh</code></li>
            <li>添加執行權限: <code>chmod +x install.sh</code></li>
            <li>以 root 執行安裝: <code>sudo ./install.sh</code></li>
        </ol>
    </div>
    
    <div class="warning">
        <strong>注意事項:</strong>
        <ul>
            <li>請勿使用 <code>curl | sh</code> 方式安裝</li>
            <li>建議先檢查腳本內容再執行</li>
            <li>需要 root 權限執行安裝</li>
        </ul>
    </div>
</div>
```

## 升級機制

### Agent 自動升級流程
1. Server 推送升級命令
2. Agent 下載新版本 binary
3. 驗證 checksum
4. 替換舊版本 binary
5. 重啟 Agent

### 手動升級
```bash
# 下載新版本安裝腳本
wget https://agent.example.com/download/install.sh

# 執行安裝 (會自動偵測並升級)
sudo ./install.sh
```

## 卸載腳本

### uninstall.sh
```bash
#!/bin/bash
# Agent Uninstallation Script

INSTALL_DIR="/opt/agent"
SERVICE_NAME="agent"

echo "Uninstalling agent..."

# Stop and remove service
if systemctl is-active --quiet ${SERVICE_NAME}; then
    systemctl stop ${SERVICE_NAME}
    systemctl disable ${SERVICE_NAME}
    rm -f /etc/systemd/system/${SERVICE_NAME}.service
    systemctl daemon-reload
    echo "Service removed"
fi

# Remove installation directory
if [ -d "$INSTALL_DIR" ]; then
    rm -rf "$INSTALL_DIR"
    echo "Installation directory removed"
fi

echo "Uninstallation complete"
```

## 故障排除

### 常見問題

1. **無法下載 binary**
   - 檢查網路連線
   - 確認 token 是否有效
   - 檢查 Server URL 是否正確

2. **註冊失敗**
   - 確認 Server 是否可達
   - 檢查 token 權限
   - 查看 Server 日誌

3. **服務無法啟動**
   - 檢查設定檔格式
   - 查看日誌檔
   - 確認 binary 有執行權限

### 日誌位置
- 安裝日誌: 終端輸出
- Agent 日誌: `/opt/agent/logs/agent.log`
- systemd 日誌: `journalctl -u agent`
