// Main State Manager
const state = {
    running: false,
    whitelist: {
        allow_all: true,
        allowed_threads: [],
        allowed_names: []
    },
    pollInterval: null
};

// DOM Nodes
const nodes = {
    tabs: document.querySelectorAll('.nav-item'),
    panes: document.querySelectorAll('.tab-pane'),
    botBadge: document.getElementById('bot-badge'),
    btnStart: document.getElementById('btn-start'),
    btnStop: document.getElementById('btn-stop'),
    consoleOutput: document.getElementById('console-output'),
    btnClearConsole: document.getElementById('btn-clear-console'),
    infoProfile: document.getElementById('info-profile'),
    infoModel: document.getElementById('info-model'),
    
    // Forms & Settings
    settingsForm: document.getElementById('settings-form'),
    whitelistAllowAll: document.getElementById('whitelist-allow-all'),
    
    // Whitelist management
    addNameInput: document.getElementById('add-name-input'),
    btnAddName: document.getElementById('btn-add-name'),
    listNames: document.getElementById('list-names'),
    
    addThreadInput: document.getElementById('add-thread-input'),
    btnAddThread: document.getElementById('btn-add-thread'),
    listThreads: document.getElementById('list-threads'),
    
    // History
    historyTableBody: document.getElementById('history-table-body'),
    btnRefreshHistory: document.getElementById('btn-refresh-history'),
    
    // Notification Toast
    toast: document.getElementById('toast'),
    toastMessage: document.getElementById('toast-message')
};

// Initialize Application
document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    loadConfiguration();
    loadWhitelist();
    loadHistory();
    
    // Start status polling
    pollStatus();
    state.pollInterval = setInterval(pollStatus, 2500);
    
    // Register actions
    nodes.btnStart.addEventListener('click', startBot);
    nodes.btnStop.addEventListener('click', stopBot);
    nodes.btnClearConsole.addEventListener('click', () => nodes.consoleOutput.innerText = 'Nhật ký đã xóa...');
    
    nodes.settingsForm.addEventListener('submit', saveConfiguration);
    nodes.whitelistAllowAll.addEventListener('change', toggleWhitelistMode);
    
    nodes.btnAddName.addEventListener('click', addWhitelistName);
    nodes.btnAddThread.addEventListener('click', addWhitelistThread);
    
    nodes.btnRefreshHistory.addEventListener('click', loadHistory);
    
    // Auto-poll history every 10 seconds
    setInterval(loadHistory, 10000);
});

// Tab Switching Routing
function initTabs() {
    nodes.tabs.forEach(tab => {
        tab.addEventListener('click', (e) => {
            e.preventDefault();
            const tabId = tab.getAttribute('data-tab');
            
            // Set active class
            nodes.tabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            
            // Show corresponding pane
            nodes.panes.forEach(pane => {
                if (pane.id === `tab-${tabId}`) {
                    pane.classList.add('active');
                } else {
                    pane.classList.remove('active');
                }
            });
            
            // Tab specific triggers
            if (tabId === 'history') {
                loadHistory();
            }
        });
    });
}

// Show Toast notification
function showToast(message, type = 'success') {
    nodes.toastMessage.innerText = message;
    nodes.toast.className = 'toast'; // reset class
    if (type === 'error') {
        nodes.toast.classList.add('bg-rose');
    }
    nodes.toast.classList.remove('hidden');
    
    setTimeout(() => {
        nodes.toast.classList.add('hidden');
    }, 3000);
}

// Poll status of the chatbot thread
async function pollStatus() {
    try {
        const response = await fetch('/api/status');
        const data = await response.json();
        
        state.running = data.running;
        
        // Update badge
        if (state.running) {
            nodes.botBadge.className = 'badge status-running';
            nodes.botBadge.innerHTML = '<span class="dot"></span> Đang Chạy';
            nodes.btnStart.disabled = true;
            nodes.btnStop.disabled = false;
        } else {
            nodes.botBadge.className = 'badge status-stopped';
            nodes.botBadge.innerHTML = '<span class="dot"></span> Đang Dừng';
            nodes.btnStart.disabled = false;
            nodes.btnStop.disabled = true;
        }
        
        // Update Console Logs (keep scroll at bottom if already at bottom)
        const isScrolledToBottom = nodes.consoleOutput.parentElement.scrollHeight - nodes.consoleOutput.parentElement.clientHeight <= nodes.consoleOutput.parentElement.scrollTop + 50;
        
        nodes.consoleOutput.innerText = data.logs;
        
        if (isScrolledToBottom) {
            nodes.consoleOutput.parentElement.scrollTop = nodes.consoleOutput.parentElement.scrollHeight;
        }
        
    } catch (e) {
        console.error("Error polling chatbot status:", e);
    }
}

