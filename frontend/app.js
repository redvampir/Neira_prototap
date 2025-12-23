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
const MAX_RECONNECT_ATTEMPTS = 20;  // Увеличено для большей надёжности

// Control Panel Settings
const settings = {
    temperature: 0.7,
    contextSize: 10,
    maxTokens: 4096,
    streamMode: true,
    debugMode: false,
    autoMemory: true,
};

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

    // Control Panel
    controlPanelToggle: document.getElementById('controlPanelToggle'),
    controlPanel: document.getElementById('controlPanel'),
    closeControlPanel: document.getElementById('closeControlPanel'),
    temperatureSlider: document.getElementById('temperatureSlider'),
    temperatureValue: document.getElementById('temperatureValue'),
    contextSizeSlider: document.getElementById('contextSizeSlider'),
    contextSizeValue: document.getElementById('contextSizeValue'),
    maxTokensInput: document.getElementById('maxTokensInput'),
    streamMode: document.getElementById('streamMode'),
    debugMode: document.getElementById('debugMode'),
    autoMemoryMode: document.getElementById('autoMemoryMode'),
    clearContextBtn: document.getElementById('clearContextBtn'),
    resetMemoryBtn: document.getElementById('resetMemoryBtn'),
    exportSettingsBtn: document.getElementById('exportSettingsBtn'),
    importSettingsBtn: document.getElementById('importSettingsBtn'),
    logViewer: document.getElementById('logViewer'),
    clearLogsBtn: document.getElementById('clearLogsBtn'),
    mainModelSelect: document.getElementById('mainModelSelect'),

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

    // Artifact Viewer
    artifactToggle: document.getElementById('artifactToggle'),
    artifactViewer: document.getElementById('artifactViewer'),
    artifactFrame: document.getElementById('artifactFrame'),
    artifactEmpty: document.getElementById('artifactEmpty'),
    artifactInfo: document.getElementById('artifactInfo'),
    templateName: document.getElementById('templateName'),
    artifactId: document.getElementById('artifactId'),
    artifactRefresh: document.getElementById('artifactRefresh'),
    artifactExpand: document.getElementById('artifactExpand'),
    artifactExport: document.getElementById('artifactExport'),
    artifactClose: document.getElementById('artifactClose'),
};

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    connectWebSocket();
    setupEventListeners();
    setupControlPanel();
    setupArtifactViewer();
    setupMobileUI();
    fetchStats();
    loadSettings();
    loadAvailableModels();

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
            
            // Обработка keepalive ping от сервера
            if (data.type === 'ping') {
                // Просто игнорируем, соединение живо
                return;
            }
            
            handleMessage(data);
        };

        ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            updateConnectionStatus(false);
        };

        ws.onclose = () => {
            console.log('WebSocket disconnected');
            updateConnectionStatus(false);

            // Attempt reconnection with exponential backoff
            if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
                reconnectAttempts++;
                const delay = Math.min(1000 * Math.pow(1.5, reconnectAttempts), 10000); // max 10s
                setTimeout(() => {
                    console.log(`Reconnecting... (${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})`);
                    connectWebSocket();
                }, delay);
            } else {
                const port = CONFIG.WS_URL.includes('8001') ? '8001' : '8000';
                addMessage('system', `Не удалось подключиться к серверу. Проверьте, что backend запущен на 127.0.0.1:${port}`);
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

// === Control Panel Setup ===
function setupControlPanel() {
    // Toggle control panel
    if (elements.controlPanelToggle) {
        elements.controlPanelToggle.addEventListener('click', () => {
            elements.controlPanel.classList.toggle('visible');
            addLog('Панель управления ' + (elements.controlPanel.classList.contains('visible') ? 'открыта' : 'закрыта'), 'info');
        });
    }

    // Close control panel
    if (elements.closeControlPanel) {
        elements.closeControlPanel.addEventListener('click', () => {
            elements.controlPanel.classList.remove('visible');
            addLog('Панель управления закрыта', 'info');
        });
    }

    // Temperature slider
    if (elements.temperatureSlider) {
        elements.temperatureSlider.addEventListener('input', (e) => {
            settings.temperature = e.target.value / 10;
            elements.temperatureValue.textContent = settings.temperature.toFixed(1);
            addLog(`Температура установлена: ${settings.temperature}`, 'info');
        });
    }

    // Context size slider
    if (elements.contextSizeSlider) {
        elements.contextSizeSlider.addEventListener('input', (e) => {
            settings.contextSize = parseInt(e.target.value);
            elements.contextSizeValue.textContent = settings.contextSize;
            addLog(`Размер контекста: ${settings.contextSize}`, 'info');
        });
    }

    // Max tokens input
    if (elements.maxTokensInput) {
        elements.maxTokensInput.addEventListener('change', (e) => {
            settings.maxTokens = parseInt(e.target.value);
            addLog(`Макс. токенов: ${settings.maxTokens}`, 'info');
        });
    }

    // Checkboxes
    if (elements.streamMode) {
        elements.streamMode.addEventListener('change', (e) => {
            settings.streamMode = e.target.checked;
            addLog(`Streaming ${settings.streamMode ? 'включён' : 'выключен'}`, 'info');
        });
    }

    if (elements.debugMode) {
        elements.debugMode.addEventListener('change', (e) => {
            settings.debugMode = e.target.checked;
            addLog(`Debug режим ${settings.debugMode ? 'включён' : 'выключен'}`, settings.debugMode ? 'success' : 'info');
        });
    }

    if (elements.autoMemoryMode) {
        elements.autoMemoryMode.addEventListener('change', (e) => {
            settings.autoMemory = e.target.checked;
            addLog(`Авто-сохранение памяти ${settings.autoMemory ? 'включено' : 'выключено'}`, 'info');
        });
    }

    // Action buttons
    if (elements.clearContextBtn) {
        elements.clearContextBtn.addEventListener('click', clearContext);
    }

    if (elements.resetMemoryBtn) {
        elements.resetMemoryBtn.addEventListener('click', resetMemory);
    }

    if (elements.exportSettingsBtn) {
        elements.exportSettingsBtn.addEventListener('click', exportSettings);
    }

    if (elements.importSettingsBtn) {
        elements.importSettingsBtn.addEventListener('click', importSettings);
    }

    if (elements.clearLogsBtn) {
        elements.clearLogsBtn.addEventListener('click', clearLogs);
    }
}

// Load settings from localStorage
function loadSettings() {
    const saved = localStorage.getItem('neira_settings');
    if (saved) {
        try {
            const loaded = JSON.parse(saved);
            Object.assign(settings, loaded);
            
            // Update UI
            if (elements.temperatureSlider) {
                elements.temperatureSlider.value = settings.temperature * 10;
                elements.temperatureValue.textContent = settings.temperature.toFixed(1);
            }
            if (elements.contextSizeSlider) {
                elements.contextSizeSlider.value = settings.contextSize;
                elements.contextSizeValue.textContent = settings.contextSize;
            }
            if (elements.maxTokensInput) elements.maxTokensInput.value = settings.maxTokens;
            if (elements.streamMode) elements.streamMode.checked = settings.streamMode;
            if (elements.debugMode) elements.debugMode.checked = settings.debugMode;
            if (elements.autoMemoryMode) elements.autoMemoryMode.checked = settings.autoMemory;
            
            addLog('Настройки загружены', 'success');
        } catch (error) {
            addLog('Ошибка загрузки настроек', 'error');
        }
    }
}

// Save settings to localStorage
function saveSettings() {
    localStorage.setItem('neira_settings', JSON.stringify(settings));
    addLog('Настройки сохранены', 'success');
}

// === Control Panel Actions ===
function clearContext() {
    if (confirm('Очистить контекст диалога?')) {
        fetch(`${CONFIG.API_URL}/clear-context`, { method: 'POST' })
            .then(response => response.json())
            .then(data => {
                addLog('Контекст очищен', 'success');
                addMessage('system', 'Контекст диалога очищен');
            })
            .catch(error => {
                addLog(`Ошибка очистки контекста: ${error.message}`, 'error');
            });
    }
}

function resetMemory() {
    if (confirm('ВНИМАНИЕ: Это удалит всю память Neira! Продолжить?')) {
        fetch(`${CONFIG.API_URL}/reset-memory`, { method: 'POST' })
            .then(response => response.json())
            .then(data => {
                addLog('Память сброшена', 'success');
                addMessage('system', '⚠️ Память системы сброшена');
            })
            .catch(error => {
                addLog(`Ошибка сброса памяти: ${error.message}`, 'error');
            });
    }
}

function exportSettings() {
    const dataStr = JSON.stringify(settings, null, 2);
    const dataUri = 'data:application/json;charset=utf-8,' + encodeURIComponent(dataStr);
    const exportFileDefaultName = `neira_settings_${new Date().toISOString().split('T')[0]}.json`;
    
    const linkElement = document.createElement('a');
    linkElement.setAttribute('href', dataUri);
    linkElement.setAttribute('download', exportFileDefaultName);
    linkElement.click();
    
    addLog('Настройки экспортированы', 'success');
}

function importSettings() {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'application/json';
    input.onchange = (e) => {
        const file = e.target.files[0];
        const reader = new FileReader();
        reader.onload = (event) => {
            try {
                const imported = JSON.parse(event.target.result);
                Object.assign(settings, imported);
                saveSettings();
                loadSettings();
                addLog('Настройки импортированы', 'success');
            } catch (error) {
                addLog(`Ошибка импорта: ${error.message}`, 'error');
            }
        };
        reader.readAsText(file);
    };
    input.click();
}

function clearLogs() {
    elements.logViewer.innerHTML = '<div class="log-entry">Логи очищены</div>';
}

function addLog(message, type = 'info') {
    const entry = document.createElement('div');
    entry.className = `log-entry ${type}`;
    const timestamp = new Date().toLocaleTimeString('ru-RU');
    entry.textContent = `[${timestamp}] ${message}`;
    elements.logViewer.appendChild(entry);
    elements.logViewer.scrollTop = elements.logViewer.scrollHeight;
    
    // Save settings on important changes
    if (type === 'success' && !message.includes('загружены') && !message.includes('импортированы')) {
        saveSettings();
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

    if (!message) {
        // Пустое сообщение
        elements.userInput.focus();
        return;
    }

    if (isProcessing) {
        // Уже обрабатывается запрос
        console.log('Ожидайте завершения предыдущего запроса');
        return;
    }

    if (!ws || ws.readyState !== WebSocket.OPEN) {
        // WebSocket не подключен
        addMessage('system', '❗ Нет связи с сервером. Попытка пereconnect...');
        connectWebSocket();
        return;
    }

    try {
        // Add user message to UI
        addMessage('user', message);

        // Clear input
        elements.userInput.value = '';
        autoResizeTextarea(); // Сбросить высоту

        // Send to backend
        ws.send(JSON.stringify({ message }));

        // Update UI state
        isProcessing = true;
        elements.sendButton.disabled = true;
        elements.sendButton.classList.add('processing');
        elements.sendButton.querySelector('span').textContent = 'Обработка...';
    } catch (error) {
        console.error('Send message error:', error);
        addMessage('system', `❗ Ошибка отправки: ${error.message}`);
        isProcessing = false;
        elements.sendButton.disabled = false;
        elements.sendButton.classList.remove('processing');
        elements.sendButton.querySelector('span').textContent = 'Отправить';
    }
}

// Handle WebSocket message
function handleMessage(data) {
    const { type, stage, content, metadata } = data;

    switch (type) {
        case 'stage':
            showStage(stage, content);
            break;

        case 'artifact':
            // Artifact создан - показать в viewer
            hideStage();
            if (metadata && metadata.artifact) {
                showArtifact(metadata.artifact);
                addMessage('assistant', content, { artifact_id: metadata.artifact.id });
            } else {
                addMessage('assistant', content);
            }
            resetProcessingState();
            break;

        case 'content':
            hideStage();
            addMessage('assistant', content, metadata);
            break;

        case 'done':
            hideStage();
            resetProcessingState();
            fetchStats(); // Refresh stats after completion
            break;

        case 'error':
            hideStage();
            addMessage('system', `❌ Ошибка: ${content}`);
            resetProcessingState();
            break;
    }
}

// Сбросить состояние обработки
function resetProcessingState() {
    isProcessing = false;
    elements.sendButton.disabled = false;
    elements.sendButton.classList.remove('processing');
    elements.sendButton.querySelector('span').textContent = 'Отправить';
    elements.userInput.focus();
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
        // Визуальный feedback
        if (elements.refreshStats) {
            elements.refreshStats.disabled = true;
            elements.refreshStats.textContent = '⏳ Обновление...';
        }

        const response = await fetch(`${CONFIG.API_URL}/stats`);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        const data = await response.json();
        updateStatsUI(data);
        
        // Успех
        if (elements.refreshStats) {
            elements.refreshStats.textContent = '✅ Обновлено';
            setTimeout(() => {
                elements.refreshStats.textContent = '🔄 Обновить';
                elements.refreshStats.disabled = false;
            }, 1000);
        }
    } catch (error) {
        console.error('Failed to fetch stats:', error);
        
        // Ошибка
        if (elements.refreshStats) {
            elements.refreshStats.textContent = '❌ Ошибка';
            setTimeout(() => {
                elements.refreshStats.textContent = '🔄 Обновить';
                elements.refreshStats.disabled = false;
            }, 2000);
        }
        
        // Показать ошибку в UI
        addMessage('system', `⚠️ Не удалось обновить статистику: ${error.message}`);
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

// Load available models from Ollama
async function loadAvailableModels() {
    try {
        const response = await fetch(`${CONFIG.API_URL}/available-models`);
        const data = await response.json();
        const models = data.models || [];
        
        if (elements.mainModelSelect && models.length > 0) {
            // Clear existing options except "Auto"
            elements.mainModelSelect.innerHTML = '<option value="auto">Auto (по умолчанию)</option>';
            
            // Add available models
            models.forEach(model => {
                const option = document.createElement('option');
                option.value = model;
                option.textContent = model;
                elements.mainModelSelect.appendChild(option);
            });
            
            addLog(`Загружено ${models.length} моделей`, 'success');
        }
    } catch (error) {
        addLog(`Ошибка загрузки моделей: ${error.message}`, 'error');
    }
}

// === Artifact Viewer Functions ===
let currentArtifact = null;

function setupArtifactViewer() {
    // Toggle artifact viewer
    if (elements.artifactToggle) {
        elements.artifactToggle.addEventListener('click', toggleArtifactViewer);
    }

    // Close artifact viewer
    if (elements.artifactClose) {
        elements.artifactClose.addEventListener('click', () => {
            elements.artifactViewer.classList.remove('visible');
            addLog('Artifact viewer закрыт', 'info');
        });
    }

    // Refresh artifact
    if (elements.artifactRefresh) {
        elements.artifactRefresh.addEventListener('click', () => {
            if (currentArtifact) {
                renderArtifact(currentArtifact);
                addLog('Артефакт обновлён', 'info');
            }
        });
    }

    // Expand artifact (fullscreen)
    if (elements.artifactExpand) {
        elements.artifactExpand.addEventListener('click', () => {
            if (currentArtifact) {
                const htmlFile = `${window.location.origin}/artifacts/${currentArtifact.id}.html`;
                window.open(htmlFile, '_blank');
            }
        });
    }

    // Export artifact
    if (elements.artifactExport) {
        elements.artifactExport.addEventListener('click', exportArtifact);
    }
}

function toggleArtifactViewer() {
    const isVisible = elements.artifactViewer.classList.toggle('visible');
    addLog('Artifact viewer ' + (isVisible ? 'открыт' : 'закрыт'), 'info');
}

function showArtifact(artifact) {
    currentArtifact = artifact;
    
    // Show viewer
    elements.artifactViewer.classList.add('visible');
    
    // Update info
    elements.templateName.textContent = artifact.template_used || 'Custom';
    elements.artifactId.textContent = artifact.id;
    
    // Render in iframe
    renderArtifact(artifact);
    
    // Hide empty state
    elements.artifactEmpty.style.display = 'none';
    
    addLog(`Артефакт ${artifact.id} загружен`, 'success');
}

function renderArtifact(artifact) {
    const html = buildArtifactHTML(artifact);
    const blob = new Blob([html], { type: 'text/html' });
    const url = URL.createObjectURL(blob);
    
    elements.artifactFrame.src = url;
    
    // Clean up old blob URL
    elements.artifactFrame.addEventListener('load', () => {
        URL.revokeObjectURL(url);
    }, { once: true });
}

function buildArtifactHTML(artifact) {
    return `<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Neira Artifact - ${artifact.id}</title>
  <style>
    body {
      margin: 0;
      padding: 20px;
      background: #1a1a1a;
      color: #e0e0e0;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      display: flex;
      justify-content: center;
      align-items: center;
      min-height: 100vh;
    }
    ${artifact.css}
  </style>
</head>
<body>
  ${artifact.html}
  <script>
    ${artifact.js}
  </script>
</body>
</html>`;
}

function exportArtifact() {
    if (!currentArtifact) return;
    
    const html = buildArtifactHTML(currentArtifact);
    const blob = new Blob([html], { type: 'text/html' });
    const url = URL.createObjectURL(blob);
    
    const a = document.createElement('a');
    a.href = url;
    a.download = `neira_artifact_${currentArtifact.id}.html`;
    a.click();
    
    URL.revokeObjectURL(url);
    addLog(`Артефакт экспортирован: ${a.download}`, 'success');
}

// Export for debugging
window.NeiraDebug = {
    sendTestMessage: (msg) => {
        elements.userInput.value = msg;
        sendMessage();
    },
    getStats: fetchStats,
    reconnect: connectWebSocket,
    settings: settings,
    reloadModels: loadAvailableModels,
    showArtifact: showArtifact,
    currentArtifact: () => currentArtifact,
};

console.log('🧠 Neira Frontend loaded');
console.log('Debug functions available: window.NeiraDebug');
