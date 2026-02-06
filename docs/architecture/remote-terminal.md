# 遠端終端機存取設計 (Remote Terminal Access Design)

## 功能概述

遠端終端機存取功能允許使用者透過 Web UI 直接連線到 Client 主機的終端機（Terminal），執行指令並即時查看輸出。這提供了類似 SSH 的遠端管理能力，但整合在 Web 介面中，無需額外的 SSH 設定。

## 核心特性

- 🖥️ **Web-based Terminal**: 在瀏覽器中直接操作遠端終端機
- 🔐 **安全連線**: 透過 WSS (WebSocket Secure) 加密傳輸
- 👤 **權限控制**: 只能存取自己的 Client
- 📝 **即時互動**: 支援即時輸入輸出
- 🎨 **終端模擬**: 支援顏色、控制字元等終端特性
- 📊 **Session 管理**: 多重終端 Session 支援
- 📋 **審計記錄**: 記錄所有終端操作

## 架構設計

```
┌─────────────────────────────────────────────────────────┐
│                    Web Browser                          │
│  ┌──────────────────────────────────────────────────┐  │
│  │          Web UI (Terminal Component)             │  │
│  │  ┌────────────────────────────────────────────┐  │  │
│  │  │  xterm.js Terminal Emulator                │  │  │
│  │  │  - Input: Keyboard events                  │  │  │
│  │  │  - Output: Terminal display                │  │  │
│  │  │  - Support: ANSI colors, cursor control    │  │  │
│  │  └────────────────────────────────────────────┘  │  │
│  └───────────────────┬──────────────────────────────┘  │
└────────────────────┬─┴──────────────────────────────────┘
                     │ WSS (WebSocket Secure)
                     │ /terminal/{client_id}
                     │
          ┌──────────▼─────────────┐
          │   Server (Python)      │
          │  ┌─────────────────┐   │
          │  │ Terminal Proxy  │   │
          │  │ WebSocket       │   │
          │  │ Handler         │   │
          │  └────────┬────────┘   │
          └───────────┼────────────┘
                      │ WSS (WebSocket Secure)
                      │ /ws/{client_id} + terminal command
                      │
            ┌─────────▼────────┐
            │   Client (Agent)  │
            │  ┌──────────────┐ │
            │  │ Terminal     │ │
            │  │ Executor     │ │
            │  │ (PTY/Shell)  │ │
            │  └──────────────┘ │
            └───────────────────┘
                 Host Machine
```

## 實作細節

### 1. Web UI 終端機元件

