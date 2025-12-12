/**
 * Neira Frontend - WebSocket Client
 * Connects to backend API for real-time chat
 */

// Configuration
const CONFIG = {
    // Default to localhost, can be overridden via environment variable
    WS_URL: window.NEIRA_WS_URL || 'ws://localhost:8000/ws/chat',
    API_URL: window.NEIRA_API_URL || 'http://localhost:8000/api',
    STATS_REFRESH_INTERVAL: 5000, // 5 seconds
};

// Global state
let ws = null;
let isProcessing = false;
let reconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 5;

// DOM elements
const elements = {
    messages: document.getElementById('messages'),
    userInput: document.getElementById('userInput'),
    sendButton: document.getElementById('sendButton'),
    stageIndicator: document.getElementById('stageIndicator'),
    stageText: document.getElementById('stageText'),
    statusIndicator: document.getElementById('statusIndicator'),
    statusText: document.getElementById('statusText'),
    refreshStats: document.getElementById('refreshStats'),
    statsToggle: document.getElementById('statsToggle'),
    statsSidebar: document.querySelector('.stats-sidebar'),

    // Stats
    currentModel: document.getElementById('currentModel'),
    modelSwitches: document.getElementById('modelSwitches'),
    vramUsage: document.getElementById('vramUsage'),
    memoryTotal: document.getElementById('memoryTotal'),
    memoryContext: document.getElementById('memoryContext'),
    expTotal: document.getElementById('expTotal'),
    expScore: document.getElementById('expScore'),

    // Model indicators
    modelCode: document.getElementById('modelCode'),
    modelReason: document.getElementById('modelReason'),
    modelPersonality: document.getElementById('modelPersonality'),
    cloudCode: document.getElementById('cloudCode'),
    cloudUniversal: document.getElementById('cloudUniversal'),
    cloudVision: document.getElementById('cloudVision'),
};

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    connectWebSocket();
    setupEventListeners();
    setupMobileUI();
    fetchStats();

    // Auto-refresh stats
    setInterval(fetchStats, CONFIG.STATS_REFRESH_INTERVAL);
});

// WebSocket Connection
function connectWebSocket() {
    try {
        ws = new WebSocket(CONFIG.WS_URL);

        ws.onopen = () => {
            console.log('WebSocket connected');
            updateConnectionStatus(true);
            reconnectAttempts = 0;
        };

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            handleMessage(data);
        };

        ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            updateConnectionStatus(false);
        };

        ws.onclose = () => {
            console.log('WebSocket disconnected');
            updateConnectionStatus(false);

            // Attempt reconnection
            if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
                reconnectAttempts++;
                setTimeout(() => {
                    console.log(`Reconnecting... (${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})`);
                    connectWebSocket();
                }, 2000 * reconnectAttempts);
            } else {
                addMessage('system', 'Не удалось подключиться к серверу. Проверьте, что backend запущен на http://localhost:8000');
            }
        };
    } catch (error) {
        console.error('Failed to create WebSocket:', error);
        updateConnectionStatus(false);
    }
}

// Update connection status UI
function updateConnectionStatus(connected) {
    if (connected) {
        elements.statusIndicator.className = 'status-indicator connected';
        elements.statusText.textContent = 'Connected';
        elements.sendButton.disabled = false;
    } else {
        elements.statusIndicator.className = 'status-indicator disconnected';
        elements.statusText.textContent = 'Disconnected';
        elements.sendButton.disabled = true;
    }
}

// Event Listeners
function setupEventListeners() {
    // Send button
    elements.sendButton.addEventListener('click', sendMessage);

    // Enter to send (Shift+Enter for new line)
    elements.userInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // Refresh stats button
    elements.refreshStats.addEventListener('click', fetchStats);

    // Stats toggle for mobile
    if (elements.statsToggle) {
        elements.statsToggle.addEventListener('click', toggleStats);
    }
}

// Mobile UI Setup
function setupMobileUI() {
    // Auto-resize textarea on mobile
    elements.userInput.addEventListener('input', autoResizeTextarea);

    // Handle virtual keyboard appearance
    if ('visualViewport' in window) {
        window.visualViewport.addEventListener('resize', handleViewportResize);
    }

    // Prevent zoom on input focus (iOS)
    elements.userInput.addEventListener('focus', () => {
        document.body.classList.add('input-focused');
    });

    elements.userInput.addEventListener('blur', () => {
        document.body.classList.remove('input-focused');
    });
}

// Auto-resize textarea
function autoResizeTextarea() {
    const textarea = elements.userInput;
    textarea.style.height = 'auto';
    textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
}

// Handle viewport resize (keyboard appearance)
function handleViewportResize() {
    const viewport = window.visualViewport;
    const inputContainer = document.querySelector('.input-container');

    if (viewport.height < window.innerHeight * 0.8) {
        // Keyboard is visible
        inputContainer.style.paddingBottom = (window.innerHeight - viewport.height) + 'px';
        elements.messages.scrollTop = elements.messages.scrollHeight;
    } else {
        // Keyboard hidden
        inputContainer.style.paddingBottom = '';
    }
}

