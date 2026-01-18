/**
 * Neira API Client
 * HTTP клиент для связи с сервером Нейры
 */

interface NeiraResponse {
    success: boolean;
    data?: {
        response?: string;
        message?: string;
        explanation?: string;
        completions?: string[];
        tests?: string;
        docs?: string;
        fix?: string;
        refactored?: string;
        model?: string;
        task_type?: string;
        model_source?: string;
        models?: Record<string, Array<{ id: string; kind?: string; description?: string }>>;
        status?: string;
        neira_ready?: boolean;
        uptime_seconds?: number;
        requests_processed?: number;
        websocket_clients?: number;
        version?: string;
    };
    error?: string;
    request_id?: string;
    timestamp?: string;
}

interface CompleteRequest {
    prefix: string;
    suffix: string;
    language: string;
    filename: string;
    maxTokens?: number;
}

export class NeiraClient {
    private baseUrl: string;
    private timeout: number = 300000; // 5 минут для длинных запросов (локальные модели медленные)

    constructor(baseUrl: string = 'http://127.0.0.1:8765') {
        this.baseUrl = baseUrl.replace(/\/$/, '');
    }

    setBaseUrl(url: string): void {
        this.baseUrl = url.replace(/\/$/, '');
    }

    /**
     * Универсальный метод для любых запросов к API
     */
    async request(endpoint: string, data: Record<string, any> = {}): Promise<any> {
        try {
            const response = await this.fetchWithTimeout(`${this.baseUrl}${endpoint}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    ...data,
                    request_id: this.generateRequestId()
                })
            });

            if (!response.ok) {
                const text = await response.text();
                return {
                    success: false,
                    error: `HTTP ${response.status}: ${text}`
                };
            }

            const result = await response.json();
            return result.data || result;
        } catch (error) {
            return {
                success: false,
                error: error instanceof Error ? error.message : 'Ошибка запроса'
            };
        }
    }

    async checkHealth(): Promise<NeiraResponse> {
        try {
            const response = await this.fetchWithTimeout(`${this.baseUrl}/health`, {
                method: 'GET'
            }, 5000);

            if (!response.ok) {
                return {
                    success: false,
                    error: `HTTP ${response.status}`
                };
            }

            const data = await response.json() as NeiraResponse;
            return data;
        } catch (error) {
            return {
                success: false,
                error: error instanceof Error ? error.message : 'Ошибка соединения'
            };
        }
    }

    async chat(message: string, context: string = ''): Promise<NeiraResponse> {
        try {
            const response = await this.fetchWithTimeout(`${this.baseUrl}/chat`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    message,
                    context,
                    request_id: this.generateRequestId()
                })
            });

            if (!response.ok) {
                const text = await response.text();
                return {
                    success: false,
                    error: `HTTP ${response.status}: ${text}`
                };
            }

            const data = await response.json() as NeiraResponse;
            return data;
        } catch (error) {
            return {
                success: false,
                error: error instanceof Error ? error.message : 'Ошибка запроса'
            };
        }
    }

    async explainCode(
        code: string,
        language: string = '',
        filename: string = ''
    ): Promise<NeiraResponse> {
        try {
            const response = await this.fetchWithTimeout(`${this.baseUrl}/explain`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    code,
                    language,
                    filename,
                    request_id: this.generateRequestId()
                })
            });

            if (!response.ok) {
                const text = await response.text();
                return {
                    success: false,
                    error: `HTTP ${response.status}: ${text}`
                };
            }

            const data = await response.json() as NeiraResponse;
            return data;
        } catch (error) {
            return {
                success: false,
                error: error instanceof Error ? error.message : 'Ошибка запроса'
            };
        }
    }

    async generateCode(
        description: string,
        language: string = 'python',
        context: string = ''
    ): Promise<NeiraResponse> {
        try {
            const response = await this.fetchWithTimeout(`${this.baseUrl}/generate`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    description,
                    language,
                    context,
                    request_id: this.generateRequestId()
                })
            });

            if (!response.ok) {
                const text = await response.text();
                return {
                    success: false,
                    error: `HTTP ${response.status}: ${text}`
                };
            }

            const data = await response.json() as NeiraResponse;
            return data;
        } catch (error) {
            return {
                success: false,
                error: error instanceof Error ? error.message : 'Ошибка запроса'
            };
        }
    }

    /**
     * Inline completion (ghost text)
     */
    async complete(request: CompleteRequest): Promise<NeiraResponse> {
        try {
            const response = await this.fetchWithTimeout(`${this.baseUrl}/complete`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    prefix: request.prefix,
                    suffix: request.suffix,
                    language: request.language,
                    filename: request.filename,
                    max_tokens: request.maxTokens || 150,
                    request_id: this.generateRequestId()
                })
            }, 10000); // 10 секунд для completions

            if (!response.ok) {
                return { success: false, error: `HTTP ${response.status}` };
            }

            return await response.json() as NeiraResponse;
        } catch (error) {
            return {
                success: false,
                error: error instanceof Error ? error.message : 'Ошибка запроса'
            };
        }
    }

    /**
     * Исправление ошибки в коде
     */
    async fixError(code: string, error: string, language: string): Promise<NeiraResponse> {
        try {
            const response = await this.fetchWithTimeout(`${this.baseUrl}/fix`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    code,
                    error,
                    language,
                    request_id: this.generateRequestId()
                })
            });

            if (!response.ok) {
                return { success: false, error: `HTTP ${response.status}` };
            }

            return await response.json() as NeiraResponse;
        } catch (error) {
            return {
                success: false,
                error: error instanceof Error ? error.message : 'Ошибка запроса'
            };
        }
    }

    /**
     * Генерация тестов
     */
    async generateTests(code: string, language: string, framework?: string): Promise<NeiraResponse> {
        try {
            const response = await this.fetchWithTimeout(`${this.baseUrl}/generate-tests`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    code,
                    language,
                    framework,
                    request_id: this.generateRequestId()
                })
            });

            if (!response.ok) {
                return { success: false, error: `HTTP ${response.status}` };
            }

            return await response.json() as NeiraResponse;
        } catch (error) {
            return {
                success: false,
                error: error instanceof Error ? error.message : 'Ошибка запроса'
            };
        }
    }

    /**
     * Генерация документации
     */
    async generateDocs(code: string, language: string, style?: string): Promise<NeiraResponse> {
        try {
            const response = await this.fetchWithTimeout(`${this.baseUrl}/generate-docs`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    code,
                    language,
                    style,
                    request_id: this.generateRequestId()
                })
            });

            if (!response.ok) {
                return { success: false, error: `HTTP ${response.status}` };
            }

            return await response.json() as NeiraResponse;
        } catch (error) {
            return {
                success: false,
                error: error instanceof Error ? error.message : 'Ошибка запроса'
            };
        }
    }

    /**
     * Рефакторинг кода
     */
    async refactorCode(code: string, language: string, instruction?: string): Promise<NeiraResponse> {
        try {
            const response = await this.fetchWithTimeout(`${this.baseUrl}/refactor`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    code,
                    language,
                    instruction,
                    request_id: this.generateRequestId()
                })
            });

            if (!response.ok) {
                return { success: false, error: `HTTP ${response.status}` };
            }

            return await response.json() as NeiraResponse;
        } catch (error) {
            return {
                success: false,
                error: error instanceof Error ? error.message : 'Ошибка запроса'
            };
        }
    }

    /**
     * Генерация commit message
     */
    async generateCommitMessage(diff: string): Promise<NeiraResponse> {
        try {
            const response = await this.fetchWithTimeout(`${this.baseUrl}/commit-message`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    diff,
                    request_id: this.generateRequestId()
                })
            });

            if (!response.ok) {
                return { success: false, error: `HTTP ${response.status}` };
            }

            return await response.json() as NeiraResponse;
        } catch (error) {
            return {
                success: false,
                error: error instanceof Error ? error.message : 'Ошибка запроса'
            };
        }
    }

    /**
     * Объяснение diff
     */
    async explainDiff(diff: string): Promise<NeiraResponse> {
        try {
            const response = await this.fetchWithTimeout(`${this.baseUrl}/explain-diff`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    diff,
                    request_id: this.generateRequestId()
                })
            });

            if (!response.ok) {
                return { success: false, error: `HTTP ${response.status}` };
            }

            return await response.json() as NeiraResponse;
        } catch (error) {
            return {
                success: false,
                error: error instanceof Error ? error.message : 'Ошибка запроса'
            };
        }
    }

    // --- Model layers API ---
    async listLayers(): Promise<NeiraResponse> {
        try {
            const response = await this.fetchWithTimeout(`${this.baseUrl}/layers`, { method: 'GET' }, 5000);
            if (!response.ok) {
                return { success: false, error: `HTTP ${response.status}` };
            }
            const data = await response.json() as NeiraResponse;
            return data;
        } catch (error) {
            return { success: false, error: error instanceof Error ? error.message : 'Ошибка запроса' };
        }
    }

    // --- Models (ModelManager) ---
    async listModels(): Promise<NeiraResponse> {
        try {
            const response = await this.fetchWithTimeout(`${this.baseUrl}/models`, { method: 'GET' }, 5000);
            if (!response.ok) return { success: false, error: `HTTP ${response.status}` };
            return await response.json() as NeiraResponse;
        } catch (error) {
            return { success: false, error: error instanceof Error ? error.message : 'Ошибка запроса' };
        }
    }

    async switchModel(key: string): Promise<NeiraResponse> {
        try {
            const resp = await this.request('/models/switch', { key });
            return resp;
        } catch (error) {
            return { success: false, error: error instanceof Error ? error.message : 'Ошибка запроса' };
        }
    }
    async addLayer(model: string, layer: Record<string, any>, activate: boolean = false, overwrite: boolean = false): Promise<NeiraResponse> {
        return await this.request('/layers/add', { model, layer, activate, overwrite });
    }

    async activateLayer(model: string, id: string | null): Promise<NeiraResponse> {
        return await this.request('/layers/activate', { model, id });
    }

    async deleteLayer(model: string, id: string): Promise<NeiraResponse> {
        return await this.request('/layers/delete', { model, id });
    }
    

    private async fetchWithTimeout(
        url: string,
        options: RequestInit,
        timeout: number = this.timeout
    ): Promise<Response> {
        const controller = new AbortController();
        const timeoutId = globalThis.setTimeout(() => controller.abort(), timeout);

        try {
            const response = await globalThis.fetch(url, {
                ...options,
                signal: controller.signal
            });
            return response;
        } finally {
            globalThis.clearTimeout(timeoutId);
        }
    }

    private generateRequestId(): string {
        return Math.random().toString(36).substring(2, 10);
    }
}
