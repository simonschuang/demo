# 安裝分發設計 (Installation & Distribution Design)

## 安裝流程概覽

```
使用者登入 Web UI
        |
        v
下載 install.sh
        |
        v
執行 install.sh (帶入認證 token)
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
2. 從 Web UI 下載 install.sh，並在執行時提供認證 token
3. 自動偵測 OS 和 ARCH
4. 下載對應的 Agent Binary
5. 產生設定檔和執行腳本
6. 註冊 Client 到 Server
7. 提供清楚的安裝進度和錯誤訊息

### 腳本設計要點

install.sh 腳本應包含以下主要功能：

- **認證機制**: 執行時需要帶入認證 token 作為參數
- **系統偵測**: 自動偵測作業系統和架構
- **Binary 下載**: 從 Server 下載對應版本的 Agent
- **設定產生**: 自動產生 config.yaml 設定檔
- **腳本產生**: 產生 run.sh 和 svc.sh 管理腳本
- **Client 註冊**: 向 Server 註冊並取得 client token
- **錯誤處理**: 完整的錯誤檢查和使用者提示

### 執行範例

```bash
# 從 Web UI 下載 install.sh
wget https://agent.myelintek.com/download/install.sh

# 執行安裝，帶入從 Web UI 取得的認證 token
sudo bash install.sh --token YOUR_AUTH_TOKEN
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
wget https://agent.myelintek.com/download/install.sh

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
