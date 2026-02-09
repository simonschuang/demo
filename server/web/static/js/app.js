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
  currentPage: 'dashboard',
  detailPollInterval: null,
  detailPollTimer: null,
  currentClientId: null
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

// Copy to clipboard utility function
function copyToClipboard(elementId) {
  const el = document.getElementById(elementId);
  if (!el) return;
  const text = el.textContent;
  if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
    navigator.clipboard.writeText(text).then(() => {
      el.style.background = '#e0ffe0';
      setTimeout(() => { el.style.background = ''; }, 500);
    }).catch(() => fallbackCopyTextToClipboard(text, el));
  } else {
    fallbackCopyTextToClipboard(text, el);
  }
}

function fallbackCopyTextToClipboard(text, el) {
  const textarea = document.createElement('textarea');
  textarea.value = text;
  document.body.appendChild(textarea);
  textarea.select();
  try {
    document.execCommand('copy');
    el.style.background = '#e0ffe0';
    setTimeout(() => { el.style.background = ''; }, 500);
  } catch (err) {
    alert('Copy failed');
  }
  document.body.removeChild(textarea);
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

async function getPowerHistory(clientId, hours = 24) {
  return await apiRequest(`/inventory/${clientId}/power/history?hours=${hours}`);
}

// Version Functions
async function getServerVersion() {
  try {
    return await apiRequest('/version');
  } catch (e) {
    return { version: 'unknown' };
  }
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
  // Stop any detail page polling when navigating away
  stopDetailPolling();
  state.currentClientId = null;

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

    // Load version info
    loadVersionInfo();
  } catch (error) {
    console.error('Dashboard error:', error);
    showLoginPage();
  }
}

