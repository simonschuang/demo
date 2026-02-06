/**
 * Agent Monitor - Main JavaScript Application
 */

// API Base URL
const API_BASE = '/api/v1';

// Application State
const state = {
  token: localStorage.getItem('token'),
  user: null,
  clients: [],
  currentPage: 'dashboard'
};

// Utility Functions
function formatBytes(bytes) {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function formatDate(dateString) {
  if (!dateString) return '-';
  const date = new Date(dateString);
  return date.toLocaleString();
}

function getStatusClass(status) {
  return status === 'online' ? 'badge-online' : 'badge-offline';
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// API Functions
async function apiRequest(endpoint, options = {}) {
  const headers = {
    'Content-Type': 'application/json',
    ...options.headers
  };

  if (state.token) {
    headers['Authorization'] = `Bearer ${state.token}`;
  }

  try {
    const response = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers
    });

    if (response.status === 401) {
      logout();
      throw new Error('Session expired. Please login again.');
    }

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || 'API request failed');
    }

    return data;
  } catch (error) {
    console.error('API Error:', error);
    throw error;
  }
}

// Auth Functions
async function login(username, password) {
  const data = await apiRequest('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password })
  });

  state.token = data.access_token;
  localStorage.setItem('token', data.access_token);

  return data;
}

async function register(username, email, password) {
  return await apiRequest('/auth/register', {
    method: 'POST',
    body: JSON.stringify({ username, email, password })
  });
}

function logout() {
  state.token = null;
  state.user = null;
  localStorage.removeItem('token');
  showLoginPage();
}

async function getCurrentUser() {
  const data = await apiRequest('/auth/me');
  state.user = data;
  return data;
}

// Client Functions
async function getClients() {
  const data = await apiRequest('/clients');
  state.clients = data.clients;
  return data;
}

async function getClient(clientId) {
  return await apiRequest(`/clients/${clientId}`);
}

async function createClient(clientData) {
  return await apiRequest('/clients', {
    method: 'POST',
    body: JSON.stringify(clientData)
  });
}

async function deleteClient(clientId) {
  return await apiRequest(`/clients/${clientId}`, {
    method: 'DELETE'
  });
}

async function regenerateToken(clientId) {
  return await apiRequest(`/clients/${clientId}/regenerate-token`, {
    method: 'POST'
  });
}

// Inventory Functions
async function getInventory(clientId) {
  return await apiRequest(`/inventory/${clientId}`);
}

async function getInventoryHistory(clientId, limit = 10) {
  return await apiRequest(`/inventory/${clientId}/history?limit=${limit}`);
}

// UI Functions
function showLoginPage() {
  document.getElementById('app').innerHTML = `
        <div class="login-container">
            <div class="login-card">
                <h1>🖥️ Agent Monitor</h1>
                <p class="subtitle">Sign in to your account</p>
                <div id="loginError" class="alert alert-danger" style="display: none;"></div>
                <form id="loginForm">
                    <div class="form-group">
                        <label for="username">Username</label>
                        <input type="text" id="username" class="form-control" placeholder="Enter username" required>
                    </div>
                    <div class="form-group">
                        <label for="password">Password</label>
                        <input type="password" id="password" class="form-control" placeholder="Enter password" required>
                    </div>
                    <button type="submit" class="btn btn-primary btn-block">Sign In</button>
                </form>
                <p class="mt-2 text-center" style="color: var(--text-muted);">
                    Don't have an account? <a href="#" id="showRegister">Register</a>
                </p>
            </div>
        </div>
    `;

  document.getElementById('loginForm').addEventListener('submit', handleLogin);
  document.getElementById('showRegister').addEventListener('click', showRegisterPage);
}