#### 技術選型
- **終端模擬器**: xterm.js (https://xtermjs.org/)
- **WebSocket 客戶端**: 瀏覽器原生 WebSocket API
- **UI 框架**: Vue.js

#### HTML/JavaScript 範例

```html
<!DOCTYPE html>
<html>
<head>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/xterm@5.1.0/css/xterm.css" />
    <script src="https://cdn.jsdelivr.net/npm/xterm@5.1.0/lib/xterm.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/xterm-addon-fit@0.7.0/lib/xterm-addon-fit.js"></script>
    <style>
        #terminal-container {
            width: 100%;
            height: 600px;
            background-color: #000;
        }
    </style>
</head>
<body>
    <div class="terminal-header">
        <h3>Terminal - Client: <span id="client-hostname"></span></h3>
        <button id="disconnect-btn">Disconnect</button>
    </div>
    <div id="terminal-container"></div>

    <script>
        // 初始化 xterm.js
        const term = new Terminal({
            cursorBlink: true,
            fontSize: 14,
            fontFamily: 'Monaco, Courier, monospace',
            theme: {
                background: '#1e1e1e',
                foreground: '#d4d4d4'
            }
        });
        
        const fitAddon = new FitAddon.FitAddon();
        term.loadAddon(fitAddon);
        
        // 將終端機附加到 DOM
        term.open(document.getElementById('terminal-container'));
        fitAddon.fit();
        
        // 建立 WebSocket 連線
        const clientId = getClientIdFromURL(); // 從 URL 取得 client_id
        const token = getAuthToken(); // 從 session/cookie 取得認證 token
        const wsUrl = `wss://${window.location.host}/terminal/${clientId}?token=${token}`;
        const ws = new WebSocket(wsUrl);
        
        // WebSocket 連線建立
        ws.onopen = () => {
            console.log('Terminal WebSocket connected');
            term.writeln('\x1b[32mConnected to remote terminal\x1b[0m');
            
            // 發送初始化訊息
            ws.send(JSON.stringify({
                type: 'terminal_init',
                data: {
                    rows: term.rows,
                    cols: term.cols,
                    shell: '/bin/bash' // 或 /bin/sh, /bin/zsh
                }
            }));
        };
        
        // 接收 Server 傳來的輸出
        ws.onmessage = (event) => {
            const message = JSON.parse(event.data);
            
            if (message.type === 'terminal_output') {
                // 顯示終端輸出
                term.write(message.data.output);
            } else if (message.type === 'terminal_error') {
                term.writeln(`\x1b[31mError: ${message.data.message}\x1b[0m`);
            } else if (message.type === 'terminal_closed') {
                term.writeln('\x1b[33mTerminal session closed\x1b[0m');
                ws.close();
            }
        };
        
        // 發送使用者輸入到 Server
        term.onData((data) => {
            if (ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({
                    type: 'terminal_input',
                    data: {
                        input: data
                    }
                }));
            }
        });
        
        // 處理視窗大小變更
        window.addEventListener('resize', () => {
            fitAddon.fit();
            
            // 通知 Server 終端大小變更
            if (ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({
                    type: 'terminal_resize',
                    data: {
                        rows: term.rows,
                        cols: term.cols
                    }
                }));
            }
        });
        
        // WebSocket 關閉
        ws.onclose = () => {
            console.log('Terminal WebSocket closed');
            term.writeln('\x1b[31mDisconnected from remote terminal\x1b[0m');
        };
        
        // WebSocket 錯誤
        ws.onerror = (error) => {
            console.error('Terminal WebSocket error:', error);
            term.writeln('\x1b[31mConnection error\x1b[0m');
        };
        
        // 斷線按鈕
        document.getElementById('disconnect-btn').addEventListener('click', () => {
            if (ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({
                    type: 'terminal_close',
                    data: {}
                }));
            }
            ws.close();
        });
    </script>
</body>
</html>
```

### 2. Server 端終端機代理

#### WebSocket 端點

```python
# terminal_proxy.py
from fastapi import WebSocket, WebSocketDisconnect, Depends, HTTPException
import asyncio
import json

