# 安裝分發設計 (Installation & Distribution Design)

## 安裝流程概覽

```
使用者登入 Web UI
        |
        v
選擇作業系統，下載 install-{os}-{arch}-{version}.zip
        |
        v
解壓縮 zip 檔案
        |
        ├── agent           # Agent 執行檔
        ├── config.yaml     # 設定檔範本
        ├── install.sh      # 首次安裝腳本
        ├── run.sh          # 前景執行腳本
        └── svc.sh          # 服務管理腳本
        |
        v
首次安裝執行 install.sh --token <從 Web UI 取得>
        |
        ├─> 向 Server 註冊 Client
        ├─> 取得 client_id 和 client_token
        └─> 自動更新 config.yaml
        |
        v
使用者選擇執行方式：
        ├─> ./run.sh (前景執行)
        └─> ./svc.sh install (安裝 systemd service)
```

## 檔案結構

### 下載 ZIP 檔案內容
```
install-linux-amd64-v1.0.0.zip
├── agent               # Agent 執行檔
├── config.yaml         # 設定檔範本 (需執行 install.sh 設定)
├── install.sh          # 首次安裝腳本
├── run.sh              # 前景執行腳本
└── svc.sh              # 服務管理腳本
```

### 安裝後目錄結構
```
/opt/agent/              # 預設安裝目錄 (由 svc.sh install 建立)
├── bin/
│   └── agent           # Agent 執行檔
├── config/
│   └── config.yaml     # 設定檔
├── logs/
│   └── agent.log       # 日誌檔
└── scripts/
    ├── run.sh          # 前景執行腳本
    └── svc.sh          # 服務管理腳本
```

## install.sh 設計

### 功能需求
1. 首次安裝時執行，使用 Web UI 提供的認證 token
2. 向 Server 註冊 Client，取得 client_id 和 client_token
3. 自動更新 config.yaml 中的認證資訊
4. 提供清楚的安裝進度和錯誤訊息

### 腳本設計要點

install.sh 腳本應包含以下主要功能：

- **認證機制**: 執行時需要帶入認證 token 作為參數
- **Client 註冊**: 向 Server 註冊並取得 client_id 和 client_token
- **設定更新**: 自動更新 config.yaml 中的認證資訊
- **錯誤處理**: 完整的錯誤檢查和使用者提示

### 執行範例

```bash
# 從 Web UI 下載對應作業系統的 zip 檔案
# 例如: install-linux-amd64-v1.0.0.zip

# 解壓縮
unzip install-linux-amd64-v1.0.0.zip
cd install-linux-amd64-v1.0.0

# 首次安裝，帶入從 Web UI 取得的認證 token
sudo ./install.sh --token YOUR_AUTH_TOKEN

# 安裝完成後，選擇執行方式：
# 方式一：前景執行
./run.sh

# 方式二：安裝為系統服務 (背景執行)
sudo ./svc.sh install
sudo ./svc.sh start
```


## run.sh 設計

### 功能
- 前景執行 Agent
- 輸出日誌到終端
- 支援 Ctrl+C 優雅關閉

### 使用方式
```bash
# 在解壓縮目錄中執行
./run.sh

# 或安裝後在安裝目錄中執行
cd /opt/agent/scripts
./run.sh
```

## svc.sh 設計

### 功能
- 安裝/卸載 systemd service (會複製檔案到 /opt/agent)
- 啟動/停止/重啟服務
- 查看服務狀態
- 查看日誌

### 命令介面
```bash
./svc.sh install    # 安裝服務 (複製檔案到 /opt/agent 並註冊 systemd)
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

### ZIP 檔案命名規則
```
install-{os}-{arch}-{version}.zip

範例:
- install-linux-amd64-v1.0.0.zip
- install-linux-arm64-v1.0.0.zip
- install-darwin-amd64-v1.0.0.zip
- install-darwin-arm64-v1.0.0.zip
- install-windows-amd64-v1.0.0.zip
```

### 儲存目錄結構
```
/storage/releases/
├── v1.0.0/
│   ├── install-linux-amd64-v1.0.0.zip
│   ├── install-linux-arm64-v1.0.0.zip
│   ├── install-darwin-amd64-v1.0.0.zip
│   ├── install-darwin-arm64-v1.0.0.zip
│   ├── install-windows-amd64-v1.0.0.zip
│   └── checksums.txt
├── v1.0.1/
│   └── ...
└── latest -> v1.0.1  # 符號連結
```

### Checksums 檔案
```
# checksums.txt
sha256:1234567890abcdef... install-linux-amd64-v1.0.0.zip
sha256:abcdef1234567890... install-linux-arm64-v1.0.0.zip
sha256:567890abcdef1234... install-darwin-amd64-v1.0.0.zip
sha256:890abcdef1234567... install-darwin-arm64-v1.0.0.zip
sha256:def1234567890abc... install-windows-amd64-v1.0.0.zip
```

## 下載 API (Server 端)

### API Endpoints

```python
@router.get("/download/releases")
async def list_releases():
    """列出所有可用版本"""
    return {
        "latest": "v1.0.0",
        "versions": ["v1.0.0", "v0.9.0"]
    }

@router.get("/download/{version}/{filename}")
async def download_release(
    version: str,
    filename: str,
    user: User = Depends(get_current_user)
):
    """下載指定版本的 ZIP 檔案
    
    範例: GET /download/v1.0.0/install-linux-amd64-v1.0.0.zip
    """
    file_path = f"/storage/releases/{version}/{filename}"
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/zip"
    )