function showRegisterPage(e) {
  if (e) e.preventDefault();

  document.getElementById('app').innerHTML = `
        <div class="login-container">
            <div class="login-card">
                <h1>🖥️ Agent Monitor</h1>
                <p class="subtitle">Create a new account</p>
                <div id="registerError" class="alert alert-danger" style="display: none;"></div>
                <div id="registerSuccess" class="alert alert-success" style="display: none;"></div>
                <form id="registerForm">
                    <div class="form-group">
                        <label for="regUsername">Username</label>
                        <input type="text" id="regUsername" class="form-control" placeholder="Enter username" required>
                    </div>
                    <div class="form-group">
                        <label for="regEmail">Email</label>
                        <input type="email" id="regEmail" class="form-control" placeholder="Enter email" required>
                    </div>
                    <div class="form-group">
                        <label for="regPassword">Password</label>
                        <input type="password" id="regPassword" class="form-control" placeholder="Enter password" required>
                    </div>
                    <button type="submit" class="btn btn-primary btn-block">Register</button>
                </form>
                <p class="mt-2 text-center" style="color: var(--text-muted);">
                    Already have an account? <a href="#" id="showLogin">Sign In</a>
                </p>
            </div>
        </div>
    `;

  document.getElementById('registerForm').addEventListener('submit', handleRegister);
  document.getElementById('showLogin').addEventListener('click', showLoginPage);
}

async function handleLogin(e) {
  e.preventDefault();

  const username = document.getElementById('username').value;
  const password = document.getElementById('password').value;
  const errorDiv = document.getElementById('loginError');

  try {
    await login(username, password);
    await showDashboard();
  } catch (error) {
    errorDiv.textContent = error.message;
    errorDiv.style.display = 'block';
  }
}

async function handleRegister(e) {
  e.preventDefault();

  const username = document.getElementById('regUsername').value;
  const email = document.getElementById('regEmail').value;
  const password = document.getElementById('regPassword').value;
  const errorDiv = document.getElementById('registerError');
  const successDiv = document.getElementById('registerSuccess');

  try {
    await register(username, email, password);
    errorDiv.style.display = 'none';
    successDiv.textContent = 'Registration successful! Please sign in.';
    successDiv.style.display = 'block';

    setTimeout(() => showLoginPage(), 2000);
  } catch (error) {
    successDiv.style.display = 'none';
    errorDiv.textContent = error.message;
    errorDiv.style.display = 'block';
  }
}

async function showDashboard() {
  try {
    const user = await getCurrentUser();
    const clientsData = await getClients();

    const onlineCount = clientsData.clients.filter(c => c.status === 'online').length;
    const offlineCount = clientsData.total - onlineCount;

    document.getElementById('app').innerHTML = `
            <div class="app-container">
                ${renderSidebar(user)}
                <main class="main-content">
                    <div class="page-header">
                        <h1>Dashboard</h1>
                        <button class="btn btn-primary" onclick="showCreateClientModal()">
                            <i>➕</i> Add Client
                        </button>
                    </div>
                    
                    <div class="stats-grid">
                        <div class="stat-card">
                            <div class="stat-icon total">🖥️</div>
                            <div class="stat-info">
                                <h3>Total Clients</h3>
                                <div class="stat-value">${clientsData.total}</div>
                            </div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-icon online">✓</div>
                            <div class="stat-info">
                                <h3>Online</h3>
                                <div class="stat-value">${onlineCount}</div>
                            </div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-icon offline">✗</div>
                            <div class="stat-info">
                                <h3>Offline</h3>
                                <div class="stat-value">${offlineCount}</div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="card">
                        <div class="card-header">
                            <h2>Clients</h2>
                            <button class="btn btn-sm btn-primary" onclick="refreshClients()">
                                🔄 Refresh
                            </button>
                        </div>
                        <div class="card-body">
                            ${renderClientsTable(clientsData.clients)}
                        </div>
                    </div>
                </main>
            </div>
            ${renderModal()}
        `;

    state.currentPage = 'dashboard';
  } catch (error) {
    console.error('Dashboard error:', error);
    showLoginPage();
  }
}

function renderSidebar(user) {
  return `
        <aside class="sidebar">
            <div class="sidebar-header">
                <h2>🖥️ Agent Monitor</h2>
            </div>
            <nav class="sidebar-nav">
                <a href="#" class="nav-item active" onclick="showDashboard(); return false;">
                    <i>📊</i> Dashboard
                </a>
                <a href="#" class="nav-item" onclick="showClientsPage(); return false;">
                    <i>💻</i> Clients
                </a>
            </nav>
            <div class="sidebar-footer">
                <div class="user-info">
                    <span>👤 ${escapeHtml(user.username)}</span>
                </div>
                <button class="btn btn-sm btn-danger mt-1" onclick="logout()" style="width: 100%;">
                    Logout
                </button>
            </div>
        </aside>
    `;
}