class TerminalProxy:
    def __init__(self):
        # client_id -> (user_websocket, client_websocket)
        self.active_terminals = {}
        self.redis_client = redis.Redis(...)
    
    async def handle_terminal_connection(
        self,
        user_websocket: WebSocket,
        client_id: str,
        user: User
    ):
        """處理 Web UI 到 Server 的終端機連線"""
        
        # 驗證使用者是否有權限存取此 Client
        client = await self.verify_client_access(client_id, user.id)
        if not client:
            await user_websocket.close(code=1008, reason="Unauthorized")
            return
        
        # 檢查 Client 是否在線
        client_status = await self.redis_client.hget(f"client:{client_id}", "status")
        if client_status != b"online":
            await user_websocket.close(code=1008, reason="Client offline")
            return
        
        # 接受 WebSocket 連線
        await user_websocket.accept()
        
        # 建立到 Client 的終端機 Session
        session_id = str(uuid.uuid4())
        self.active_terminals[session_id] = {
            "client_id": client_id,
            "user_id": user.id,
            "user_ws": user_websocket,
            "started_at": datetime.utcnow()
        }
        
        try:
            # 發送初始化命令到 Client
            await self.send_to_client(client_id, {
                "type": "terminal_start",
                "data": {
                    "session_id": session_id
                }
            })
            
            # 轉發訊息
            await self.proxy_messages(user_websocket, client_id, session_id)
            
        except WebSocketDisconnect:
            logger.info(f"User disconnected from terminal: {session_id}")
        except Exception as e:
            logger.error(f"Terminal proxy error: {e}")
        finally:
            # 清理
            await self.cleanup_terminal(session_id, client_id)
            del self.active_terminals[session_id]
    
    async def proxy_messages(
        self,
        user_websocket: WebSocket,
        client_id: str,
        session_id: str
    ):
        """在 User WebSocket 和 Client 之間轉發訊息"""
        
        while True:
            # 接收來自 Web UI 的訊息
            data = await user_websocket.receive_json()
            
            if data["type"] == "terminal_init":
                # 初始化終端機
                await self.send_to_client(client_id, {
                    "type": "terminal_command",
                    "data": {
                        "session_id": session_id,
                        "command": "init",
                        "params": {
                            "rows": data["data"]["rows"],
                            "cols": data["data"]["cols"],
                            "shell": data["data"].get("shell", "/bin/bash")
                        }
                    }
                })
            
            elif data["type"] == "terminal_input":
                # 轉發使用者輸入到 Client
                await self.send_to_client(client_id, {
                    "type": "terminal_command",
                    "data": {
                        "session_id": session_id,
                        "command": "input",
                        "params": {
                            "input": data["data"]["input"]
                        }
                    }
                })
            
            elif data["type"] == "terminal_resize":
                # 調整終端機大小
                await self.send_to_client(client_id, {
                    "type": "terminal_command",
                    "data": {
                        "session_id": session_id,
                        "command": "resize",
                        "params": {
                            "rows": data["data"]["rows"],
                            "cols": data["data"]["cols"]
                        }
                    }
                })
            
            elif data["type"] == "terminal_close":
                # 關閉終端機
                await self.send_to_client(client_id, {
                    "type": "terminal_command",
                    "data": {
                        "session_id": session_id,
                        "command": "close"
                    }
                })
                break
    
    async def send_to_client(self, client_id: str, message: dict):
        """透過主要 WebSocket 連線發送訊息到 Client"""
        # 透過 ConnectionManager 發送
        await connection_manager.send_message(client_id, message)
    
    async def handle_client_terminal_output(
        self,
        client_id: str,
        session_id: str,
        output: str
    ):
        """處理來自 Client 的終端機輸出"""
        if session_id in self.active_terminals:
            terminal = self.active_terminals[session_id]
            user_ws = terminal["user_ws"]
            
            try:
                await user_ws.send_json({
                    "type": "terminal_output",
                    "data": {
                        "output": output
                    }
                })
            except Exception as e:
                logger.error(f"Failed to send terminal output: {e}")
    
    async def cleanup_terminal(self, session_id: str, client_id: str):
        """清理終端機 Session"""
        # 通知 Client 關閉終端
        await self.send_to_client(client_id, {
            "type": "terminal_command",
            "data": {
                "session_id": session_id,
                "command": "close"
            }
        })
        
        # 記錄審計日誌
        if session_id in self.active_terminals:
            terminal = self.active_terminals[session_id]
            log_audit_event(
                user_id=terminal["user_id"],
                event_type="terminal.close",
                event_action="disconnect",
                details={
                    "session_id": session_id,
                    "client_id": client_id,
                    "duration": (datetime.utcnow() - terminal["started_at"]).total_seconds()
                }
            )

# FastAPI 路由
terminal_proxy = TerminalProxy()

@app.websocket("/terminal/{client_id}")
async def terminal_websocket(
    websocket: WebSocket,
    client_id: str,
    token: str,
    current_user: User = Depends(get_current_user_from_token)
):
    """Terminal WebSocket endpoint"""
    await terminal_proxy.handle_terminal_connection(
        websocket,
        client_id,
        current_user
    )
```

### 3. Client 端終端機執行器

#### Golang 實作

```go
// internal/agent/terminal/executor.go
package terminal

import (
    "io"
    "os"
    "os/exec"
    "sync"
    
    "github.com/creack/pty"
)

type TerminalExecutor struct {
    sessions map[string]*TerminalSession
    mu       sync.RWMutex
    wsClient *websocket.WSClient
}

type TerminalSession struct {
    SessionID string
    PTY       *os.File
    Cmd       *exec.Cmd
    Rows      int
    Cols      int
    Shell     string
}

func NewTerminalExecutor(wsClient *websocket.WSClient) *TerminalExecutor {
    return &TerminalExecutor{
        sessions: make(map[string]*TerminalSession),
        wsClient: wsClient,
    }
}

func (te *TerminalExecutor) HandleTerminalCommand(command map[string]interface{}) error {
    sessionID := command["session_id"].(string)
    cmd := command["command"].(string)
    params := command["params"].(map[string]interface{})
    
    switch cmd {
    case "init":
        return te.initTerminal(sessionID, params)
    case "input":
        return te.handleInput(sessionID, params)
    case "resize":
        return te.resizeTerminal(sessionID, params)
    case "close":
        return te.closeTerminal(sessionID)
    default:
        return fmt.Errorf("unknown command: %s", cmd)
    }
}

