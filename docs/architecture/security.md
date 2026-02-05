# 安全性設計 (Security Design)

## 安全架構概覽

本系統採用多層安全防護機制，確保資料傳輸、儲存和存取的安全性。

## 傳輸層安全 (Transport Security)

### 1. TLS/SSL 加密

#### Server 端
- **協定**: TLS 1.2+（建議 TLS 1.3）
- **加密演算法**: 
  - ECDHE-RSA-AES128-GCM-SHA256
  - ECDHE-RSA-AES256-GCM-SHA384
  - ECDHE-RSA-CHACHA20-POLY1305
- **憑證管理**: 
  - 使用 Let's Encrypt 或商業 CA
  - 自動更新機制
  - 憑證有效期監控

#### Ingress TLS 設定
```yaml
spec:
  tls:
  - hosts:
    - agent.example.com
    secretName: agent-tls-cert
```

#### Nginx 強化設定
```nginx
# TLS 版本
ssl_protocols TLSv1.2 TLSv1.3;

# 加密套件
ssl_ciphers 'ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-RSA-CHACHA20-POLY1305';
ssl_prefer_server_ciphers on;

# HSTS
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

# SSL Session
ssl_session_cache shared:SSL:10m;
ssl_session_timeout 10m;
ssl_session_tickets off;

# OCSP Stapling
ssl_stapling on;
ssl_stapling_verify on;
```

### 2. WebSocket Secure (WSS)

- 所有 WebSocket 連線必須使用 WSS
- 禁止非加密的 WS 連線
- 連線建立時驗證 TLS 憑證

```python
# Server 端強制 WSS
if request.url.scheme != "https":
    raise HTTPException(status_code=400, detail="HTTPS required")
```

```go
// Client 端 TLS 設定
dialer := websocket.Dialer{
    TLSClientConfig: &tls.Config{
        MinVersion: tls.VersionTLS12,
        CipherSuites: []uint16{
            tls.TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256,
            tls.TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384,
        },
    },
}
```

## 認證與授權 (Authentication & Authorization)

### 1. 使用者認證

#### 密碼安全
```python
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    """使用 bcrypt 雜湊密碼"""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """驗證密碼"""
    return pwd_context.verify(plain_password, hashed_password)
```

#### 密碼政策
- 最小長度: 8 字元
- 必須包含: 大寫字母、小寫字母、數字、特殊符號
- 禁止常見弱密碼
- 密碼過期: 90 天（可選）
- 密碼歷史: 記錄最近 5 次密碼，禁止重複使用

#### JWT Token
```python
from jose import JWTError, jwt
from datetime import datetime, timedelta

SECRET_KEY = "your-secret-key"  # 從環境變數或 Secret 載入
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440  # 24 hours

def create_access_token(data: dict, expires_delta: timedelta = None):
    """建立 JWT Token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str):
    """驗證 JWT Token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return user_id
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
```

### 2. Client 認證

#### Token 產生
```python
import secrets

def generate_client_token() -> str:
    """產生 Client 認證 Token"""
    return secrets.token_urlsafe(32)

def generate_api_token() -> str:
    """產生使用者 API Token"""
    return secrets.token_urlsafe(48)
```

#### Token 驗證流程
```
Client Request
     |
     v
Extract Token from URL/Header
     |
     v
Verify Token Format
     |
     v
Query Database/Redis
     |
     v
Check Token Validity
     |
     v
Load User/Client Info
     |
     v
Grant Access
```

#### WebSocket 認證
```python
@app.websocket("/ws/{client_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    client_id: str,
    token: str = Query(...)
):
    # 驗證 token
    client = await verify_client_token(client_id, token)
    if not client:
        await websocket.close(code=1008, reason="Authentication failed")
        return
    
    # 檢查 client 是否屬於正確的使用者
    if client.user_id != get_user_from_token(token):
        await websocket.close(code=1008, reason="Unauthorized")
        return
    
    await websocket.accept()
    # ... 處理連線
```

### 3. 資料隔離

#### 使用者資料隔離
```python
@router.get("/clients")
async def get_clients(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """只返回該使用者的 clients"""
    return db.query(Client).filter(Client.user_id == current_user.id).all()

@router.get("/clients/{client_id}")
async def get_client(
    client_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """檢查 client 是否屬於該使用者"""
    client = db.query(Client).filter(
        Client.id == client_id,
        Client.user_id == current_user.id
    ).first()
    
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    return client
```

## 輸入驗證 (Input Validation)

### 1. API 輸入驗證

```python
from pydantic import BaseModel, Field, validator
import re

class ClientRegisterRequest(BaseModel):
    client_id: str = Field(..., min_length=36, max_length=36)
    hostname: str = Field(..., min_length=1, max_length=255)
    os: str = Field(..., regex="^(linux|darwin|windows)$")
    arch: str = Field(..., regex="^(amd64|arm64|386)$")
    
    @validator('hostname')
    def validate_hostname(cls, v):
        # 只允許字母、數字、點和破折號
        if not re.match(r'^[a-zA-Z0-9.-]+$', v):
            raise ValueError('Invalid hostname format')
        return v

class InventoryUpdate(BaseModel):
    hostname: str = Field(..., max_length=255)
    os: str = Field(..., max_length=50)
    cpu_count: int = Field(..., ge=1, le=1024)
    memory_total: int = Field(..., ge=0)
    disk_total: int = Field(..., ge=0)
    # ... 其他欄位
    
    class Config:
        # 限制額外欄位
        extra = "forbid"
```

