/**
 * Streaming Provider — потоковый вывод ответов от Neira Server
 * 
 * Использует Server-Sent Events (SSE) для получения ответов по частям
 */

import * as vscode from 'vscode';
import { NeiraClient } from './neiraClient';

export interface StreamCallbacks {
    onToken: (token: string) => void;
    onComplete: (fullText: string) => void;
    onError: (error: string) => void;
}

export class NeiraStreamingProvider {
    private client: NeiraClient;
    private baseUrl: string;
    private abortController: AbortController | null = null;

    constructor(client: NeiraClient, baseUrl: string = 'http://127.0.0.1:8765') {
        this.client = client;
        this.baseUrl = baseUrl;
    }

    /**
     * Стриминг ответа на сообщение чата
     */
    async streamChat(
        message: string,
        context: string,
        callbacks: StreamCallbacks
    ): Promise<void> {
        await this.streamRequest('/stream/chat', { message, context }, callbacks);
    }

    /**
     * Стриминг объяснения кода
     */
    async streamExplain(
        code: string,
        language: string,
        callbacks: StreamCallbacks
    ): Promise<void> {
        await this.streamRequest('/stream/explain', { code, language }, callbacks);
    }

    /**
     * Стриминг генерации кода
     */
    async streamGenerate(
        description: string,
        language: string,
        callbacks: StreamCallbacks
    ): Promise<void> {
        await this.streamRequest('/stream/generate', { description, language }, callbacks);
    }

    /**
     * Универсальный стриминг запрос
     */
    async streamRequest(
        endpoint: string,
        data: Record<string, any>,
        callbacks: StreamCallbacks
    ): Promise<void> {
        // Отменяем предыдущий запрос
        this.abort();
        
        this.abortController = new AbortController();
        const signal = this.abortController.signal;

        let fullText = '';

        try {
            const response = await fetch(`${this.baseUrl}${endpoint}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'text/event-stream'
                },
                body: JSON.stringify(data),
                signal
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const reader = response.body?.getReader();
            if (!reader) {
                throw new Error('No response body');
            }

            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                
                if (done) {
                    break;
                }

                const chunk = decoder.decode(value, { stream: true });
                buffer += chunk;
                
                // Парсим SSE формат
                const lines = buffer.split(/\r?\n/);
                buffer = lines.pop() ?? '';
                for (const line of lines) {
                    if (line.startsWith('data:')) {
                        const data = line.slice(5).trimStart();
                        if (!data) {
                            continue;
                        }
                        
                        if (data === '[DONE]') {
                            callbacks.onComplete(fullText);
                            return;
                        }

                        try {
                            const parsed = JSON.parse(data);
                            if (parsed.token) {
                                fullText += parsed.token;
                                callbacks.onToken(parsed.token);
                            }
                            if (parsed.error) {
                                callbacks.onError(parsed.error);
                                return;
                            }
                        } catch {
                            // Просто текстовый токен
                            fullText += data;
                            callbacks.onToken(data);
                        }
                    }
                }
            }

            callbacks.onComplete(fullText);

        } catch (error) {
            if (error instanceof Error && error.name === 'AbortError') {
                // Запрос отменён пользователем
                callbacks.onComplete(fullText);
            } else {
                callbacks.onError(String(error));
            }
        }
    }

    /**
     * Отмена текущего стриминга
     */
    abort(): void {
        if (this.abortController) {
            this.abortController.abort();
            this.abortController = null;
        }
    }

    /**
     * Симуляция стриминга для fallback (когда сервер не поддерживает SSE)
     */
    async simulateStream(
        text: string,
        callbacks: StreamCallbacks,
        delayMs: number = 20
    ): Promise<void> {
        // Разбиваем на токены (слова + пунктуация)
        const tokens = text.match(/\S+\s*|\s+/g) || [text];
        
        for (const token of tokens) {
            await new Promise(resolve => setTimeout(resolve, delayMs));
            callbacks.onToken(token);
        }
        
        callbacks.onComplete(text);
    }
}

/**
 * Streaming Chat View — чат с потоковым выводом
 */
export class StreamingChatManager {
    private streamingProvider: NeiraStreamingProvider;
    private outputChannel: vscode.OutputChannel;
    private isStreaming: boolean = false;

    constructor(client: NeiraClient, baseUrl: string) {
        this.streamingProvider = new NeiraStreamingProvider(client, baseUrl);
        this.outputChannel = vscode.window.createOutputChannel('Neira Stream');
    }

    /**
     * Показывает стриминг в OutputChannel
     */
    async streamToOutput(message: string, context: string = ''): Promise<string> {
        return new Promise((resolve, reject) => {
            this.outputChannel.show(true);
            this.outputChannel.appendLine(`\n> ${message}\n`);
            this.outputChannel.appendLine('---');
            
            let fullText = '';
            this.isStreaming = true;

            this.streamingProvider.streamChat(message, context, {
                onToken: (token) => {
                    this.outputChannel.append(token);
                    fullText += token;
                },
                onComplete: (text) => {
                    this.isStreaming = false;
                    this.outputChannel.appendLine('\n---');
                    resolve(text);
                },
                onError: (error) => {
                    this.isStreaming = false;
                    this.outputChannel.appendLine(`\n❌ Ошибка: ${error}`);
                    reject(new Error(error));
                }
            });
        });
    }

    /**
     * Стриминг с прогресс-баром
     */
    async streamWithProgress(
        message: string,
        context: string = ''
    ): Promise<string> {
        return vscode.window.withProgress({
            location: vscode.ProgressLocation.Notification,
            title: 'Нейра думает...',
            cancellable: true
        }, async (progress, token) => {
            return new Promise<string>((resolve, reject) => {
                token.onCancellationRequested(() => {
                    this.streamingProvider.abort();
                });

                let fullText = '';
                let charCount = 0;

                this.streamingProvider.streamChat(message, context, {
                    onToken: (tokenText) => {
                        fullText += tokenText;
                        charCount += tokenText.length;
                        
                        // Обновляем прогресс
                        progress.report({
                            message: `${charCount} символов...`
                        });
                    },
                    onComplete: (text) => {
                        resolve(text);
                    },
                    onError: (error) => {
                        reject(new Error(error));
                    }
                });
            });
        });
    }

    /**
     * Проверяет, идёт ли стриминг
     */
    get streaming(): boolean {
        return this.isStreaming;
    }

    /**
     * Отменяет текущий стриминг
     */
    cancel(): void {
        this.streamingProvider.abort();
        this.isStreaming = false;
    }

    dispose(): void {
        this.outputChannel.dispose();
    }
}