func (te *TerminalExecutor) initTerminal(sessionID string, params map[string]interface{}) error {
    te.mu.Lock()
    defer te.mu.Unlock()
    
    // 取得參數
    rows := int(params["rows"].(float64))
    cols := int(params["cols"].(float64))
    shell := params["shell"].(string)
    
    // 預設 shell
    if shell == "" {
        shell = getDefaultShell()
    }
    
    // 建立 PTY
    cmd := exec.Command(shell)
    cmd.Env = os.Environ()
    
    ptmx, err := pty.Start(cmd)
    if err != nil {
        return fmt.Errorf("failed to start pty: %w", err)
    }
    
    // 設定終端大小
    if err := pty.Setsize(ptmx, &pty.Winsize{
        Rows: uint16(rows),
        Cols: uint16(cols),
    }); err != nil {
        ptmx.Close()
        return fmt.Errorf("failed to set terminal size: %w", err)
    }
    
    // 儲存 session
    session := &TerminalSession{
        SessionID: sessionID,
        PTY:       ptmx,
        Cmd:       cmd,
        Rows:      rows,
        Cols:      cols,
        Shell:     shell,
    }
    te.sessions[sessionID] = session
    
    // 啟動 goroutine 讀取輸出
    go te.readOutput(session)
    
    return nil
}

func (te *TerminalExecutor) readOutput(session *TerminalSession) {
    buffer := make([]byte, 4096)
    
    for {
        n, err := session.PTY.Read(buffer)
        if err != nil {
            if err != io.EOF {
                log.Errorf("Failed to read from PTY: %v", err)
            }
            break
        }
        
        // 發送輸出到 Server
        output := string(buffer[:n])
        te.sendOutput(session.SessionID, output)
    }
    
    // 清理
    te.closeTerminal(session.SessionID)
}

func (te *TerminalExecutor) sendOutput(sessionID string, output string) {
    // 透過 WebSocket 發送輸出到 Server
    message := map[string]interface{}{
        "type": "terminal_output",
        "data": map[string]interface{}{
            "session_id": sessionID,
            "output":     output,
        },
    }
    
    if err := te.wsClient.SendMessage("terminal_data", message); err != nil {
        log.Errorf("Failed to send terminal output: %v", err)
    }
}

func (te *TerminalExecutor) handleInput(sessionID string, params map[string]interface{}) error {
    te.mu.RLock()
    session, exists := te.sessions[sessionID]
    te.mu.RUnlock()
    
    if !exists {
        return fmt.Errorf("terminal session not found: %s", sessionID)
    }
    
    input := params["input"].(string)
    
    // 寫入到 PTY
    if _, err := session.PTY.Write([]byte(input)); err != nil {
        return fmt.Errorf("failed to write to PTY: %w", err)
    }
    
    return nil
}

func (te *TerminalExecutor) resizeTerminal(sessionID string, params map[string]interface{}) error {
    te.mu.RLock()
    session, exists := te.sessions[sessionID]
    te.mu.RUnlock()
    
    if !exists {
        return fmt.Errorf("terminal session not found: %s", sessionID)
    }
    
    rows := int(params["rows"].(float64))
    cols := int(params["cols"].(float64))
    
    if err := pty.Setsize(session.PTY, &pty.Winsize{
        Rows: uint16(rows),
        Cols: uint16(cols),
    }); err != nil {
        return fmt.Errorf("failed to resize terminal: %w", err)
    }
    
    session.Rows = rows
    session.Cols = cols
    
    return nil
}

func (te *TerminalExecutor) closeTerminal(sessionID string) error {
    te.mu.Lock()
    defer te.mu.Unlock()
    
    session, exists := te.sessions[sessionID]
    if !exists {
        return nil // 已經關閉
    }
    
    // 關閉 PTY
    if session.PTY != nil {
        session.PTY.Close()
    }
    
    // 終止程序
    if session.Cmd != nil && session.Cmd.Process != nil {
        session.Cmd.Process.Kill()
    }
    
    // 移除 session
    delete(te.sessions, sessionID)
    
    return nil
}