function renderClientsTable(clients) {
  if (clients.length === 0) {
    return `
            <div class="empty-state">
                <i>📭</i>
                <h3>No clients found</h3>
                <p>Click "Add Client" to register your first agent.</p>
            </div>
        `;
  }

  return `
        <div class="table-responsive">
            <table class="table">
                <thead>
                    <tr>
                        <th>Hostname</th>
                        <th>Status</th>
                        <th>OS / Arch</th>
                        <th>Last Seen</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    ${clients.map(client => `
                        <tr>
                            <td>
                                <a href="#" onclick="showClientDetail('${client.id}'); return false;">
                                    <strong>${escapeHtml(client.hostname || 'Unnamed')}</strong>
                                </a>
                            </td>
                            <td>
                                <span class="badge ${getStatusClass(client.status)}">
                                    <span class="badge-dot"></span>
                                    ${client.status}
                                </span>
                            </td>
                            <td>${escapeHtml(client.os || '-')} / ${escapeHtml(client.arch || '-')}</td>
                            <td>${formatDate(client.last_seen)}</td>
                            <td>
                                <button class="btn btn-sm btn-primary" onclick="showClientDetail('${client.id}')">
                                    View
                                </button>
                                <button class="btn btn-sm btn-danger" onclick="confirmDeleteClient('${client.id}', '${escapeHtml(client.hostname || 'Unnamed')}')">
                                    Delete
                                </button>
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        </div>
    `;
}

function renderModal() {
  return `
        <div id="modalOverlay" class="modal-overlay">
            <div class="modal">
                <div class="modal-header">
                    <h3 id="modalTitle">Modal</h3>
                    <button class="modal-close" onclick="closeModal()">&times;</button>
                </div>
                <div class="modal-body" id="modalBody"></div>
                <div class="modal-footer" id="modalFooter"></div>
            </div>
        </div>
    `;
}

function showModal(title, body, footer = '') {
  document.getElementById('modalTitle').textContent = title;
  document.getElementById('modalBody').innerHTML = body;
  document.getElementById('modalFooter').innerHTML = footer;
  document.getElementById('modalOverlay').classList.add('active');
}

function closeModal() {
  document.getElementById('modalOverlay').classList.remove('active');
}

function showCreateClientModal() {
  const body = `
        <form id="createClientForm">
            <p style="color: var(--text-muted); margin-bottom: 1rem;">
                Create a new client registration. The client will automatically report its hostname, OS, and platform information when it connects.
            </p>
            <div class="form-group">
                <label for="clientName">Client Name (optional)</label>
                <input type="text" id="clientName" class="form-control" placeholder="Enter a friendly name for this client">
            </div>
        </form>
        <div id="createClientError" class="alert alert-danger mt-2" style="display: none;"></div>
    `;

  const footer = `
        <button class="btn" onclick="closeModal()">Cancel</button>
        <button class="btn btn-primary" onclick="handleCreateClient()">Create Client</button>
    `;

  showModal('Create New Client', body, footer);
}

async function handleCreateClient() {
  const clientName = document.getElementById('clientName').value;
  const errorDiv = document.getElementById('createClientError');

  try {
    const client = await createClient({
      hostname: clientName || null
    });

    closeModal();
    showClientCreatedModal(client);
  } catch (error) {
    errorDiv.textContent = error.message;
    errorDiv.style.display = 'block';
  }
}

function showClientCreatedModal(client) {
  const body = `
        <div class="alert alert-success">Client created successfully!</div>
        <div class="detail-item">
            <span class="detail-label">Client ID</span>
            <span class="detail-value"><code>${client.id}</code></span>
        </div>
        <div class="detail-item">
            <span class="detail-label">Client Token</span>
            <span class="detail-value"><code style="word-break: break-all;">${client.client_token}</code></span>
        </div>
        <p class="mt-2" style="color: var(--text-muted); font-size: 0.875rem;">
            ⚠️ Save the client token! You will need it to connect the agent.
        </p>
    `;

  const footer = `
        <button class="btn btn-primary" onclick="closeModal(); showDashboard();">Done</button>
    `;

  showModal('Client Created', body, footer);
}

function confirmDeleteClient(clientId, hostname) {
  const body = `
        <p>Are you sure you want to delete client <strong>${escapeHtml(hostname)}</strong>?</p>
        <p style="color: var(--danger-color);">This action cannot be undone.</p>
    `;

  const footer = `
        <button class="btn" onclick="closeModal()">Cancel</button>
        <button class="btn btn-danger" onclick="handleDeleteClient('${clientId}')">Delete</button>
    `;

  showModal('Delete Client', body, footer);
}

async function handleDeleteClient(clientId) {
  try {
    await deleteClient(clientId);
    closeModal();
    showDashboard();
  } catch (error) {
    alert('Failed to delete client: ' + error.message);
  }
}

async function showClientDetail(clientId) {
  try {
    showModal('Loading...', '<div class="loading"><div class="spinner"></div></div>', '');

    const client = await getClient(clientId);
    let inventory = null;

    try {
      inventory = await getInventory(clientId);
    } catch (e) {
      console.log('No inventory data available');
    }

    closeModal();

    document.querySelector('.main-content').innerHTML = `
            <div class="page-header">
                <h1>
                    <a href="#" onclick="showDashboard(); return false;" style="color: var(--text-muted); text-decoration: none;">←</a>
                    ${escapeHtml(client.hostname)}
                </h1>
                <span class="badge ${getStatusClass(client.status)}">
                    <span class="badge-dot"></span>
                    ${client.status}
                </span>
            </div>
            
            <div class="detail-grid">
                <div class="detail-section">
                    <h3>📋 Client Information</h3>
                    <div class="detail-item">
                        <span class="detail-label">Client ID</span>
                        <span class="detail-value"><code>${client.id}</code></span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Hostname</span>
                        <span class="detail-value">${escapeHtml(client.hostname)}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Operating System</span>
                        <span class="detail-value">${escapeHtml(client.os || '-')}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Platform</span>
                        <span class="detail-value">${escapeHtml(client.platform || '-')}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Architecture</span>
                        <span class="detail-value">${escapeHtml(client.arch || '-')}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Agent Version</span>
                        <span class="detail-value">${escapeHtml(client.agent_version || '-')}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Last Seen</span>
                        <span class="detail-value">${formatDate(client.last_seen)}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Created At</span>
                        <span class="detail-value">${formatDate(client.created_at)}</span>
                    </div>
                </div>
                
                ${inventory ? renderInventorySection(inventory) : `
                    <div class="detail-section">
                        <h3>📊 System Information</h3>
                        <div class="empty-state">
                            <p>No inventory data available yet.</p>
                            <p style="font-size: 0.875rem;">Data will appear once the agent connects.</p>
                        </div>
                    </div>
                `}
            </div>
            
            <div class="card mt-2">
                <div class="card-header">
                    <h2>🔧 Actions</h2>
                </div>
                <div class="card-body d-flex gap-1">
                    <button class="btn btn-primary" onclick="openTerminal('${client.id}', '${escapeHtml(client.hostname)}')" ${client.status !== 'online' ? 'disabled' : ''}>
                        🖥️ Open Terminal
                    </button>
                    <button class="btn btn-primary" onclick="handleRegenerateToken('${client.id}')">
                        🔄 Regenerate Token
                    </button>
                    <button class="btn btn-danger" onclick="confirmDeleteClient('${client.id}', '${escapeHtml(client.hostname)}')">
                        🗑️ Delete Client
                    </button>
                </div>
            </div>
            ${renderModal()}
        `;
  } catch (error) {
    closeModal();
    alert('Failed to load client details: ' + error.message);
  }
}

function renderInventorySection(inventory) {
  const memUsagePercent = Math.round((inventory.memory_used / inventory.memory_total) * 100);
  const diskUsagePercent = Math.round((inventory.disk_used / inventory.disk_total) * 100);

  const getProgressClass = (percent) => {
    if (percent < 50) return 'low';
    if (percent < 80) return 'medium';
    return 'high';
  };

  return `
        <div class="detail-section">
            <h3>💻 CPU</h3>
            <div class="detail-item">
                <span class="detail-label">CPU Cores</span>
                <span class="detail-value">${inventory.cpu_count || '-'}</span>
            </div>
            <div class="detail-item">
                <span class="detail-label">CPU Model</span>
                <span class="detail-value">${escapeHtml(inventory.cpu_model || '-')}</span>
            </div>
        </div>
        
        <div class="detail-section">
            <h3>🧠 Memory</h3>
            <div class="detail-item">
                <span class="detail-label">Total</span>
                <span class="detail-value">${formatBytes(inventory.memory_total)}</span>
            </div>
            <div class="detail-item">
                <span class="detail-label">Used</span>
                <span class="detail-value">${formatBytes(inventory.memory_used)} (${memUsagePercent}%)</span>
            </div>
            <div class="progress">
                <div class="progress-bar ${getProgressClass(memUsagePercent)}" style="width: ${memUsagePercent}%;"></div>
            </div>
        </div>
        
        <div class="detail-section">
            <h3>💾 Disk</h3>
            <div class="detail-item">
                <span class="detail-label">Total</span>
                <span class="detail-value">${formatBytes(inventory.disk_total)}</span>
            </div>
            <div class="detail-item">
                <span class="detail-label">Used</span>
                <span class="detail-value">${formatBytes(inventory.disk_used)} (${diskUsagePercent}%)</span>
            </div>
            <div class="detail-item">
                <span class="detail-label">Free</span>
                <span class="detail-value">${formatBytes(inventory.disk_free)}</span>
            </div>
            <div class="progress">
                <div class="progress-bar ${getProgressClass(diskUsagePercent)}" style="width: ${diskUsagePercent}%;"></div>
            </div>
        </div>
        
        <div class="detail-section">
            <h3>🌐 Network</h3>
            <div class="detail-item">
                <span class="detail-label">IP Addresses</span>
                <span class="detail-value" style="max-width: 200px; word-break: break-word;">
                    ${(inventory.ip_addresses || []).slice(0, 5).join('<br>') || '-'}
                    ${(inventory.ip_addresses || []).length > 5 ? '<br>...' : ''}
                </span>
            </div>
            <div class="detail-item">
                <span class="detail-label">Last Updated</span>
                <span class="detail-value">${formatDate(inventory.collected_at)}</span>
            </div>
        </div>
    `;
}

async function handleRegenerateToken(clientId) {
  if (!confirm('Are you sure you want to regenerate the client token? The current agent will need to be reconfigured.')) {
    return;
  }

  try {
    const client = await regenerateToken(clientId);

    const body = `
            <div class="alert alert-success">Token regenerated successfully!</div>
            <div class="detail-item">
                <span class="detail-label">New Client Token</span>
                <span class="detail-value"><code style="word-break: break-all;">${client.client_token}</code></span>
            </div>
            <p class="mt-2" style="color: var(--text-muted); font-size: 0.875rem;">
                ⚠️ Update your agent configuration with this new token.
            </p>
        `;

    showModal('Token Regenerated', body, '<button class="btn btn-primary" onclick="closeModal()">Done</button>');
  } catch (error) {
    alert('Failed to regenerate token: ' + error.message);
  }
}

async function refreshClients() {
  try {
    await showDashboard();
  } catch (error) {
    alert('Failed to refresh: ' + error.message);
  }
}

async function showClientsPage() {
  await showDashboard();
}

// ============================================
// Terminal Functionality
// ============================================

// Terminal state
const terminalState = {
  terminal: null,
  websocket: null,
  sessionId: null,
  fitAddon: null,
  clientId: null,
  hostname: null
};

// Load xterm.js dynamically
function loadXterm() {
  return new Promise((resolve, reject) => {
    // Check if already loaded
    if (window.Terminal) {
      resolve();
      return;
    }

    // Load xterm.css
    const css = document.createElement('link');
    css.rel = 'stylesheet';
    css.href = 'https://cdn.jsdelivr.net/npm/xterm@5.3.0/css/xterm.css';
    document.head.appendChild(css);

    // Load xterm.js
    const script = document.createElement('script');
    script.src = 'https://cdn.jsdelivr.net/npm/xterm@5.3.0/lib/xterm.min.js';
    script.onload = () => {
      // Load fit addon
      const fitScript = document.createElement('script');
      fitScript.src = 'https://cdn.jsdelivr.net/npm/xterm-addon-fit@0.8.0/lib/xterm-addon-fit.min.js';
      fitScript.onload = () => resolve();
      fitScript.onerror = () => reject(new Error('Failed to load xterm-addon-fit'));
      document.head.appendChild(fitScript);
    };
    script.onerror = () => reject(new Error('Failed to load xterm.js'));
    document.head.appendChild(script);
  });
}

async function openTerminal(clientId, hostname) {
  try {
    // Load xterm if not loaded
    await loadXterm();

    terminalState.clientId = clientId;
    terminalState.hostname = hostname;

    // Create terminal overlay
    const overlay = document.createElement('div');
    overlay.id = 'terminalOverlay';
    overlay.className = 'terminal-overlay';
    overlay.innerHTML = `
      <div class="terminal-container">
        <div class="terminal-header">
          <span>🖥️ Terminal - ${escapeHtml(hostname)}</span>
          <button class="terminal-close" onclick="closeTerminal()">&times;</button>
        </div>
        <div id="terminalContainer" class="terminal-body"></div>
        <div class="terminal-status" id="terminalStatus">Connecting...</div>
      </div>
    `;
    document.body.appendChild(overlay);

    // Create terminal instance
    terminalState.terminal = new Terminal({
      cursorBlink: true,
      fontSize: 14,
      fontFamily: 'Monaco, Menlo, "Ubuntu Mono", Consolas, monospace',
      theme: {
        background: '#1e1e1e',
        foreground: '#d4d4d4',
        cursor: '#aeafad',
        black: '#000000',
        red: '#cd3131',
        green: '#0dbc79',
        yellow: '#e5e510',
        blue: '#2472c8',
        magenta: '#bc3fbc',
        cyan: '#11a8cd',
        white: '#e5e5e5',
        brightBlack: '#666666',
        brightRed: '#f14c4c',
        brightGreen: '#23d18b',
        brightYellow: '#f5f543',
        brightBlue: '#3b8eea',
        brightMagenta: '#d670d6',
        brightCyan: '#29b8db',
        brightWhite: '#e5e5e5'
      }
    });

    // Fit addon
    terminalState.fitAddon = new FitAddon.FitAddon();
    terminalState.terminal.loadAddon(terminalState.fitAddon);

    // Open terminal in container
    terminalState.terminal.open(document.getElementById('terminalContainer'));
    terminalState.fitAddon.fit();

    // Connect WebSocket
    connectTerminalWebSocket(clientId);

    // Handle terminal input
    terminalState.terminal.onData((data) => {
      if (terminalState.websocket && terminalState.websocket.readyState === WebSocket.OPEN) {
        terminalState.websocket.send(JSON.stringify({
          type: 'input',
          data: data
        }));
      }
    });

    // Handle resize
    terminalState.terminal.onResize(({ cols, rows }) => {
      if (terminalState.websocket && terminalState.websocket.readyState === WebSocket.OPEN) {
        terminalState.websocket.send(JSON.stringify({
          type: 'resize',
          cols: cols,
          rows: rows
        }));
      }
    });

    // Window resize handler
    window.addEventListener('resize', handleTerminalResize);

  } catch (error) {
    console.error('Failed to open terminal:', error);
    alert('Failed to open terminal: ' + error.message);
  }
}

function connectTerminalWebSocket(clientId) {
  const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${wsProtocol}//${window.location.host}/ws/terminal/${clientId}?token=${state.token}`;

  terminalState.websocket = new WebSocket(wsUrl);

  terminalState.websocket.onopen = () => {
    updateTerminalStatus('Connected, initializing...');
    // Send init message with terminal size
    const { cols, rows } = terminalState.fitAddon.proposeDimensions() || { cols: 80, rows: 24 };
    terminalState.websocket.send(JSON.stringify({
      cols: cols,
      rows: rows,
      shell: ''
    }));
  };

  terminalState.websocket.onmessage = (event) => {
    try {
      const message = JSON.parse(event.data);
      handleTerminalMessage(message);
    } catch (e) {
      console.error('Failed to parse terminal message:', e);
    }
  };

  terminalState.websocket.onerror = (error) => {
    console.error('Terminal WebSocket error:', error);
    updateTerminalStatus('Connection error', true);
  };

  terminalState.websocket.onclose = (event) => {
    console.log('Terminal WebSocket closed:', event.code, event.reason);
    updateTerminalStatus('Disconnected', true);
    if (terminalState.terminal) {
      terminalState.terminal.write('\r\n\x1b[31m[Connection closed]\x1b[0m\r\n');
    }
  };
}

