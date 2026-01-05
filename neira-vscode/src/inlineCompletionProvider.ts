/**
 * Neira Inline Completion Provider
 * Ghost Text - подсказки кода по мере набора (как Copilot)
 */

import * as vscode from 'vscode';
import { NeiraClient } from './neiraClient';

interface CompletionCache {
    prefix: string;
    completions: string[];
    timestamp: number;
}

export class NeiraInlineCompletionProvider implements vscode.InlineCompletionItemProvider {
    private _client: NeiraClient;
    private _cache: Map<string, CompletionCache> = new Map();
    private _debounceTimer: NodeJS.Timeout | undefined;
    private _lastRequestTime = 0;
    private _enabled = true;

    // Настройки
    private readonly DEBOUNCE_MS = 300;      // Задержка перед запросом
    private readonly CACHE_TTL_MS = 30000;   // Время жизни кэша
    private readonly MIN_PREFIX_LENGTH = 3;  // Минимум символов для запроса
    private readonly MAX_CONTEXT_LINES = 50; // Контекст для модели
    private readonly REQUEST_COOLDOWN_MS = 500; // Минимум между запросами

    constructor(client: NeiraClient) {
        this._client = client;
    }

    public setEnabled(enabled: boolean) {
        this._enabled = enabled;
    }

    public isEnabled(): boolean {
        return this._enabled;
    }

    public clearCache() {
        this._cache.clear();
    }

    async provideInlineCompletionItems(
        document: vscode.TextDocument,
        position: vscode.Position,
        context: vscode.InlineCompletionContext,
        token: vscode.CancellationToken
    ): Promise<vscode.InlineCompletionItem[] | undefined> {
        if (!this._enabled) {
            return undefined;
        }

        // Проверяем тип триггера
        if (context.triggerKind === vscode.InlineCompletionTriggerKind.Automatic) {
            // Автоматический триггер - используем debounce
            return this._debouncedComplete(document, position, token);
        }

        // Ручной триггер (Ctrl+Space) - сразу запрашиваем
        return this._getCompletions(document, position, token);
    }

    private async _debouncedComplete(
        document: vscode.TextDocument,
        position: vscode.Position,
        token: vscode.CancellationToken
    ): Promise<vscode.InlineCompletionItem[] | undefined> {
        return new Promise((resolve) => {
            if (this._debounceTimer) {
                clearTimeout(this._debounceTimer);
            }

            this._debounceTimer = setTimeout(async () => {
                if (token.isCancellationRequested) {
                    resolve(undefined);
                    return;
                }

                const result = await this._getCompletions(document, position, token);
                resolve(result);
            }, this.DEBOUNCE_MS);
        });
    }

    private async _getCompletions(
        document: vscode.TextDocument,
        position: vscode.Position,
        token: vscode.CancellationToken
    ): Promise<vscode.InlineCompletionItem[] | undefined> {
        // Проверяем cooldown между запросами
        const now = Date.now();
        if (now - this._lastRequestTime < this.REQUEST_COOLDOWN_MS) {
            return undefined;
        }

        // Получаем текст до курсора
        const linePrefix = document.lineAt(position).text.substring(0, position.character);
        
        // Проверяем минимальную длину
        if (linePrefix.trim().length < this.MIN_PREFIX_LENGTH) {
            return undefined;
        }

        // Не предлагаем в комментариях и строках (базовая проверка)
        if (this._isInCommentOrString(document, position)) {
            return undefined;
        }

        // Проверяем кэш
        const cacheKey = this._getCacheKey(document, position);
        const cached = this._cache.get(cacheKey);
        if (cached && (now - cached.timestamp) < this.CACHE_TTL_MS) {
            return this._createCompletionItems(cached.completions, position);
        }

        // Получаем контекст
        const contextCode = this._getContext(document, position);
        
        if (token.isCancellationRequested) {
            return undefined;
        }

        try {
            this._lastRequestTime = now;

            const response = await this._client.complete({
                prefix: contextCode.before,
                suffix: contextCode.after,
                language: document.languageId,
                filename: document.fileName,
                maxTokens: 150
            });

            if (token.isCancellationRequested) {
                return undefined;
            }

            if (response.success && response.data?.completions) {
                const completions = response.data.completions;
                
                // Кэшируем результат
                this._cache.set(cacheKey, {
                    prefix: linePrefix,
                    completions,
                    timestamp: now
                });

                // Чистим старый кэш
                this._cleanupCache();

                return this._createCompletionItems(completions, position);
            }
        } catch (error) {
            console.error('Neira completion error:', error);
        }

        return undefined;
    }

    private _getContext(document: vscode.TextDocument, position: vscode.Position): { before: string; after: string } {
        const startLine = Math.max(0, position.line - this.MAX_CONTEXT_LINES);
        const endLine = Math.min(document.lineCount - 1, position.line + 10);

        // Код ДО курсора
        const beforeRange = new vscode.Range(startLine, 0, position.line, position.character);
        const before = document.getText(beforeRange);

        // Код ПОСЛЕ курсора
        const afterRange = new vscode.Range(position.line, position.character, endLine, document.lineAt(endLine).text.length);
        const after = document.getText(afterRange);

        return { before, after };
    }

    private _createCompletionItems(
        completions: string[],
        position: vscode.Position
    ): vscode.InlineCompletionItem[] {
        return completions.map(text => {
            const item = new vscode.InlineCompletionItem(text);
            item.range = new vscode.Range(position, position);
            return item;
        });
    }

    private _getCacheKey(document: vscode.TextDocument, position: vscode.Position): string {
        const linePrefix = document.lineAt(position).text.substring(0, position.character);
        return `${document.uri.toString()}:${position.line}:${linePrefix}`;
    }

    private _isInCommentOrString(document: vscode.TextDocument, position: vscode.Position): boolean {
        const line = document.lineAt(position).text;
        const prefix = line.substring(0, position.character);

        // Базовая проверка для распространённых языков
        const lang = document.languageId;

        // Однострочные комментарии
        if (lang === 'python' && prefix.includes('#')) {
            return true;
        }
        if (['javascript', 'typescript', 'java', 'c', 'cpp', 'csharp', 'go', 'rust'].includes(lang)) {
            if (prefix.includes('//')) {
                return true;
            }
        }

        // Проверка на незакрытые строки (очень базовая)
        const singleQuotes = (prefix.match(/'/g) || []).length;
        const doubleQuotes = (prefix.match(/"/g) || []).length;
        const backticks = (prefix.match(/`/g) || []).length;

        if (singleQuotes % 2 !== 0 || doubleQuotes % 2 !== 0 || backticks % 2 !== 0) {
            return true;
        }

        return false;
    }

    private _cleanupCache() {
        const now = Date.now();
        for (const [key, value] of this._cache.entries()) {
            if (now - value.timestamp > this.CACHE_TTL_MS) {
                this._cache.delete(key);
            }
        }
    }
}
