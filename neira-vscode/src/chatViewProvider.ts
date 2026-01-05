/**
 * Neira Chat View Provider
 * Webview для чата с Нейрой
 */

import * as vscode from 'vscode';
import { NeiraClient } from './neiraClient';

interface Message {
    role: 'user' | 'assistant' | 'system';
    content: string;
    timestamp: string;  // ISO string for serialization
}

interface WebviewMessage {
    type: string;
    message?: string;
}

const CHAT_HISTORY_KEY = 'neira.chatHistory';
const MAX_HISTORY_MESSAGES = 100;  // Ограничиваем историю

export class NeiraChatViewProvider implements vscode.WebviewViewProvider {
    public static readonly viewType = 'neira.chatView';

    private _view?: vscode.WebviewView;
    private _messages: Message[] = [];
    private _client: NeiraClient;
    private _context: vscode.ExtensionContext;

    constructor(
        private readonly _extensionUri: vscode.Uri,
        client: NeiraClient,
        context: vscode.ExtensionContext
    ) {
        this._client = client;
        this._context = context;
        this._loadHistory();
    }

    /**
     * Загрузка истории из globalState
     */
    private _loadHistory(): void {
        const saved = this._context.globalState.get<Message[]>(CHAT_HISTORY_KEY);
        if (saved && Array.isArray(saved)) {
            this._messages = saved;
            console.log(`📚 Загружено ${saved.length} сообщений из истории`);
        }
    }

    /**
     * Сохранение истории в globalState
     */
    private _saveHistory(): void {
        // Ограничиваем размер истории
        if (this._messages.length > MAX_HISTORY_MESSAGES) {
            this._messages = this._messages.slice(-MAX_HISTORY_MESSAGES);
        }
        this._context.globalState.update(CHAT_HISTORY_KEY, this._messages);
    }

    public resolveWebviewView(
        webviewView: vscode.WebviewView,
        _context: vscode.WebviewViewResolveContext,
        _token: vscode.CancellationToken
    ) {
        this._view = webviewView;

        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: [this._extensionUri]
        };

        webviewView.webview.html = this._getHtmlForWebview(webviewView.webview);

        // Обработка сообщений от webview
        webviewView.webview.onDidReceiveMessage(async (data: WebviewMessage) => {
            switch (data.type) {
                case 'sendMessage':
                    if (data.message) {
                        await this._handleUserMessage(data.message);
                    }
                    break;
                case 'clearChat':
                    this._messages = [];
                    this._saveHistory();
                    this._updateWebview();
                    break;
            }
        });

        // Начальное приветствие (только если история пуста)
        if (this._messages.length === 0) {
            this._messages.push({
                role: 'assistant',
                content: '👋 Привет! Я Нейра — твой локальный AI-ассистент.\n\nЯ работаю через Ollama без облачных зависимостей. Могу:\n• Объяснять код\n• Генерировать код\n• Отвечать на вопросы\n• Помогать с отладкой\n\nВыдели код и используй контекстное меню, или просто напиши мне!',
                timestamp: new Date().toISOString()
            });
            this._saveHistory();
        }