// Start chatbot trigger
async function startBot() {
    nodes.btnStart.disabled = true;
    showToast("Đang kết nối GPM Login và khởi động bot...");
    try {
        const response = await fetch('/api/start', { method: 'POST' });
        const data = await response.json();
        if (data.success) {
            showToast("Khởi động chatbot thành công!");
            pollStatus();
        } else {
            showToast(data.message || "Lỗi khi khởi động chatbot", "error");
        }
    } catch (e) {
        showToast("Không thể kết nối đến máy chủ quản lý.", "error");
    }
}

// Stop chatbot trigger
async function stopBot() {
    nodes.btnStop.disabled = true;
    showToast("Đang dừng hoạt động của chatbot...");
    try {
        const response = await fetch('/api/stop', { method: 'POST' });
        const data = await response.json();
        if (data.success) {
            showToast("Chatbot đã dừng hẳn.");
            pollStatus();
        } else {
            showToast(data.message || "Lỗi khi dừng chatbot", "error");
        }
    } catch (e) {
        showToast("Không thể kết nối đến máy chủ quản lý.", "error");
    }
}

// Load configurations (.env + settings.yaml)
async function loadConfiguration() {
    try {
        const response = await fetch('/api/settings');
        const data = await response.json();
        
        const env = data.env;
        const settings = data.settings;
        
        // Fill form fields
        // Env variables
        document.getElementById('key-gemini').value = env.GEMINI_API_KEY || '';
        document.getElementById('key-mimo').value = env.XIAOMIMIMO_API_KEY || '';
        document.getElementById('base-mimo').value = env.XIAOMIMIMO_API_BASE || 'https://token-plan-sgp.xiaomimimo.com/v1';
        document.getElementById('key-openai').value = env.OPENAI_API_KEY || '';
        document.getElementById('key-deepseek').value = env.DEEPSEEK_API_KEY || '';
        
        document.getElementById('gpm-url').value = env.GPM_API_URL || 'http://127.0.0.1:9495';
        document.getElementById('gpm-profile-id').value = env.GPM_PROFILE_ID || '';
        document.getElementById('gpm-debug-port').value = env.GPM_DEBUG_PORT || '9222';
        
        // Settings.yaml variables
        document.getElementById('gpm-mode').value = settings.connection?.mode || 'gpm_api';
        document.getElementById('llm-model').value = settings.llm?.default_model || 'openai/mimo-v2.5-pro';
        document.getElementById('system-prompt').value = settings.llm?.system_prompt || '';
        
        document.getElementById('delay-min').value = settings.human_like?.min_delay || 2.0;
        document.getElementById('delay-max').value = settings.human_like?.max_delay || 5.0;
        document.getElementById('typing-speed').value = settings.human_like?.typing_speed_wpm || 80;
        document.getElementById('debounce-time').value = settings.chatbot?.wait_for_user_finish_seconds || 10.0;
        
        // Update Quick Info cards
        nodes.infoProfile.innerText = env.GPM_PROFILE_ID || 'Chưa cấu hình';
        nodes.infoModel.innerText = settings.llm?.default_model || 'mimo-v2.5-pro';
        
    } catch (e) {
        showToast("Không thể tải cấu hình hệ thống.", "error");
    }
}

// Save Configuration
async function saveConfiguration(e) {
    e.preventDefault();
    showToast("Đang lưu cấu hình...");
    
    // Construct payload
    const payload = {
        env: {
            GEMINI_API_KEY: document.getElementById('key-gemini').value.trim(),
            XIAOMIMIMO_API_KEY: document.getElementById('key-mimo').value.trim(),
            XIAOMIMIMO_API_BASE: document.getElementById('base-mimo').value.trim(),
            OPENAI_API_KEY: document.getElementById('key-openai').value.trim(),
            DEEPSEEK_API_KEY: document.getElementById('key-deepseek').value.trim(),
            GPM_API_URL: document.getElementById('gpm-url').value.trim(),
            GPM_PROFILE_ID: document.getElementById('gpm-profile-id').value.trim(),
            GPM_DEBUG_PORT: document.getElementById('gpm-debug-port').value.trim()
        },
        settings: {
            connection: {
                mode: document.getElementById('gpm-mode').value,
                default_port: parseInt(document.getElementById('gpm-debug-port').value || 9222)
            },
            llm: {
                default_model: document.getElementById('llm-model').value.trim(),
                system_prompt: document.getElementById('system-prompt').value,
                fallbacks: [
                    "gemini/gemini-2.5-flash",
                    "openai/gpt-4o-mini",
                    "deepseek/deepseek-chat"
                ]
            },
            human_like: {
                min_delay: parseFloat(document.getElementById('delay-min').value || 2.0),
                max_delay: parseFloat(document.getElementById('delay-max').value || 5.0),
                typing_speed_wpm: parseInt(document.getElementById('typing-speed').value || 80),
                simulate_mouse: true
            },
            chatbot: {
                poll_interval: 2.0,
                context_history_limit: 10,
                wait_for_user_finish_seconds: parseFloat(document.getElementById('debounce-time').value || 10.0)
            }
        }
    };
    
    try {
        const response = await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await response.json();
        if (data.success) {
            showToast("Đã lưu và cập nhật cấu hình thành công!");
            loadConfiguration(); // reload data
        } else {
            showToast(data.message || "Gặp lỗi khi lưu cấu hình.", "error");
        }
    } catch (e) {
        showToast("Không thể gửi yêu cầu lưu cấu hình.", "error");
    }
}