// Toggle stats sidebar (mobile)
function toggleStats() {
    if (elements.statsSidebar) {
        elements.statsSidebar.classList.toggle('visible');
        elements.statsToggle.textContent = elements.statsSidebar.classList.contains('visible') ? '✕' : '📊';
    }
}

// Send message
function sendMessage() {
    const message = elements.userInput.value.trim();

    if (!message || isProcessing || ws.readyState !== WebSocket.OPEN) {
        return;
    }

    // Add user message to UI
    addMessage('user', message);

    // Clear input
    elements.userInput.value = '';

    // Send to backend
    ws.send(JSON.stringify({ message }));

    // Update UI state
    isProcessing = true;
    elements.sendButton.disabled = true;
}

// Handle WebSocket message
function handleMessage(data) {
    const { type, stage, content, metadata } = data;

    switch (type) {
        case 'stage':
            showStage(stage, content);
            break;

        case 'content':
            hideStage();
            addMessage('assistant', content, metadata);
            break;

        case 'done':
            hideStage();
            isProcessing = false;
            elements.sendButton.disabled = false;
            fetchStats(); // Refresh stats after completion
            break;

        case 'error':
            hideStage();
            addMessage('system', `Ошибка: ${content}`);
            isProcessing = false;
            elements.sendButton.disabled = false;
            break;
    }
}

// Show processing stage
function showStage(stage, content) {
    const stageEmojis = {
        analysis: '🔍',
        planning: '📋',
        execution: '⚙️',
        verification: '✅'
    };

    elements.stageIndicator.style.display = 'flex';
    elements.stageIndicator.querySelector('.stage-icon').textContent = stageEmojis[stage] || '⚙️';
    elements.stageText.textContent = content;
}

// Hide processing stage
function hideStage() {
    elements.stageIndicator.style.display = 'none';
}

// Add message to chat
function addMessage(role, content, metadata = null) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.textContent = content;

    messageDiv.appendChild(contentDiv);

    // Add metadata if available
    if (metadata) {
        const metaDiv = document.createElement('div');
        metaDiv.className = 'message-meta';

        if (metadata.model) {
            metaDiv.textContent = `Модель: ${metadata.model}`;
        }

        if (metadata.timestamp) {
            const time = new Date(metadata.timestamp).toLocaleTimeString('ru-RU');
            metaDiv.textContent += ` • ${time}`;
        }

        contentDiv.appendChild(metaDiv);
    }

    elements.messages.appendChild(messageDiv);

    // Scroll to bottom
    elements.messages.scrollTop = elements.messages.scrollHeight;
}

// Fetch stats from API
async function fetchStats() {
    try {
        const response = await fetch(`${CONFIG.API_URL}/stats`);
        const data = await response.json();

        updateStatsUI(data);
    } catch (error) {
        console.error('Failed to fetch stats:', error);
    }
}

// Update stats UI
function updateStatsUI(data) {
    // Model Manager
    if (data.model_manager) {
        elements.currentModel.textContent = data.model_manager.current_model || '-';
        elements.modelSwitches.textContent = data.model_manager.switches || 0;

        const loaded = data.model_manager.loaded_models || [];
        const currentVram = loaded.length > 0 ? '~5' : '0'; // Approximate
        elements.vramUsage.textContent = `${currentVram} / ${data.model_manager.max_vram_gb} GB`;
    }

    // Memory
    if (data.memory) {
        elements.memoryTotal.textContent = data.memory.total || 0;
        elements.memoryContext.textContent = data.memory.session_context || 0;
    }

    // Experience
    if (data.experience) {
        elements.expTotal.textContent = data.experience.total || 0;
        const avgScore = data.experience.avg_score || 0;
        elements.expScore.textContent = avgScore > 0 ? avgScore.toFixed(1) : '-';
    }

    // Model Status
    if (data.models) {
        updateModelIndicator(elements.modelCode, data.models.local?.code);
        updateModelIndicator(elements.modelReason, data.models.local?.reason);
        updateModelIndicator(elements.modelPersonality, data.models.local?.personality);
        updateModelIndicator(elements.cloudCode, data.models.cloud?.code);
        updateModelIndicator(elements.cloudUniversal, data.models.cloud?.universal);
        updateModelIndicator(elements.cloudVision, data.models.cloud?.vision);
    }
}

// Update model indicator
function updateModelIndicator(element, ready) {
    if (ready) {
        element.className = 'model-indicator ready';
    } else if (ready === false) {
        element.className = 'model-indicator';
    } else {
        element.className = 'model-indicator loading';
    }
}

// Export for debugging
window.NeiraDebug = {
    sendTestMessage: (msg) => {
        elements.userInput.value = msg;
        sendMessage();
    },
    getStats: fetchStats,
    reconnect: connectWebSocket
};

console.log('🧠 Neira Frontend loaded');
console.log('Debug functions available: window.NeiraDebug');