func getDefaultShell() string {
    // 嘗試取得使用者的預設 shell
    if shell := os.Getenv("SHELL"); shell != "" {
        return shell
    }
    
    // 根據作業系統選擇
    switch runtime.GOOS {
    case "windows":
        return "cmd.exe"
    default:
        return "/bin/bash"
    }
}
```

#### 整合到主程式

```go
// cmd/agent/main.go
func main() {
    // ... 現有程式碼 ...
    
    // 建立 Terminal Executor
    terminalExecutor := terminal.NewTerminalExecutor(wsClient)
    
    // 處理 Server 傳來的終端機命令
    wsClient.OnMessage("terminal_command", func(data map[string]interface{}) {
        if err := terminalExecutor.HandleTerminalCommand(data); err != nil {
            log.Errorf("Terminal command error: %v", err)
        }
    })
    
    // 處理終端機輸出
    wsClient.OnMessage("terminal_data", func(data map[string]interface{}) {
        // 轉發到 Server
        sessionID := data["session_id"].(string)
        output := data["output"].(string)
        
        terminalProxy.SendToUser(sessionID, output)
    })
    
    // ... 其他程式碼 ...
}
```

## 安全考量

### 1. 權限控制

```python
async def verify_terminal_access(user_id: str, client_id: str) -> bool:
    """驗證使用者是否有權限存取 Client 的終端機"""
    
    # 檢查 Client 是否屬於該使用者
    client = db.query(Client).filter(
        Client.id == client_id,
        Client.user_id == user_id
    ).first()
    
    if not client:
        return False
    
    # 檢查使用者是否有終端機存取權限
    user = db.query(User).filter(User.id == user_id).first()
    if not user.has_terminal_permission:
        return False
    
    return True
```

### 2. 命令審計

```python
def log_terminal_command(session_id: str, command: str):
    """記錄終端機命令（用於審計）"""
    
    terminal_log = TerminalLog(
        session_id=session_id,
        command=command,
        timestamp=datetime.utcnow()
    )
    db.add(terminal_log)
    db.commit()
```

### 3. 限制與保護

```python
# 設定檔
class TerminalSettings:
    # Session 超時時間
    SESSION_TIMEOUT = 3600  # 1 小時
    
    # 最大同時 Session 數
    MAX_SESSIONS_PER_USER = 5
    
    # 禁止的命令（選用）
    BLOCKED_COMMANDS = [
        "rm -rf /",
        "mkfs",
        # ... 其他危險命令
    ]
    
    # 是否記錄所有輸出
    LOG_ALL_OUTPUT = True
```

### 4. 資料加密

- 所有終端機通訊透過 WSS 加密
- 敏感輸出（如密碼）應該被遮蔽
- Session 資料不應儲存在明文日誌中

## 資料模型

### Terminal Sessions 表

```sql
CREATE TABLE terminal_sessions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id          VARCHAR(255) UNIQUE NOT NULL,
    user_id             UUID NOT NULL REFERENCES users(id),
    client_id           UUID NOT NULL REFERENCES clients(id),
    
    -- Session 資訊
    shell               VARCHAR(50),
    started_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at            TIMESTAMP,
    status              VARCHAR(50) DEFAULT 'active',
    
    -- 統計資訊
    commands_count      INTEGER DEFAULT 0,
    duration_seconds    INTEGER,
    
    INDEX idx_user_id (user_id),
    INDEX idx_client_id (client_id),
    INDEX idx_session_id (session_id),
    INDEX idx_status (status)
);
```

### Terminal Logs 表

```sql
CREATE TABLE terminal_logs (
    id                  BIGSERIAL PRIMARY KEY,
    session_id          VARCHAR(255) NOT NULL,
    
    -- 日誌類型
    log_type            VARCHAR(50) NOT NULL, -- 'input', 'output', 'command'
    
    -- 內容
    content             TEXT,
    
    -- 時間戳記
    timestamp           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_session_id (session_id),
    INDEX idx_timestamp (timestamp)
);
```

## UI/UX 設計

### Terminal 頁面佈局

```
┌────────────────────────────────────────────────────────┐
│  Agent Management > Client: server-01 > Terminal       │
├────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────┐  │
│  │  Terminal Controls                                │  │
│  │  [Disconnect] [Clear] [Copy] [New Tab]           │  │
│  └──────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────┐  │
│  │  Terminal Display (xterm.js)                     │  │
│  │  ┌────────────────────────────────────────────┐  │  │
│  │  │ user@server-01:~$ ls -la                   │  │  │
│  │  │ total 48                                    │  │  │
│  │  │ drwxr-xr-x 5 user user 4096 Feb  5 10:00 . │  │  │
│  │  │ drwxr-xr-x 3 root root 4096 Jan 15 09:00 ..│  │  │
│  │  │ -rw-r--r-- 1 user user  220 Jan 15 09:00 .b│  │  │
│  │  │ user@server-01:~$ _                        │  │  │
│  │  └────────────────────────────────────────────┘  │  │
│  └──────────────────────────────────────────────────┘  │
│  Session Info: Active | Duration: 00:05:32             │
└────────────────────────────────────────────────────────┘
```

### 互動流程

1. **開啟終端機**
   - 使用者在 Client 列表點擊「Open Terminal」
   - 系統檢查權限
   - 建立 WebSocket 連線
   - 顯示終端機介面

2. **執行命令**
   - 使用者輸入命令
   - 即時傳送到 Client
   - Client 執行並回傳輸出
   - 顯示在終端機中

3. **關閉終端機**
   - 使用者點擊 Disconnect
   - 關閉 WebSocket 連線
   - Client 終止 shell process
   - 記錄 Session 資訊

## 效能考量

### 1. 資料傳輸優化

```python
# 批次傳送輸出（減少 WebSocket 訊息數）
class OutputBuffer:
    def __init__(self, max_size=4096, flush_interval=0.05):
        self.buffer = []
        self.max_size = max_size
        self.flush_interval = flush_interval
        self.last_flush = time.time()
    
    def add(self, data):
        self.buffer.append(data)
        
        # 達到大小限制或時間間隔，立即 flush
        if self.get_size() >= self.max_size or \
           time.time() - self.last_flush >= self.flush_interval:
            return self.flush()
        
        return None
    
    def flush(self):
        if not self.buffer:
            return None
        
        data = ''.join(self.buffer)
        self.buffer = []
        self.last_flush = time.time()
        return data