// Load Whitelist details
async function loadWhitelist() {
    try {
        const response = await fetch('/api/whitelist');
        state.whitelist = await response.json();
        
        // Update checkbox
        nodes.whitelistAllowAll.checked = state.whitelist.allow_all;
        
        // Render lists
        renderWhitelistList(nodes.listNames, state.whitelist.allowed_names, 'name');
        renderWhitelistList(nodes.listThreads, state.whitelist.allowed_threads, 'thread');
        
    } catch (e) {
        console.error("Error loading whitelist:", e);
    }
}

// Render lists helper
function renderWhitelistList(container, items, type) {
    container.innerHTML = '';
    if (!items || items.length === 0) {
        container.innerHTML = '<li class="text-center text-muted py-4">Danh sách trống.</li>';
        return;
    }
    
    items.forEach((item, index) => {
        const li = document.createElement('li');
        li.className = 'whitelist-item';
        li.innerHTML = `
            <span>${item}</span>
            <button class="btn-delete" onclick="removeWhitelistItem('${type}', ${index})">
                <i class="fa-solid fa-trash-can"></i>
            </button>
        `;
        container.appendChild(li);
    });
}

// Toggle Whitelist Filter Mode
async function toggleWhitelistMode() {
    state.whitelist.allow_all = nodes.whitelistAllowAll.checked;
    await saveWhitelistOnBackend();
}

// Add Name to Whitelist
async function addWhitelistName() {
    const name = nodes.addNameInput.value.trim();
    if (!name) return;
    
    if (!state.whitelist.allowed_names) state.whitelist.allowed_names = [];
    if (state.whitelist.allowed_names.includes(name)) {
        showToast("Tên này đã tồn tại trong danh sách.", "error");
        return;
    }
    
    state.whitelist.allowed_names.push(name);
    nodes.addNameInput.value = '';
    await saveWhitelistOnBackend();
}

// Add Thread ID to Whitelist
async function addWhitelistThread() {
    const threadId = nodes.addThreadInput.value.trim();
    if (!threadId) return;
    
    if (!state.whitelist.allowed_threads) state.whitelist.allowed_threads = [];
    if (state.whitelist.allowed_threads.includes(threadId)) {
        showToast("ID này đã tồn tại trong danh sách.", "error");
        return;
    }
    
    state.whitelist.allowed_threads.push(threadId);
    nodes.addThreadInput.value = '';
    await saveWhitelistOnBackend();
}

// Remove item helper
async function removeWhitelistItem(type, index) {
    if (type === 'name') {
        state.whitelist.allowed_names.splice(index, 1);
    } else {
        state.whitelist.allowed_threads.splice(index, 1);
    }
    await saveWhitelistOnBackend();
}

// Global window reference so onclick works in HTML
window.removeWhitelistItem = removeWhitelistItem;

// Sync Whitelist to Backend
async function saveWhitelistOnBackend() {
    try {
        const response = await fetch('/api/whitelist', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(state.whitelist)
        });
        const data = await response.json();
        if (data.success) {
            loadWhitelist(); // Refresh UI
            showToast("Cập nhật Whitelist thành công!");
        }
    } catch (e) {
        showToast("Không thể lưu thay đổi whitelist.", "error");
    }
}

// Load Sent Messages History
async function loadHistory() {
    try {
        const response = await fetch('/api/messages');
        const data = await response.json();
        const messages = data.messages || [];
        
        nodes.historyTableBody.innerHTML = '';
        
        if (messages.length === 0) {
            nodes.historyTableBody.innerHTML = `
                <tr>
                    <td colspan="4" class="text-center text-muted">Chưa gửi đi tin nhắn nào trong phiên này.</td>
                </tr>
            `;
            return;
        }
        
        // Order from newest to oldest
        messages.reverse().forEach(m => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><strong>${m.timestamp}</strong></td>
                <td><span class="badge status-running" style="font-weight: 500;"><i class="fa-solid fa-user"></i> ${m.recipient}</span></td>
                <td>${m.reply}</td>
                <td><code style="color: #c084fc;">${m.model}</code></td>
            `;
            nodes.historyTableBody.appendChild(tr);
        });
    } catch (e) {
        console.error("Error loading sent messages history:", e);
    }
}