### 2. WebSocket 訊息驗證

```python
def validate_message(message: dict) -> bool:
    """驗證 WebSocket 訊息格式"""
    required_fields = ["type", "data", "timestamp"]
    
    # 檢查必要欄位
    if not all(field in message for field in required_fields):
        return False
    
    # 檢查 type 是否有效
    valid_types = ["heartbeat", "inventory", "command_response", "pong"]
    if message["type"] not in valid_types:
        return False
    
    # 檢查 timestamp 是否合理 (避免 replay attack)
    current_time = time.time()
    msg_time = message["timestamp"]
    if abs(current_time - msg_time) > 300:  # 5 分鐘內
        return False
    
    # 檢查訊息大小
    if len(json.dumps(message)) > 1024 * 1024:  # 1MB
        return False
    
    return True
```

### 3. SQL Injection 防護

```python
# 使用 ORM (SQLAlchemy) 避免 SQL Injection
# ✓ 正確做法
client = db.query(Client).filter(Client.id == client_id).first()

# ✗ 錯誤做法 (不要這樣做)
# query = f"SELECT * FROM clients WHERE id = '{client_id}'"
# db.execute(query)

# 如果必須使用原生 SQL，使用參數化查詢
query = "SELECT * FROM clients WHERE id = :client_id"
result = db.execute(text(query), {"client_id": client_id})
```

## 敏感資料保護

### 1. 密碼與金鑰管理

#### Kubernetes Secrets
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: agent-server-secret
  namespace: agent-system
type: Opaque
stringData:
  DATABASE_URL: "postgresql://user:password@postgres:5432/agentdb"
  SECRET_KEY: "your-secret-key"
  JWT_ALGORITHM: "HS256"
```

#### 環境變數
```python
# 從環境變數載入敏感資訊
import os

class Settings:
    SECRET_KEY: str = os.getenv("SECRET_KEY")
    DATABASE_URL: str = os.getenv("DATABASE_URL")
    
    def __init__(self):
        if not self.SECRET_KEY:
            raise ValueError("SECRET_KEY not set")
```

#### 金鑰輪換
- 定期更換 SECRET_KEY (建議每 90 天)
- Token 過期後自動失效
- 提供金鑰輪換機制不中斷服務

### 2. 資料庫加密

#### 連線加密
```python
# PostgreSQL SSL 連線
DATABASE_URL = "postgresql://user:pass@host:5432/db?sslmode=require"
```

#### 欄位加密 (敏感資料)
```python
from cryptography.fernet import Fernet

class Encryption:
    def __init__(self, key: str):
        self.cipher = Fernet(key.encode())
    
    def encrypt(self, data: str) -> str:
        """加密資料"""
        return self.cipher.encrypt(data.encode()).decode()
    
    def decrypt(self, encrypted_data: str) -> str:
        """解密資料"""
        return self.cipher.decrypt(encrypted_data.encode()).decode()

# 使用範例
enc = Encryption(settings.ENCRYPTION_KEY)
user.api_token = enc.encrypt(token)
```

### 3. 日誌脫敏

```python
import re

def sanitize_log(message: str) -> str:
    """移除日誌中的敏感資訊"""
    # 移除 Token
    message = re.sub(r'token=[A-Za-z0-9_-]+', 'token=***', message)
    
    # 移除密碼
    message = re.sub(r'"password":\s*"[^"]+"', '"password": "***"', message)
    
    # 移除 API Key
    message = re.sub(r'api_key=[A-Za-z0-9_-]+', 'api_key=***', message)
    
    return message

# 自訂 Logger
class SecureLogger:
    def info(self, message: str):
        safe_message = sanitize_log(message)
        logger.info(safe_message)
```

## 網路安全

### 1. Rate Limiting (頻率限制)

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.post("/api/v1/auth/login")
@limiter.limit("5/minute")  # 每分鐘最多 5 次登入嘗試
async def login(request: Request, credentials: LoginRequest):
    # ... 登入邏輯
    pass

@app.post("/api/v1/clients/register")
@limiter.limit("10/hour")  # 每小時最多 10 次註冊
async def register_client(request: Request, data: ClientRegisterRequest):
    # ... 註冊邏輯
    pass
```

### 2. CORS 設定

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://agent.example.com"  # 只允許特定來源
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
    max_age=3600,
)
```

### 3. DDoS 防護

#### Kubernetes NetworkPolicy
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: agent-server-netpol
  namespace: agent-system
spec:
  podSelector:
    matchLabels:
      app: agent-server
  policyTypes:
  - Ingress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: ingress-nginx
    ports:
    - protocol: TCP
      port: 8000
```

