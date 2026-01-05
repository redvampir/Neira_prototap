/**
 * Tool Provider — Система инструментов для VS Code Extension
 * 
 * Позволяет Нейре выполнять:
 * - Команды в терминале
 * - HTTP запросы
 * - Анализ кода
 * - Поиск файлов
 */

import * as vscode from 'vscode';
import { NeiraClient } from './neiraClient';

interface ToolDefinition {
    name: string;
    description: string;
    parameters: {
        type: string;
        properties: Record<string, any>;
        required: string[];
    };
}

interface ToolResult {
    success: boolean;
    output: any;
    error?: string;
    execution_time: number;
    tool_name: string;
}

interface ToolCall {
    name: string;
    parameters: Record<string, any>;
}

export class NeiraToolProvider {
    private client: NeiraClient;
    private outputChannel: vscode.OutputChannel;
    private tools: ToolDefinition[] = [];

    constructor(client: NeiraClient) {
        this.client = client;
        this.outputChannel = vscode.window.createOutputChannel('Neira Tools');
    }

    /**
     * Загружает список доступных инструментов
     */
    async loadTools(): Promise<ToolDefinition[]> {
        try {
            const response = await this.client.request('/tools', {});
            if (response.tools) {
                this.tools = response.tools;
                return this.tools;
            }
            return [];
        } catch (error) {
            this.outputChannel.appendLine(`❌ Ошибка загрузки инструментов: ${error}`);
            return [];
        }
    }

    /**
     * Выполняет инструмент
     */
    async execute(name: string, parameters: Record<string, any> = {}): Promise<ToolResult> {
        try {
            this.outputChannel.appendLine(`\n🔧 Выполняю: ${name}`);
            this.outputChannel.appendLine(`   Параметры: ${JSON.stringify(parameters)}`);
            
            const response = await this.client.request('/tools/execute', {
                name,
                parameters
            });

            if (response.success) {
                this.outputChannel.appendLine(`✅ Успешно (${response.execution_time?.toFixed(2)}с)`);
            } else {
                this.outputChannel.appendLine(`❌ Ошибка: ${response.error}`);
            }

            return response as ToolResult;
        } catch (error) {
            const result: ToolResult = {
                success: false,
                output: null,
                error: String(error),
                execution_time: 0,
                tool_name: name
            };
            this.outputChannel.appendLine(`❌ Исключение: ${error}`);
            return result;
        }
    }

    /**
     * Выполняет несколько инструментов последовательно
     */
    async executeBatch(calls: ToolCall[]): Promise<ToolResult[]> {
        try {
            this.outputChannel.appendLine(`\n📦 Пакетное выполнение: ${calls.length} инструментов`);
            
            const response = await this.client.request('/tools/batch', { calls });
            
            if (response.results) {
                this.outputChannel.appendLine(`✅ Завершено: ${response.successful}/${response.total} успешно`);
                return response.results as ToolResult[];
            }
            
            return [];
        } catch (error) {
            this.outputChannel.appendLine(`❌ Ошибка пакетного выполнения: ${error}`);
            return [];
        }
    }

    /**
     * Выполняет команду в терминале
     */
    async runCommand(command: string, cwd?: string): Promise<ToolResult> {
        return this.execute('run_command', {
            command,
            cwd: cwd || vscode.workspace.workspaceFolders?.[0]?.uri.fsPath,
            timeout: 60
        });
    }

    /**
     * Выполняет Python код
     */
    async runPython(code: string): Promise<ToolResult> {
        return this.execute('run_python', {
            code,
            timeout: 60
        });
    }

    /**
     * Поиск в файлах
     */
    async searchFiles(query: string, filePattern: string = '*'): Promise<ToolResult> {
        return this.execute('search_files', {
            query,
            file_pattern: filePattern,
            path: vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '.',
            max_results: 50
        });
    }

    /**
     * Найти файл по имени
     */
    async findFile(filename: string): Promise<ToolResult> {
        return this.execute('find_file', {
            filename,
            path: vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '.'
        });
    }

    /**
     * HTTP запрос
     */
    async httpRequest(
        url: string,
        method: string = 'GET',
        body?: string,
        headers?: Record<string, string>
    ): Promise<ToolResult> {
        return this.execute('http_request', {
            url,
            method,
            body,
            headers,
            timeout: 30
        });
    }

    /**
     * Информация о системе
     */
    async getSystemInfo(): Promise<ToolResult> {
        return this.execute('system_info', {});
    }

    /**
     * Анализ кода
     */
    async analyzeCode(code: string, language: string = 'python'): Promise<ToolResult> {
        return this.execute('analyze_code', {
            code,
            language
        });
    }