```

### 2. 連線管理

- 限制每個使用者的同時 Session 數
- Session 超時自動關閉
- 非活動 Session 自動清理

### 3. 資源限制

```go
// 限制 PTY 輸出緩衝區大小
const MAX_PTY_BUFFER_SIZE = 8192

// 限制命令執行時間（可選）
const COMMAND_TIMEOUT = 300 * time.Second
```

## 故障排除

### 常見問題

1. **無法連線到終端機**
   - 檢查 Client 是否 online
   - 檢查使用者權限
   - 檢查 WebSocket 連線

2. **終端機輸出延遲**
   - 檢查網路延遲
   - 調整輸出緩衝設定
   - 檢查 Server 負載

3. **終端機無法輸入中文**
   - 設定正確的 locale
   - 確保 PTY 支援 UTF-8

### 日誌記錄

```python
logger.info(f"Terminal session started: {session_id}")
logger.debug(f"Terminal input: {sanitize(command)}")
logger.info(f"Terminal session closed: {session_id}, duration: {duration}s")
logger.error(f"Terminal error: {error_message}")
```

## 測試建議

### 1. 功能測試

- 基本命令執行（ls, pwd, echo）
- 互動式命令（vi, nano）
- 長時間執行的命令（top, tail -f）
- 特殊字元處理

### 2. 安全測試

- 權限驗證
- 未授權存取嘗試
- 惡意命令注入
- Session 劫持

### 3. 效能測試

- 多個同時 Session
- 大量輸出處理
- 網路延遲情況
- 連線斷開重連

## 未來擴展

### 可能的改進

1. **多 Tab 支援**: 同時開啟多個終端機
2. **檔案上傳/下載**: 透過終端機介面傳輸檔案
3. **命令歷史**: 記錄和搜尋命令歷史
4. **Session 錄影**: 記錄完整 Session 供回放
5. **協作模式**: 多使用者同時存取同一終端機
6. **自動補全**: 提供命令和路徑自動補全
7. **視窗分割**: 在同一頁面顯示多個終端機

## 總結

遠端終端機存取功能提供了強大的遠端管理能力，但也帶來了安全風險。實作時必須特別注意：

1. ✅ 嚴格的權限控制
2. ✅ 完整的審計記錄
3. ✅ 加密的通訊傳輸
4. ✅ 適當的限制與保護
5. ✅ 良好的錯誤處理

正確實作的終端機存取功能可以大幅提升系統的可管理性和使用便利性。
