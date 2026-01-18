/**
 * Neira Context Manager Provider
 * 
 * Умное управление контекстом для LLM.
 * Оптимизация, сжатие и подсчёт токенов.
 */

import * as vscode from 'vscode';
import { NeiraClient } from './neiraClient';

// ==================== ИНТЕРФЕЙСЫ ====================

interface ContextBuildOptions {
    query: string;
    currentFile?: string;
    currentCode?: string;
    chatHistory?: Array<{ role: string; content: string }>;
    relatedFiles?: string[];
    toolResults?: any[];
    systemPrompt?: string;
    maxTokens?: number;
}

interface ContextResult {
    prompt: string;
    totalTokens: number;
    availableTokens: number;
    chunksCount: number;
}

interface TokenEstimate {
    tokens: number;
    characters: number;
    words: number;
}

// ==================== ПРОВАЙДЕР ====================

export class NeiraContextProvider {
    private tokenCache = new Map<string, number>();
    private maxCacheSize = 100;

    constructor(private client: NeiraClient) {}

    // ==================== ОСНОВНЫЕ МЕТОДЫ ====================

    /**
     * Собрать оптимизированный контекст для запроса
     */
    async buildContext(options: ContextBuildOptions): Promise<ContextResult> {
        try {
            const payload: Record<string, unknown> = {
                query: options.query,
                current_file: options.currentFile,
                current_code: options.currentCode,
                chat_history: options.chatHistory,
                related_files: options.relatedFiles,
                tool_results: options.toolResults,
                system_prompt: options.systemPrompt,
            };
            if (typeof options.maxTokens === 'number') {
                payload.max_tokens = options.maxTokens;
            }

            const response = await this.client.request('/context/build', payload);

            if (response.success && response.data) {
                return {
                    prompt: response.data.prompt,
                    totalTokens: response.data.total_tokens,
                    availableTokens: response.data.available_tokens,
                    chunksCount: response.data.chunks_count
                };
            }

            throw new Error(response.error || 'Не удалось собрать контекст');
        } catch (error) {
            // Fallback: возвращаем простой контекст
            return this.buildFallbackContext(options);
        }
    }

    /**
     * Оценить количество токенов
     */
    async estimateTokens(text: string): Promise<TokenEstimate> {
        // Проверяем кэш
        const cacheKey = this.hashString(text.substring(0, 100));
        if (this.tokenCache.has(cacheKey)) {
            const cached = this.tokenCache.get(cacheKey)!;
            return {
                tokens: cached,
                characters: text.length,
                words: text.split(/\s+/).length
            };
        }

        try {
            const response = await this.client.request('/context/estimate-tokens', {
                text
            });

            if (response.success && response.data) {
                // Кэшируем результат
                this.cacheToken(cacheKey, response.data.tokens);
                
                return {
                    tokens: response.data.tokens,
                    characters: response.data.characters,
                    words: response.data.words
                };
            }
        } catch {
            // Fallback
        }

        // Локальная оценка
        const tokens = this.estimateTokensLocal(text);
        this.cacheToken(cacheKey, tokens);
        
        return {
            tokens,
            characters: text.length,
            words: text.split(/\s+/).length
        };
    }

    /**
     * Получить оптимальный размер контекста для модели
     */
    async getOptimalContextSize(model: string, taskType: string = 'chat'): Promise<number> {
        try {
            const response = await this.client.request('/context/optimal-size', {
                model,
                task_type: taskType
            });

            if (response.success && response.data) {
                return response.data.optimal_tokens;
            }
        } catch {
            // Fallback
        }

        // Стандартные значения
        return this.getDefaultContextSize(model, taskType);
    }

    // ==================== МЕТОДЫ ДЛЯ РЕДАКТОРА ====================

    /**
     * Получить контекст для текущего редактора
     */
    async getEditorContext(): Promise<ContextResult | null> {
        const editor = vscode.window.activeTextEditor;
        if (!editor) {
            return null;
        }

        const document = editor.document;
        const selection = editor.selection;

        let currentCode: string;
        let currentFile = document.uri.fsPath;

        if (selection.isEmpty) {
            // Берём весь файл
            currentCode = document.getText();
        } else {
            // Берём выделение + контекст
            currentCode = this.getSelectionWithContext(document, selection);
        }

        return this.buildContext({
            query: 'Analyze the following code',
            currentFile,
            currentCode
        });
    }

    /**
     * Показать информацию о токенах для текущего документа
     */
    async showTokenInfo(): Promise<void> {
        const editor = vscode.window.activeTextEditor;
        if (!editor) {
            vscode.window.showWarningMessage('Нет активного редактора');
            return;
        }

        const text = editor.selection.isEmpty 
            ? editor.document.getText()
            : editor.document.getText(editor.selection);

        const estimate = await this.estimateTokens(text);

        vscode.window.showInformationMessage(
            `📊 Токены: ${estimate.tokens} | Символы: ${estimate.characters} | Слова: ${estimate.words}`
        );
    }