    /**
     * Показывает QuickPick со списком инструментов
     */
    async showToolPicker(): Promise<void> {
        if (this.tools.length === 0) {
            await this.loadTools();
        }

        if (this.tools.length === 0) {
            vscode.window.showWarningMessage('Инструменты недоступны');
            return;
        }

        const items = this.tools.map(t => ({
            label: `$(tools) ${t.name}`,
            description: t.description,
            tool: t
        }));

        const selected = await vscode.window.showQuickPick(items, {
            placeHolder: 'Выберите инструмент для выполнения'
        });

        if (selected) {
            await this.executeToolInteractively(selected.tool);
        }
    }

    /**
     * Интерактивное выполнение инструмента
     */
    private async executeToolInteractively(tool: ToolDefinition): Promise<void> {
        const params: Record<string, any> = {};
        
        // Запрашиваем параметры
        for (const [name, schema] of Object.entries(tool.parameters.properties)) {
            const isRequired = tool.parameters.required.includes(name);
            const schemaObj = schema as any;
            
            const value = await vscode.window.showInputBox({
                prompt: `${schemaObj.description || name}${isRequired ? ' (обязательно)' : ''}`,
                placeHolder: schemaObj.default?.toString() || '',
                validateInput: (input) => {
                    if (isRequired && !input.trim()) {
                        return 'Это поле обязательно';
                    }
                    return null;
                }
            });

            if (value === undefined) {
                return; // Отменено
            }

            if (value.trim()) {
                // Конвертируем тип
                if (schemaObj.type === 'number') {
                    params[name] = parseFloat(value);
                } else if (schemaObj.type === 'boolean') {
                    params[name] = value.toLowerCase() === 'true';
                } else {
                    params[name] = value;
                }
            }
        }

        // Выполняем
        const result = await this.execute(tool.name, params);
        
        // Показываем результат
        this.outputChannel.show();
        this.outputChannel.appendLine('\n--- Результат ---');
        this.outputChannel.appendLine(JSON.stringify(result.output, null, 2));
    }

    /**
     * Выполняет команду из активного терминала
     */
    async executeFromTerminal(): Promise<void> {
        const command = await vscode.window.showInputBox({
            prompt: 'Введите команду для выполнения',
            placeHolder: 'ls -la, git status, npm test...'
        });

        if (command) {
            const result = await this.runCommand(command);
            
            if (result.success) {
                const output = result.output;
                vscode.window.showInformationMessage(
                    `Команда выполнена (${result.execution_time.toFixed(2)}с)`
                );
                
                // Показываем вывод
                this.outputChannel.show();
                this.outputChannel.appendLine(`\n$ ${command}`);
                this.outputChannel.appendLine(output?.stdout || '');
                if (output?.stderr) {
                    this.outputChannel.appendLine(`STDERR: ${output.stderr}`);
                }
            } else {
                vscode.window.showErrorMessage(`Ошибка: ${result.error}`);
            }
        }
    }

    /**
     * Анализирует текущий файл
     */
    async analyzeCurrentFile(): Promise<void> {
        const editor = vscode.window.activeTextEditor;
        if (!editor) {
            vscode.window.showWarningMessage('Нет активного файла');
            return;
        }

        const code = editor.document.getText();
        const language = editor.document.languageId;

        const result = await this.analyzeCode(code, language);

        if (result.success) {
            const issues = result.output?.issues || [];
            
            if (issues.length === 0) {
                vscode.window.showInformationMessage('✅ Проблем не найдено!');
            } else {
                const items = issues.map((i: string) => ({
                    label: `$(warning) ${i}`,
                    description: ''
                }));

                vscode.window.showQuickPick(items, {
                    placeHolder: `Найдено ${issues.length} проблем`
                });
            }
        } else {
            vscode.window.showErrorMessage(`Ошибка анализа: ${result.error}`);
        }
    }

    dispose(): void {
        this.outputChannel.dispose();
    }
}

/**
 * Регистрирует команды инструментов
 */
export function registerToolCommands(
    context: vscode.ExtensionContext,
    toolProvider: NeiraToolProvider
): void {
    
    // Показать список инструментов
    context.subscriptions.push(
        vscode.commands.registerCommand('neira.showTools', async () => {
            await toolProvider.showToolPicker();
        })
    );

    // Выполнить команду
    context.subscriptions.push(
        vscode.commands.registerCommand('neira.executeCommand', async () => {
            await toolProvider.executeFromTerminal();
        })
    );

    // Анализ текущего файла
    context.subscriptions.push(
        vscode.commands.registerCommand('neira.analyzeFile', async () => {
            await toolProvider.analyzeCurrentFile();
        })
    );

    // Системная информация
    context.subscriptions.push(
        vscode.commands.registerCommand('neira.systemInfo', async () => {
            const result = await toolProvider.getSystemInfo();
            if (result.success) {
                const info = result.output;
                vscode.window.showInformationMessage(
                    `${info.os} ${info.os_version}\nPython: ${info.python}\nМашина: ${info.machine}`,
                    { modal: true }
                );
            }
        })
    );
}