function handleTerminalMessage(message) {
  switch (message.type) {
    case 'terminal_ready':
      terminalState.sessionId = message.session_id;
      updateTerminalStatus('Terminal ready');
      terminalState.terminal.focus();
      break;

    case 'terminal_output':
      if (terminalState.terminal && message.output) {
        terminalState.terminal.write(message.output);
      }
      break;

    case 'terminal_error':
      updateTerminalStatus(`Error: ${message.error}`, true);
      terminalState.terminal.write(`\r\n\x1b[31m[Error: ${message.error}]\x1b[0m\r\n`);
      break;

    case 'terminal_closed':
      updateTerminalStatus('Session closed', true);
      terminalState.terminal.write('\r\n\x1b[33m[Session closed]\x1b[0m\r\n');
      break;

    default:
      console.log('Unknown terminal message type:', message.type);
  }
}

function updateTerminalStatus(text, isError = false) {
  const statusEl = document.getElementById('terminalStatus');
  if (statusEl) {
    statusEl.textContent = text;
    statusEl.style.color = isError ? 'var(--danger-color)' : 'var(--text-muted)';
  }
}

function handleTerminalResize() {
  if (terminalState.fitAddon) {
    terminalState.fitAddon.fit();
  }
}

function closeTerminal() {
  // Send close message
  if (terminalState.websocket && terminalState.websocket.readyState === WebSocket.OPEN) {
    terminalState.websocket.send(JSON.stringify({ type: 'close' }));
    terminalState.websocket.close();
  }

  // Dispose terminal
  if (terminalState.terminal) {
    terminalState.terminal.dispose();
    terminalState.terminal = null;
  }

  // Remove resize listener
  window.removeEventListener('resize', handleTerminalResize);

  // Remove overlay
  const overlay = document.getElementById('terminalOverlay');
  if (overlay) {
    overlay.remove();
  }

  // Reset state
  terminalState.websocket = null;
  terminalState.sessionId = null;
  terminalState.fitAddon = null;
  terminalState.clientId = null;
  terminalState.hostname = null;
}