#### Ingress Rate Limiting
```yaml
annotations:
  nginx.ingress.kubernetes.io/limit-rps: "100"
  nginx.ingress.kubernetes.io/limit-connections: "50"
```

### 4. IP 白名單 (選用)

```python
ALLOWED_IPS = ["192.168.1.0/24", "10.0.0.0/8"]

def check_ip_whitelist(request: Request):
    client_ip = request.client.host
    if not is_ip_allowed(client_ip, ALLOWED_IPS):
        raise HTTPException(status_code=403, detail="IP not allowed")
```

## 審計與監控

### 1. 審計日誌

```python
def log_audit_event(
    user_id: str,
    event_type: str,
    event_action: str,
    result: str,
    details: dict,
    ip_address: str
):
    """記錄審計事件"""
    audit_log = AuditLog(
        user_id=user_id,
        event_type=event_type,
        event_action=event_action,
        event_result=result,
        ip_address=ip_address,
        details=details,
        created_at=datetime.utcnow()
    )
    db.add(audit_log)
    db.commit()

# 使用範例
@router.post("/auth/login")
async def login(request: Request, credentials: LoginRequest):
    # ... 登入邏輯
    
    log_audit_event(
        user_id=user.id,
        event_type="user.login",
        event_action="login",
        result="success",
        details={"method": "password"},
        ip_address=request.client.host
    )
```

### 2. 安全事件監控

```python
# 監控異常登入
def detect_suspicious_login(user_id: str, ip_address: str):
    """檢測可疑登入"""
    # 檢查是否為新 IP
    last_login = get_last_login(user_id)
    if last_login and last_login.ip_address != ip_address:
        alert_security_team(f"New IP login for user {user_id}")
    
    # 檢查登入頻率
    recent_logins = get_recent_logins(user_id, minutes=5)
    if len(recent_logins) > 3:
        alert_security_team(f"Multiple login attempts for user {user_id}")

# 監控異常 Client 行為
def detect_abnormal_behavior(client_id: str):
    """檢測異常 Client 行為"""
    # 檢查心跳頻率
    heartbeat_rate = get_heartbeat_rate(client_id)
    if heartbeat_rate > 10:  # 每秒超過 10 次
        alert_security_team(f"High heartbeat rate for client {client_id}")
    
    # 檢查資料上傳量
    upload_size = get_upload_size(client_id, minutes=1)
    if upload_size > 10 * 1024 * 1024:  # 超過 10MB
        alert_security_team(f"Large data upload from client {client_id}")
```

### 3. 安全告警

```python
import smtplib
from email.mime.text import MIMEText

def send_security_alert(subject: str, message: str):
    """發送安全告警郵件"""
    msg = MIMEText(message)
    msg['Subject'] = f"[SECURITY ALERT] {subject}"
    msg['From'] = "security@example.com"
    msg['To'] = "admin@example.com"
    
    with smtplib.SMTP('smtp.example.com') as smtp:
        smtp.send_message(msg)

def alert_security_team(message: str):
    """通知安全團隊"""
    logger.warning(f"Security Alert: {message}")
    send_security_alert("Security Event Detected", message)
```

## 定期安全檢查

### 1. 漏洞掃描

```bash
# Python 依賴漏洞掃描
pip install safety
safety check

# Docker 映像掃描
trivy image your-registry/agent-server:v1.0.0

# Kubernetes 安全掃描
kubesec scan deployment.yaml
```

### 2. 滲透測試

- 定期進行滲透測試
- 測試 API 端點安全性
- 測試 WebSocket 連線安全性
- 驗證認證授權機制

### 3. 安全更新

- 定期更新依賴套件
- 追蹤 CVE 漏洞
- 及時修補安全漏洞
- 測試更新後的系統穩定性

## 安全檢查清單

### 部署前檢查
- [ ] TLS 憑證已正確配置
- [ ] 所有密碼已從程式碼中移除
- [ ] Secret Key 已安全儲存
- [ ] 資料庫連線已加密
- [ ] 所有 API 端點已實作認證
- [ ] 輸入驗證已實作
- [ ] Rate Limiting 已啟用
- [ ] CORS 設定正確
- [ ] 審計日誌已啟用
- [ ] 監控告警已設定

### 定期檢查
- [ ] 檢查審計日誌
- [ ] 檢查異常登入
- [ ] 檢查系統漏洞
- [ ] 更新依賴套件
- [ ] 檢查憑證有效期
- [ ] 檢查 Token 有效性
- [ ] 檢查資源使用情況
- [ ] 檢查安全告警

## 安全最佳實踐

1. **最小權限原則**: 只授予必要的權限
2. **縱深防禦**: 多層安全防護
3. **安全預設**: 預設使用安全設定
4. **fail-safe**: 失敗時保持安全狀態
5. **定期審查**: 定期檢查和更新安全設定
6. **教育訓練**: 培訓團隊成員安全意識
7. **事件回應**: 建立安全事件回應流程
8. **備份恢復**: 定期備份並測試恢復流程