async function loadVersionInfo() {
  const versionEl = document.getElementById('versionInfo');
  if (versionEl) {
    const version = await getServerVersion();
    versionEl.textContent = `Server v${version.version}`;
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
                <div id="versionInfo" style="margin-top: 0.5rem; font-size: 0.75rem; color: var(--text-muted); text-align: center;"></div>
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
                <input type="text" id="clientName" class="form-control" placeholder="Enter a friendly name for this client" autofocus>
            </div>
        </form>
        <div id="createClientError" class="alert alert-danger mt-2" style="display: none;"></div>
    `;

  const footer = `
        <button class="btn" onclick="closeModal()">Cancel</button>
        <button class="btn btn-primary" id="createClientBtn" type="button">Create Client</button>
    `;

  showModal('Create New Client', body, footer);


  // Autofocus the input after modal is visible
  setTimeout(() => {
    const input = document.getElementById('clientName');
    if (input) {
      input.focus();
      // Fallback: try again after a short delay in case modal animation delays rendering
      setTimeout(() => {
        if (document.activeElement !== input) input.focus();
      }, 100);
    }
  }, 10);

  // Submit on Enter key
  const form = document.getElementById('createClientForm');
  if (form) {
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      handleCreateClient();
    });
  }
  // Also allow button click
  const btn = document.getElementById('createClientBtn');
  if (btn) {
    btn.addEventListener('click', handleCreateClient);
  }
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
        <span class="detail-value">
          <code id="clientIdValue">${client.id}</code>
          <button class="copy-btn" title="Copy Client ID" onclick="copyToClipboard('clientIdValue')" style="margin-left: 0.5em; border: none; background: none; cursor: pointer; font-size: 1em;">
            📋
          </button>
        </span>
      </div>
      <div class="detail-item">
        <span class="detail-label">Client Token</span>
        <span class="detail-value">
          <code id="clientTokenValue" style="word-break: break-all;">${client.client_token}</code>
          <button class="copy-btn" title="Copy Client Token" onclick="copyToClipboard('clientTokenValue')" style="margin-left: 0.5em; border: none; background: none; cursor: pointer; font-size: 1em;">
            📋
          </button>
        </span>
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

    // Set current page to prevent auto-refresh from overwriting content
    state.currentPage = 'client-detail';

    // Store current client ID for polling
    state.currentClientId = clientId;

    document.querySelector('.main-content').innerHTML = `
            <div class="page-header">
                <h1>
                    <a href="#" onclick="stopDetailPolling(); showDashboard(); return false;" style="color: var(--text-muted); text-decoration: none;">←</a>
                    ${escapeHtml(client.hostname)}
                </h1>
                <div style="display: flex; align-items: center; gap: 1rem;">
                    <div style="display: flex; align-items: center; gap: 0.5rem;">
                        <label for="pollInterval" style="font-size: 0.875rem; color: var(--text-muted);">Auto-refresh:</label>
                        <select id="pollInterval" class="form-control" style="width: auto; padding: 0.25rem 0.5rem; font-size: 0.875rem;" onchange="setDetailPollingInterval(this.value, '${clientId}')">
                            <option value="0">Off</option>
                            <option value="5000">5s</option>
                            <option value="10000">10s</option>
                            <option value="30000">30s</option>
                            <option value="60000">60s</option>
                        </select>
                        <span id="pollStatus" style="font-size: 0.75rem; color: var(--text-muted);"></span>
                    </div>
                    <span class="badge ${getStatusClass(client.status)}">
                        <span class="badge-dot"></span>
                        ${client.status}
                    </span>
                </div>
            </div>
            
            <div class="detail-grid">
                <div class="detail-section" style="grid-column: 1 / -1;">
                    <h3>📋 Client Information</h3>
                    <div class="detail-grid" style="grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));">
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
                            <span class="detail-label">Registered At</span>
                            <span class="detail-value">${formatDate(client.registered_at)}</span>
                        </div>
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
            
            <div class="card mt-2">
                <div class="card-header">
                    <h2>🔑 Client Credentials</h2>
                </div>
                <div class="card-body">
                    <div class="detail-item">
                        <span class="detail-label">Client ID</span>
                        <span class="detail-value">
                            <code id="detailClientId">${client.id}</code>
                            <button class="copy-btn" title="Copy Client ID" onclick="copyToClipboard('detailClientId')" style="margin-left: 0.5em; border: none; background: none; cursor: pointer; font-size: 1em;">
                              📋
                            </button>
                        </span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Client Token</span>
                        <span class="detail-value">
                            <code id="detailClientToken" style="word-break: break-all;">${client.client_token || '••••••••'}</code>
                            ${client.client_token ? `
                            <button class="copy-btn" title="Copy Client Token" onclick="copyToClipboard('detailClientToken')" style="margin-left: 0.5em; border: none; background: none; cursor: pointer; font-size: 1em;">
                              📋
                            </button>
                            ` : '<span style="color: var(--text-muted); font-size: 0.875rem; margin-left: 0.5em;">(Use "Regenerate Token" to get a new token)</span>'}
                        </span>
                    </div>
                </div>
            </div>
            ${renderModal()}
        `;

    // Load power chart if inventory data exists
    if (inventory) {
      loadPowerChart(clientId);
    }

    // Restore polling interval if previously set
    if (state.detailPollInterval) {
      const select = document.getElementById('pollInterval');
      if (select) {
        select.value = state.detailPollInterval;
        startDetailPolling(state.detailPollInterval, clientId);
      }
    }
  } catch (error) {
    closeModal();
    alert('Failed to load client details: ' + error.message);
  }
}

// Polling functions for client detail page
function setDetailPollingInterval(interval, clientId) {
  state.detailPollInterval = parseInt(interval);
  stopDetailPolling();

  if (state.detailPollInterval > 0) {
    startDetailPolling(state.detailPollInterval, clientId);
  } else {
    updatePollStatus('');
  }
}

function startDetailPolling(interval, clientId) {
  stopDetailPolling();

  if (interval > 0 && state.currentPage === 'client-detail') {
    updatePollStatus('Polling...');
    state.detailPollTimer = setInterval(async () => {
      if (state.currentPage !== 'client-detail' || state.currentClientId !== clientId) {
        stopDetailPolling();
        return;
      }
      await refreshInventoryData(clientId);
    }, interval);
  }
}

function stopDetailPolling() {
  if (state.detailPollTimer) {
    clearInterval(state.detailPollTimer);
    state.detailPollTimer = null;
  }
  updatePollStatus('');
}

function updatePollStatus(text) {
  const statusEl = document.getElementById('pollStatus');
  if (statusEl) {
    statusEl.textContent = text;
  }
}

async function refreshInventoryData(clientId) {
  try {
    updatePollStatus('Refreshing...');
    const inventory = await getInventory(clientId);

    // Update the inventory sections in place
    const detailGrid = document.querySelector('.detail-grid');
    if (detailGrid && inventory) {
      // Keep the first detail-section (Client Information) and replace the rest
      const clientInfoSection = detailGrid.querySelector('.detail-section');
      detailGrid.innerHTML = '';
      if (clientInfoSection) {
        detailGrid.appendChild(clientInfoSection);
      }
      detailGrid.innerHTML += renderInventorySection(inventory);

      // Reload power chart after refreshing inventory
      loadPowerChart(clientId);
    }

    updatePollStatus(`Last updated: ${new Date().toLocaleTimeString()}`);
  } catch (e) {
    console.error('Failed to refresh inventory:', e);
    updatePollStatus('Refresh failed');
  }
}

function renderInventorySection(inventory) {
  const memUsagePercent = inventory.memory_total ? Math.round((inventory.memory_used / inventory.memory_total) * 100) : 0;
  const diskUsagePercent = inventory.disk_total ? Math.round((inventory.disk_used / inventory.disk_total) * 100) : 0;

  const getProgressClass = (percent) => {
    if (percent < 50) return 'low';
    if (percent < 80) return 'medium';
    return 'high';
  };

  const getHealthBadge = (status) => {
    if (!status) return '';
    const statusLower = status.toLowerCase();
    if (statusLower === 'ok' || statusLower === 'healthy') {
      return `<span class="badge badge-online">${escapeHtml(status)}</span>`;
    } else if (statusLower === 'warning') {
      return `<span class="badge" style="background: var(--warning-color); color: #000;">${escapeHtml(status)}</span>`;
    } else {
      return `<span class="badge badge-offline">${escapeHtml(status)}</span>`;
    }
  };

  let bmcSection = '';
  if (inventory.bmc) {
    const bmc = inventory.bmc;

    // BMC System Info Section
    bmcSection += `
        <div class="detail-section" style="grid-column: 1 / -1;">
            <h3>🖥️ BMC / Hardware Information</h3>
            <div class="detail-grid" style="grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));">
                <div class="detail-item">
                    <span class="detail-label">BMC Type</span>
                    <span class="detail-value">${escapeHtml(bmc.bmc_type || '-')}</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">BMC Version</span>
                    <span class="detail-value">${escapeHtml(bmc.bmc_version || '-')}</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">BMC IP</span>
                    <span class="detail-value">${escapeHtml(bmc.bmc_ip || '-')}</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">Manufacturer</span>
                    <span class="detail-value">${escapeHtml(bmc.manufacturer || '-')}</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">Model</span>
                    <span class="detail-value">${escapeHtml(bmc.model || '-')}</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">Serial Number</span>
                    <span class="detail-value">${escapeHtml(bmc.serial_number || '-')}</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">SKU</span>
                    <span class="detail-value">${escapeHtml(bmc.sku || '-')}</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">BIOS Version</span>
                    <span class="detail-value">${escapeHtml(bmc.bios_version || '-')}</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">Power State</span>
                    <span class="detail-value">${escapeHtml(bmc.power_state || '-')}</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">Power Consumption</span>
                    <span class="detail-value">${bmc.power_consumed_watts ? bmc.power_consumed_watts + ' W' : '-'}</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">Health Status</span>
                    <span class="detail-value">${getHealthBadge(bmc.health_status) || '-'}</span>
                </div>
            </div>
        </div>
    `;

    // Memory Modules Section
    if (bmc.memory_modules && bmc.memory_modules.length > 0) {
      const totalMemoryMiB = bmc.memory_modules.reduce((sum, m) => sum + (m.capacity_mib || 0), 0);
      bmcSection += `
        <div class="detail-section" style="grid-column: 1 / -1;">
            <h3>🧠 Memory Modules (${bmc.memory_modules.length} DIMMs, Total: ${formatBytes(totalMemoryMiB * 1024 * 1024)})</h3>
            <div class="table-responsive">
                <table class="table" style="font-size: 0.85rem;">
                    <thead>
                        <tr>
                            <th>Slot</th>
                            <th>Manufacturer</th>
                            <th>Part Number</th>
                            <th>Capacity</th>
                            <th>Speed</th>
                            <th>Type</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${bmc.memory_modules.map(mem => `
                            <tr>
                                <td>${escapeHtml(mem.id || '-')}</td>
                                <td>${escapeHtml(mem.manufacturer || '-')}</td>
                                <td>${escapeHtml(mem.part_number || '-')}</td>
                                <td>${mem.capacity_mib ? formatBytes(mem.capacity_mib * 1024 * 1024) : '-'}</td>
                                <td>${mem.speed_mhz ? mem.speed_mhz + ' MHz' : '-'}</td>
                                <td>${escapeHtml(mem.memory_type || '-')}</td>
                                <td>${getHealthBadge(mem.status) || '-'}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        </div>
      `;
    }

    // Temperature Sensors Section
    if (bmc.temperatures && bmc.temperatures.length > 0) {
      bmcSection += `
        <div class="detail-section">
            <h3>🌡️ Temperature Sensors</h3>
            <div class="table-responsive">
                <table class="table" style="font-size: 0.85rem;">
                    <thead>
                        <tr>
                            <th>Sensor</th>
                            <th>Reading</th>
                            <th>Threshold</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${bmc.temperatures.map(temp => {
        const reading = temp.reading_celsius;
        const threshold = temp.upper_threshold || temp.critical_threshold;
        let tempClass = '';
        if (reading && threshold) {
          if (reading >= threshold * 0.9) tempClass = 'style="color: var(--danger-color);"';
          else if (reading >= threshold * 0.7) tempClass = 'style="color: var(--warning-color);"';
        }
        return `
                            <tr>
                                <td>${escapeHtml(temp.name || temp.id || '-')}</td>
                                <td ${tempClass}>${reading !== null && reading !== undefined ? reading.toFixed(1) + ' °C' : '-'}</td>
                                <td>${threshold ? threshold.toFixed(1) + ' °C' : '-'}</td>
                                <td>${getHealthBadge(temp.status) || '-'}</td>
                            </tr>
                          `;
      }).join('')}
                    </tbody>
                </table>
            </div>
        </div>
      `;
    }

    // Fan Speed Section
    if (bmc.fans && bmc.fans.length > 0) {
      bmcSection += `
        <div class="detail-section">
            <h3>🌀 Fan Status</h3>
            <div class="table-responsive">
                <table class="table" style="font-size: 0.85rem;">
                    <thead>
                        <tr>
                            <th>Fan</th>
                            <th>Speed</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${bmc.fans.map(fan => `
                            <tr>
                                <td>${escapeHtml(fan.name || fan.id || '-')}</td>
                                <td>${fan.speed_rpm ? fan.speed_rpm + ' RPM' : (fan.speed_percent ? fan.speed_percent + '%' : '-')}</td>
                                <td>${getHealthBadge(fan.status) || '-'}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        </div>
      `;
    }

    // Storage Section
    if (bmc.storage && bmc.storage.length > 0) {
      bmcSection += `
        <div class="detail-section" style="grid-column: 1 / -1;">
            <h3>💿 Storage (BMC)</h3>
            <div class="table-responsive">
                <table class="table" style="font-size: 0.85rem;">
                    <thead>
                        <tr>
                            <th>Drive</th>
                            <th>Model</th>
                            <th>Manufacturer</th>
                            <th>Capacity</th>
                            <th>Type</th>
                            <th>Protocol</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${bmc.storage.map(drive => `
                            <tr>
                                <td>${escapeHtml(drive.name || drive.id || '-')}</td>
                                <td>${escapeHtml(drive.model || '-')}</td>
                                <td>${escapeHtml(drive.manufacturer || '-')}</td>
                                <td>${drive.capacity_gb ? drive.capacity_gb + ' GB' : '-'}</td>
                                <td>${escapeHtml(drive.media_type || '-')}</td>
                                <td>${escapeHtml(drive.protocol || '-')}</td>
                                <td>${getHealthBadge(drive.status) || '-'}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        </div>
      `;
    }
  }

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
        
        <div class="detail-section" style="grid-column: 1 / -1;">
            <h3>⚡ Power Consumption</h3>
            <div id="powerChartContainer" style="position: relative; min-height: 200px;">
                <div style="display: flex; align-items: center; justify-content: center; height: 200px; color: var(--text-muted);">
                    Loading chart...
                </div>
            </div>
        </div>
        
        ${bmcSection}
    `;
}

// Power consumption chart instance
let powerChart = null;
let powerChartData = null; // Store data for download

function downloadPowerData() {
  if (!powerChartData || powerChartData.length === 0) {
    alert('No power data available to download');
    return;
  }

  // Create CSV content
  let csv = 'Date,Watts\n';
  powerChartData.forEach(d => {
    const date = new Date(d.timestamp);
    const dateStr = date.toString().replace(/\s*\(.*\)/, '').replace(/GMT.*$/, '').trim();
    csv += `${dateStr},${d.power_watts}\n`;
  });

  // Create download
  const blob = new Blob([csv], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `power_consumption_${new Date().toISOString().split('T')[0]}.csv`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

async function loadPowerChart(clientId, hours = 24) {
  const chartContainer = document.getElementById('powerChartContainer');

  if (!chartContainer) {
    return;
  }

  try {
    // Show loading state
    chartContainer.innerHTML = `
      <canvas id="powerChart" style="max-height: 300px;"></canvas>
      <div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); color: var(--text-muted);">
        Loading power data...
      </div>
    `;

    const data = await getPowerHistory(clientId, hours);

    if (!data.data || data.data.length === 0) {
      powerChartData = null;
      chartContainer.innerHTML = `
        <div style="display: flex; align-items: center; justify-content: center; height: 200px; color: var(--text-muted);">
          No power consumption data available yet
        </div>
      `;
      return;
    }

    // Store data for download
    powerChartData = data.data;

    // Prepare chart data
    const labels = data.data.map(d => {
      const date = new Date(d.timestamp);
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    });
    const powerValues = data.data.map(d => d.power_watts);

    // Calculate stats
    const avgPower = Math.round(powerValues.reduce((a, b) => a + b, 0) / powerValues.length);
    const minPower = Math.min(...powerValues);
    const maxPower = Math.max(...powerValues);

    // Restore canvas
    chartContainer.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
        <div style="font-size: 0.85rem; color: var(--text-muted);">
          Avg: <strong>${avgPower}W</strong> | Min: <strong>${minPower}W</strong> | Max: <strong>${maxPower}W</strong>
        </div>
        <div style="display: flex; align-items: center; gap: 0.5rem;">
          <button class="btn btn-sm" onclick="downloadPowerData()" title="Download CSV">📥 Download</button>
          <select id="powerChartHours" class="form-control" style="width: auto; padding: 0.25rem 0.5rem; font-size: 0.85rem;" onchange="loadPowerChart('${clientId}', parseInt(this.value))">
            <option value="1" ${hours === 1 ? 'selected' : ''}>Last 1 hour</option>
            <option value="6" ${hours === 6 ? 'selected' : ''}>Last 6 hours</option>
            <option value="24" ${hours === 24 ? 'selected' : ''}>Last 24 hours</option>
            <option value="168" ${hours === 168 ? 'selected' : ''}>Last 7 days</option>
          </select>
        </div>
      </div>
      <canvas id="powerChart" style="max-height: 250px;"></canvas>
    `;

    const ctx = document.getElementById('powerChart').getContext('2d');

    // Destroy existing chart if any
    if (powerChart) {
      powerChart.destroy();
    }

    powerChart = new Chart(ctx, {
      type: 'line',
      data: {
        labels: labels,
        datasets: [{
          label: 'Power Consumption (W)',
          data: powerValues,
          borderColor: '#3b82f6',
          backgroundColor: 'rgba(59, 130, 246, 0.1)',
          borderWidth: 2,
          fill: true,
          tension: 0.3,
          pointRadius: data.data.length > 100 ? 0 : 2,
          pointHoverRadius: 4
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
          intersect: false,
          mode: 'index'
        },
        plugins: {
          legend: {
            display: false
          },
          tooltip: {
            backgroundColor: 'rgba(0, 0, 0, 0.8)',
            padding: 10,
            callbacks: {
              label: function (context) {
                return `Power: ${context.raw}W`;
              }
            }
          }
        },
        scales: {
          x: {
            display: true,
            title: {
              display: true,
              text: 'Time',
              color: 'rgba(255, 255, 255, 0.8)',
              font: {
                size: 12
              }
            },
            grid: {
              color: 'rgba(255, 255, 255, 0.1)'
            },
            ticks: {
              color: 'rgba(255, 255, 255, 0.6)',
              maxTicksLimit: 10
            }
          },
          y: {
            display: true,
            title: {
              display: true,
              text: 'Power (Watts)',
              color: 'rgba(255, 255, 255, 0.8)',
              font: {
                size: 12
              }
            },
            grid: {
              color: 'rgba(255, 255, 255, 0.1)'
            },
            ticks: {
              color: 'rgba(255, 255, 255, 0.6)',
              callback: function (value) {
                return value + 'W';
              }
            }
          }
        }
      }
    });
  } catch (error) {
    console.error('Failed to load power chart:', error);
    chartContainer.innerHTML = `
      <div style="display: flex; align-items: center; justify-content: center; height: 200px; color: var(--text-muted);">
        Failed to load power data
      </div>
    `;
  }
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