        this._updateWebview();
    }

    public addMessage(role: 'user' | 'assistant', content: string) {
        this._messages.push({
            role,
            content,
            timestamp: new Date().toISOString()
        });
        this._saveHistory();
        this._updateWebview();
    }

    private async _handleUserMessage(message: string) {
        if (!message.trim()) {
            return;
        }

        // Добавляем сообщение пользователя
        this._messages.push({
            role: 'user',
            content: message,
            timestamp: new Date().toISOString()
        });
        this._saveHistory();
        this._updateWebview();

        // Показываем индикатор загрузки
        this._view?.webview.postMessage({ type: 'setLoading', loading: true });

        try {
            // Отправляем запрос
            const response = await this._client.chat(message);

            if (response.success && response.data) {
                this._messages.push({
                    role: 'assistant',
                    content: response.data.response || '',
                    timestamp: new Date().toISOString()
                });
            } else {
                this._messages.push({
                    role: 'assistant',
                    content: `⚠️ Ошибка: ${response.error || 'Нет ответа от сервера'}\n\nУбедитесь, что сервер запущен: \`python neira_server.py\``,
                    timestamp: new Date().toISOString()
                });
            }
        } catch (error) {
            this._messages.push({
                role: 'assistant',
                content: `❌ Ошибка соединения: ${error}\n\nПроверьте:\n1. Запущен ли сервер Нейры\n2. Правильный ли адрес в настройках`,
                timestamp: new Date().toISOString()
            });
        } finally {
            this._view?.webview.postMessage({ type: 'setLoading', loading: false });
            this._saveHistory();
            this._updateWebview();
        }
    }

    /**
     * Форматирует ISO строку времени в локальное время
     */
    private _formatTime(isoString: string): string {
        try {
            return new Date(isoString).toLocaleTimeString('ru-RU', {
                hour: '2-digit',
                minute: '2-digit'
            });
        } catch {
            return '';
        }
    }

    private _updateWebview() {
        if (this._view) {
            this._view.webview.postMessage({
                type: 'updateMessages',
                messages: this._messages.map(m => ({
                    role: m.role,
                    content: m.content,
                    time: this._formatTime(m.timestamp)
                }))
            });
        }
    }

    private _getHtmlForWebview(webview: vscode.Webview): string {
        return `<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline';">
    <title>Neira Chat</title>
    <style>
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }
        
        body {
            font-family: var(--vscode-font-family);
            font-size: var(--vscode-font-size);
            color: var(--vscode-foreground);
            background: var(--vscode-editor-background);
            height: 100vh;
            display: flex;
            flex-direction: column;
        }
        
        .header {
            padding: 10px 15px;
            background: var(--vscode-sideBarSectionHeader-background);
            border-bottom: 1px solid var(--vscode-sideBarSectionHeader-border);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .header h2 {
            font-size: 14px;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .clear-btn {
            background: none;
            border: none;
            color: var(--vscode-textLink-foreground);
            cursor: pointer;
            font-size: 12px;
            padding: 4px 8px;
            border-radius: 3px;
        }
        
        .clear-btn:hover {
            background: var(--vscode-toolbar-hoverBackground);
        }
        
        .messages {
            flex: 1;
            overflow-y: auto;
            padding: 15px;
            display: flex;
            flex-direction: column;
            gap: 12px;
        }
        
        .message {
            display: flex;
            flex-direction: column;
            max-width: 95%;
        }
        
        .message.user {
            align-self: flex-end;
        }
        
        .message.assistant {
            align-self: flex-start;
        }
        
        .message-content {
            padding: 10px 14px;
            border-radius: 12px;
            line-height: 1.5;
            white-space: pre-wrap;
            word-wrap: break-word;
        }
        
        .message.user .message-content {
            background: var(--vscode-button-background);
            color: var(--vscode-button-foreground);
            border-bottom-right-radius: 4px;
        }
        
        .message.assistant .message-content {
            background: var(--vscode-editor-inactiveSelectionBackground);
            border-bottom-left-radius: 4px;
        }
        
        .message-time {
            font-size: 10px;
            color: var(--vscode-descriptionForeground);
            margin-top: 4px;
            padding: 0 4px;
        }
        
        .message.user .message-time {
            text-align: right;
        }
        
        /* Code blocks */
        .message-content code {
            font-family: var(--vscode-editor-font-family);
            background: var(--vscode-textCodeBlock-background);
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 0.9em;
        }
        
        .message-content pre {
            background: var(--vscode-textCodeBlock-background);
            padding: 12px;
            border-radius: 6px;
            overflow-x: auto;
            margin: 8px 0;
        }
        
        .message-content pre code {
            background: none;
            padding: 0;
        }
        
        .input-area {
            padding: 12px 15px;
            background: var(--vscode-sideBarSectionHeader-background);
            border-top: 1px solid var(--vscode-sideBarSectionHeader-border);
        }
        
        .input-container {
            display: flex;
            gap: 8px;
        }
        
        #messageInput {
            flex: 1;
            padding: 10px 14px;
            border: 1px solid var(--vscode-input-border);
            background: var(--vscode-input-background);
            color: var(--vscode-input-foreground);
            border-radius: 6px;
            font-family: inherit;
            font-size: inherit;
            resize: none;
            min-height: 40px;
            max-height: 120px;
        }
        
        #messageInput:focus {
            outline: none;
            border-color: var(--vscode-focusBorder);
        }
        
        #messageInput::placeholder {
            color: var(--vscode-input-placeholderForeground);
        }
        
        #sendBtn {
            padding: 10px 16px;
            background: var(--vscode-button-background);
            color: var(--vscode-button-foreground);
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-weight: 500;
            transition: background 0.2s;
        }
        
        #sendBtn:hover {
            background: var(--vscode-button-hoverBackground);
        }
        
        #sendBtn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        
        .loading {
            display: none;
            align-items: center;
            gap: 8px;
            padding: 10px 15px;
            color: var(--vscode-descriptionForeground);
        }
        
        .loading.visible {
            display: flex;
        }
        
        .loading-spinner {
            width: 16px;
            height: 16px;
            border: 2px solid var(--vscode-progressBar-background);
            border-top-color: transparent;
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }
        
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        
        .shortcuts {
            font-size: 11px;
            color: var(--vscode-descriptionForeground);
            margin-top: 8px;
        }
    </style>
</head>
<body>
    <div class="header">
        <h2>🧠 Нейра</h2>
        <button class="clear-btn" id="clearBtn">Очистить</button>
    </div>
    
    <div class="messages" id="messages"></div>
    
    <div class="loading" id="loading">
        <div class="loading-spinner"></div>
        <span>Нейра думает...</span>
    </div>
    
    <div class="input-area">
        <div class="input-container">
            <textarea 
                id="messageInput" 
                placeholder="Спросите что-нибудь..." 
                rows="1"
            ></textarea>
            <button id="sendBtn">→</button>
        </div>
        <div class="shortcuts">
            Ctrl+Enter — отправить | Ctrl+Shift+E — объяснить код
        </div>
    </div>

    <script>
        const vscode = acquireVsCodeApi();
        const messagesContainer = document.getElementById('messages');
        const messageInput = document.getElementById('messageInput');
        const sendBtn = document.getElementById('sendBtn');
        const clearBtn = document.getElementById('clearBtn');
        const loadingEl = document.getElementById('loading');
        
        // Auto-resize textarea
        messageInput.addEventListener('input', () => {
            messageInput.style.height = 'auto';
            messageInput.style.height = Math.min(messageInput.scrollHeight, 120) + 'px';
        });
        
        // Send message
        function sendMessage() {
            const message = messageInput.value.trim();
            if (!message) return;
            
            vscode.postMessage({ type: 'sendMessage', message });
            messageInput.value = '';
            messageInput.style.height = 'auto';
        }
        
        sendBtn.addEventListener('click', sendMessage);
        
        messageInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                e.preventDefault();
                sendMessage();
            }
        });
        
        // Clear chat
        clearBtn.addEventListener('click', () => {
            vscode.postMessage({ type: 'clearChat' });
        });
        
        // Handle messages from extension
        window.addEventListener('message', (event) => {
            const data = event.data;
            
            switch (data.type) {
                case 'updateMessages':
                    renderMessages(data.messages);
                    break;
                case 'setLoading':
                    loadingEl.classList.toggle('visible', data.loading);
                    sendBtn.disabled = data.loading;
                    break;
            }
        });
        
        function renderMessages(messages) {
            messagesContainer.innerHTML = messages.map(msg => {
                const content = formatMessage(msg.content);
                return \`
                    <div class="message \${msg.role}">
                        <div class="message-content">\${content}</div>
                        <div class="message-time">\${msg.time}</div>
                    </div>
                \`;
            }).join('');
            
            // Scroll to bottom
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }
        
        function formatMessage(text) {
            // Escape HTML
            text = text.replace(/&/g, '&amp;')
                      .replace(/</g, '&lt;')
                      .replace(/>/g, '&gt;');
            
            // Code blocks
            text = text.replace(/\`\`\`(\\w*)\\n([\\s\\S]*?)\`\`\`/g, 
                '<pre><code class="language-$1">$2</code></pre>');
            
            // Inline code
            text = text.replace(/\`([^\`]+)\`/g, '<code>$1</code>');
            
            // Bold
            text = text.replace(/\\*\\*([^*]+)\\*\\*/g, '<strong>$1</strong>');
            
            // Links
            text = text.replace(/\\[([^\\]]+)\\]\\(([^)]+)\\)/g, 
                '<a href="$2" target="_blank">$1</a>');
            
            return text;
        }
    </script>
</body>
</html>`;
    }
}