    // ==================== УМНОЕ ВКЛЮЧЕНИЕ КОНТЕКСТА ====================

    /**
     * Получить релевантные файлы для контекста
     */
    async getRelatedFiles(currentFile: string, maxFiles: number = 5): Promise<string[]> {
        const relatedFiles: string[] = [];
        
        try {
            const document = await vscode.workspace.openTextDocument(currentFile);
            const text = document.getText();
            
            // Извлекаем импорты
            const imports = this.extractImports(text, document.languageId);
            
            // Находим файлы
            for (const imp of imports) {
                if (relatedFiles.length >= maxFiles) {
                    break;
                }
                
                const files = await vscode.workspace.findFiles(
                    `**/${imp}*`,
                    '**/node_modules/**',
                    1
                );
                
                if (files.length > 0) {
                    relatedFiles.push(files[0].fsPath);
                }
            }
        } catch {
            // Игнорируем ошибки
        }

        return relatedFiles;
    }

    /**
     * Собрать контекст с автоматическим включением связанных файлов
     */
    async buildSmartContext(query: string): Promise<ContextResult> {
        const editor = vscode.window.activeTextEditor;
        
        if (!editor) {
            return this.buildContext({ query });
        }

        const currentFile = editor.document.uri.fsPath;
        const currentCode = editor.selection.isEmpty
            ? editor.document.getText()
            : this.getSelectionWithContext(editor.document, editor.selection);

        // Получаем связанные файлы
        const relatedFiles = await this.getRelatedFiles(currentFile, 3);

        return this.buildContext({
            query,
            currentFile,
            currentCode,
            relatedFiles
        });
    }

    // ==================== ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ====================

    private getSelectionWithContext(
        document: vscode.TextDocument,
        selection: vscode.Selection,
        contextLines: number = 10
    ): string {
        const startLine = Math.max(0, selection.start.line - contextLines);
        const endLine = Math.min(document.lineCount - 1, selection.end.line + contextLines);

        const range = new vscode.Range(
            new vscode.Position(startLine, 0),
            new vscode.Position(endLine, document.lineAt(endLine).text.length)
        );

        const fullText = document.getText(range);
        const selectedText = document.getText(selection);

        // Помечаем выделенный текст
        return fullText.replace(selectedText, `/* SELECTED START */\n${selectedText}\n/* SELECTED END */`);
    }

    private extractImports(text: string, language: string): string[] {
        const imports: string[] = [];

        if (language === 'python') {
            const matches = text.matchAll(/^(?:from\s+(\S+)|import\s+(\S+))/gm);
            for (const match of matches) {
                const mod = match[1] || match[2];
                if (mod && !mod.startsWith('.')) {
                    imports.push(mod.split('.')[0]);
                }
            }
        } else if (['javascript', 'typescript', 'javascriptreact', 'typescriptreact'].includes(language)) {
            const matches = text.matchAll(/(?:import|require)\s*\(?['"]([^'"]+)['"]/g);
            for (const match of matches) {
                if (!match[1].startsWith('.')) {
                    imports.push(match[1]);
                }
            }
        }

        return [...new Set(imports)];
    }

    private estimateTokensLocal(text: string): number {
        // Простая эвристика: ~4 символа на токен
        const words = text.split(/\s+/).length;
        const specialChars = (text.match(/[^\w\s]/g) || []).length;
        return words + specialChars;
    }

    private getDefaultContextSize(model: string, taskType: string): number {
        const modelSizes: { [key: string]: number } = {
            'llama3': 8192,
            'llama3.1': 131072,
            'mistral': 8192,
            'mixtral': 32768,
            'codellama': 16384,
            'qwen': 32768,
            'deepseek': 16384,
            'gpt-3.5': 16384,
            'gpt-4': 8192,
            'claude': 200000
        };

        let baseSize = 8192;
        for (const [name, size] of Object.entries(modelSizes)) {
            if (model.toLowerCase().includes(name)) {
                baseSize = size;
                break;
            }
        }

        const taskRatios: { [key: string]: number } = {
            'chat': 0.6,
            'completion': 0.3,
            'explain': 0.7,
            'generate': 0.5,
            'refactor': 0.8
        };

        const ratio = taskRatios[taskType] || 0.6;
        return Math.floor(baseSize * ratio);
    }

    private buildFallbackContext(options: ContextBuildOptions): ContextResult {
        const parts: string[] = [];

        if (options.systemPrompt) {
            parts.push(options.systemPrompt);
        }

        if (options.currentCode) {
            const fileInfo = options.currentFile ? `# ${options.currentFile}\n` : '';
            parts.push(`\`\`\`\n${fileInfo}${options.currentCode}\n\`\`\``);
        }

        parts.push(options.query);

        const prompt = parts.join('\n\n');
        const tokens = this.estimateTokensLocal(prompt);

        return {
            prompt,
            totalTokens: tokens,
            availableTokens: 6000 - tokens,
            chunksCount: parts.length
        };
    }

    private hashString(str: string): string {
        let hash = 0;
        for (let i = 0; i < str.length; i++) {
            const char = str.charCodeAt(i);
            hash = ((hash << 5) - hash) + char;
            hash = hash & hash;
        }
        return hash.toString(16);
    }

    private cacheToken(key: string, value: number): void {
        // Ограничиваем размер кэша
        if (this.tokenCache.size >= this.maxCacheSize) {
            const firstKey = this.tokenCache.keys().next().value;
            if (firstKey) {
                this.tokenCache.delete(firstKey);
            }
        }
        this.tokenCache.set(key, value);
    }

    clearCache(): void {
        this.tokenCache.clear();
    }
}

// ==================== STATUS BAR ITEM ====================

export class TokenCountStatusBar {
    private statusBarItem: vscode.StatusBarItem;
    private contextProvider: NeiraContextProvider;
    private updateTimeout: NodeJS.Timeout | undefined;