@router.post("/download/register")
async def register_client(
    token: str,
    hostname: Optional[str] = None,
    user: User = Depends(verify_install_token)
):
    """install.sh 呼叫此 API 註冊 Client
    
    回傳 client_id 和 client_token 供寫入 config.yaml
    """
    client = await create_client(user_id=user.id, hostname=hostname)
    
    return {
        "client_id": client.id,
        "client_token": client.client_token,
        "server_url": settings.SERVER_URL
    }
```

## Web UI 下載頁面

### 頁面元素
1. **版本選擇**: 下拉選單選擇 Agent 版本
2. **作業系統選擇**: 自動偵測或手動選擇 OS/ARCH
3. **下載按鈕**: 下載對應的 ZIP 檔案
4. **認證 Token**: 顯示用於 install.sh 的 token
5. **安裝說明**: 顯示安裝步驟

### 範例 HTML
```html
<div class="download-section">
    <h2>下載 Agent 安裝包</h2>
    
    <div class="version-selector">
        <label>選擇版本:</label>
        <select id="version">
            <option value="v1.0.0">Latest (v1.0.0)</option>
            <option value="v0.9.0">v0.9.0</option>
        </select>
    </div>
    
    <div class="os-selector">
        <label>選擇作業系統:</label>
        <select id="os-arch">
            <option value="linux-amd64">Linux (x86_64)</option>
            <option value="linux-arm64">Linux (ARM64)</option>
            <option value="darwin-amd64">macOS (Intel)</option>
            <option value="darwin-arm64">macOS (Apple Silicon)</option>
            <option value="windows-amd64">Windows (x86_64)</option>
        </select>
    </div>
    
    <div class="download-button">
        <button onclick="downloadInstallZip()">
            📦 下載 install.zip
        </button>
    </div>
    
    <div class="auth-token">
        <h3>認證 Token:</h3>
        <code id="install-token">YOUR_AUTH_TOKEN_HERE</code>
        <button onclick="copyToken()">📋 複製</button>
        <p class="token-note">⚠️ 此 Token 用於 install.sh，請妥善保管</p>
    </div>
    
    <div class="installation-steps">
        <h3>安裝步驟:</h3>
        <ol>
            <li>下載對應作業系統的 ZIP 檔案</li>
            <li>解壓縮: <code>unzip install-linux-amd64-v1.0.0.zip</code></li>
            <li>進入目錄: <code>cd install-linux-amd64-v1.0.0</code></li>
            <li>首次安裝: <code>sudo ./install.sh --token YOUR_TOKEN</code></li>
            <li>選擇執行方式:
                <ul>
                    <li>前景執行: <code>./run.sh</code></li>
                    <li>背景服務: <code>sudo ./svc.sh install && sudo ./svc.sh start</code></li>
                </ul>
            </li>
        </ol>
    </div>
    
    <div class="file-contents">
        <h3>ZIP 檔案內容:</h3>
        <ul>
            <li><code>agent</code> - Agent 執行檔</li>
            <li><code>config.yaml</code> - 設定檔範本</li>
            <li><code>install.sh</code> - 首次安裝腳本 (設定認證)</li>
            <li><code>run.sh</code> - 前景執行腳本</li>
            <li><code>svc.sh</code> - 服務管理腳本</li>
        </ul>
    </div>
</div>
```

## 升級機制

### 手動升級流程
1. 從 Web UI 下載新版本 ZIP 檔案
2. 解壓縮到新目錄
3. 停止現有服務: `sudo ./svc.sh stop`
4. 複製新的 agent binary 到 /opt/agent/bin/
5. 重啟服務: `sudo ./svc.sh start`

### 升級範例
```bash
# 下載新版本
wget https://mon.myelintek.com/download/v1.1.0/install-linux-amd64-v1.1.0.zip

# 解壓縮
unzip install-linux-amd64-v1.1.0.zip

# 停止服務
sudo systemctl stop agent

# 備份舊版本
sudo cp /opt/agent/bin/agent /opt/agent/bin/agent.bak

# 複製新版本
sudo cp install-linux-amd64-v1.1.0/agent /opt/agent/bin/agent

# 重啟服務
sudo systemctl start agent

# 確認版本
sudo systemctl status agent
```

### Agent 自動升級 (未來功能)
1. Server 推送升級命令
2. Agent 下載新版本 binary
3. 驗證 checksum
4. 替換舊版本 binary
5. 重啟 Agent

## 卸載

### 透過 svc.sh 卸載
```bash
# 停止並卸載服務
sudo ./svc.sh uninstall
```

### svc.sh uninstall 執行內容
```bash
#!/bin/bash
# svc.sh uninstall 功能

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

1. **install.sh 註冊失敗**
   - 確認 token 是否正確且未過期
   - 確認 Server 是否可達
   - 檢查網路連線

2. **config.yaml 未正確設定**
   - 確認已執行 `install.sh --token <token>`
   - 檢查 config.yaml 中 client_id 和 client_token 是否有值
   - 重新執行 install.sh

3. **服務無法啟動**
   - 檢查設定檔格式: `cat config.yaml`
   - 確認 agent binary 有執行權限: `chmod +x agent`
   - 查看日誌: `./svc.sh logs`

4. **Agent 無法連線到 Server**
   - 確認 server_url 設定正確
   - 檢查防火牆設定
   - 確認 WebSocket 連線 (wss://) 是否被阻擋

### 日誌位置
- 前景執行日誌: 終端輸出
- 服務日誌: `/opt/agent/logs/agent.log`
- systemd 日誌: `journalctl -u agent`

### 重新安裝
如需重新安裝，請先卸載再重新執行安裝流程：
```bash
# 卸載
sudo ./svc.sh uninstall

# 重新下載 ZIP 並安裝
./install.sh --token YOUR_NEW_TOKEN
sudo ./svc.sh install
sudo ./svc.sh start
```