// Initialize
document.addEventListener('DOMContentLoaded', async () => {
  if (state.token) {
    try {
      await showDashboard();
    } catch (error) {
      showLoginPage();
    }
  } else {
    showLoginPage();
  }
});

// Auto-refresh every 30 seconds
setInterval(async () => {
  if (state.token && state.currentPage === 'dashboard') {
    try {
      const clientsData = await getClients();
      const tableBody = document.querySelector('.table tbody');
      if (tableBody && clientsData.clients.length > 0) {
        // Only update the table body rows, not the entire table
        tableBody.innerHTML = clientsData.clients.map(client => `
          <tr>
            <td>
              <a href="#" onclick="showClientDetail('${client.id}'); return false;">
                <strong>${escapeHtml(client.hostname || 'Unnamed')}</strong>
              </a>
            </td>
            <td>
              <span class="badge ${getStatusClass(client.status)}">
                <span class="badge-dot"></span>
                ${client.status}
              </span>
            </td>
            <td>${escapeHtml(client.os || '-')} / ${escapeHtml(client.arch || '-')}</td>
            <td>${formatDate(client.last_seen)}</td>
            <td>
              <button class="btn btn-sm btn-primary" onclick="showClientDetail('${client.id}')">
                View
              </button>
              <button class="btn btn-sm btn-danger" onclick="confirmDeleteClient('${client.id}', '${escapeHtml(client.hostname || 'Unnamed')}')">
                Delete
              </button>
            </td>
          </tr>
        `).join('');
      }

      // Also update stats
      const onlineCount = clientsData.clients.filter(c => c.status === 'online').length;
      const offlineCount = clientsData.total - onlineCount;
      const statValues = document.querySelectorAll('.stat-value');
      if (statValues.length >= 3) {
        statValues[0].textContent = clientsData.total;
        statValues[1].textContent = onlineCount;
        statValues[2].textContent = offlineCount;
      }
    } catch (error) {
      console.error('Auto-refresh error:', error);
    }
  }
}, 30000);