    constructor(contextProvider: NeiraContextProvider) {
        this.contextProvider = contextProvider;
        
        this.statusBarItem = vscode.window.createStatusBarItem(
            vscode.StatusBarAlignment.Right,
            90
        );
        this.statusBarItem.command = 'neira.showTokenInfo';
        this.statusBarItem.tooltip = 'Нажмите для подробной информации о токенах';
    }

    activate(context: vscode.ExtensionContext): void {
        context.subscriptions.push(this.statusBarItem);

        // Обновляем при смене редактора
        context.subscriptions.push(
            vscode.window.onDidChangeActiveTextEditor(() => this.scheduleUpdate())
        );

        // Обновляем при изменении текста
        context.subscriptions.push(
            vscode.workspace.onDidChangeTextDocument(() => this.scheduleUpdate())
        );

        // Обновляем при изменении выделения
        context.subscriptions.push(
            vscode.window.onDidChangeTextEditorSelection(() => this.scheduleUpdate())
        );

        // Первое обновление
        this.update();
    }

    private scheduleUpdate(): void {
        if (this.updateTimeout) {
            clearTimeout(this.updateTimeout);
        }
        this.updateTimeout = setTimeout(() => this.update(), 300);
    }

    private async update(): Promise<void> {
        const editor = vscode.window.activeTextEditor;
        
        if (!editor) {
            this.statusBarItem.hide();
            return;
        }

        const text = editor.selection.isEmpty
            ? editor.document.getText()
            : editor.document.getText(editor.selection);

        const estimate = await this.contextProvider.estimateTokens(text);

        const selectionText = editor.selection.isEmpty ? '' : ' (выделение)';
        this.statusBarItem.text = `$(symbol-numeric) ${estimate.tokens} токенов${selectionText}`;
        this.statusBarItem.show();
    }

    dispose(): void {
        if (this.updateTimeout) {
            clearTimeout(this.updateTimeout);
        }
        this.statusBarItem.dispose();
    }
}

// ==================== КОМАНДЫ ====================

export function registerContextCommands(
    context: vscode.ExtensionContext,
    provider: NeiraContextProvider
): void {
    // Показать информацию о токенах
    context.subscriptions.push(
        vscode.commands.registerCommand('neira.showTokenInfo', () => {
            provider.showTokenInfo();
        })
    );

    // Собрать умный контекст
    context.subscriptions.push(
        vscode.commands.registerCommand('neira.buildSmartContext', async () => {
            const query = await vscode.window.showInputBox({
                prompt: 'Запрос для сборки контекста',
                placeHolder: 'Например: Объясни этот код'
            });

            if (!query) {
                return;
            }

            const result = await provider.buildSmartContext(query);
            
            // Показываем результат в новом документе
            const doc = await vscode.workspace.openTextDocument({
                content: `# Собранный контекст\n\n**Токены:** ${result.totalTokens}\n**Доступно:** ${result.availableTokens}\n**Чанков:** ${result.chunksCount}\n\n---\n\n${result.prompt}`,
                language: 'markdown'
            });
            await vscode.window.showTextDocument(doc);
        })
    );

    // Очистить кэш токенов
    context.subscriptions.push(
        vscode.commands.registerCommand('neira.clearTokenCache', () => {
            provider.clearCache();
            vscode.window.showInformationMessage('Кэш токенов очищен');
        })
    );
}
