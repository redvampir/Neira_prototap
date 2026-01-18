/**
 * File System Provider — работа с файлами через Neira Server
 * 
 * Позволяет:
 * - Читать/записывать файлы
 * - Искать по содержимому
 * - Навигация по структуре проекта
 * - Применение multi-file edits
 */

import * as vscode from 'vscode';
import { NeiraClient } from './neiraClient';

interface FileInfo {
    path: string;
    name: string;
    extension: string;
    size: number;
    is_directory: boolean;
    modified: string;
}

interface SearchResult {
    file_path: string;
    line_number: number;
    line_content: string;
    match_start: number;
    match_end: number;
}

interface ReadFileResult {
    success: boolean;
    content?: string;
    total_lines?: number;
    start_line?: number;
    end_line?: number;
    language?: string;
    path?: string;
    relative_path?: string;
    error?: string;
}

interface SearchResponse {
    success: boolean;
    results?: SearchResult[];
    total_matches?: number;
    files_searched?: number;
    truncated?: boolean;
    error?: string;
}

interface ListResponse {
    success: boolean;
    items?: FileInfo[];
    path?: string;
    total_items?: number;
    error?: string;
}

interface ProjectStructure {
    success: boolean;
    tree?: any;
    stats?: {
        total_files: number;
        total_dirs: number;
        total_size: number;
        by_extension: Record<string, number>;
        languages: Array<{ name: string; files: number }>;
    };
    root?: string;
    error?: string;
}

interface FileEdit {
    path: string;
    old_text: string;
    new_text: string;
}

export class NeiraFileSystemProvider {
    private client: NeiraClient;
    private outputChannel: vscode.OutputChannel;
    private workspaceRoot: string;

    constructor(client: NeiraClient) {
        this.client = client;
        this.outputChannel = vscode.window.createOutputChannel('Neira Files');
        
        // Определяем workspace root
        const folders = vscode.workspace.workspaceFolders;
        this.workspaceRoot = folders && folders.length > 0 
            ? folders[0].uri.fsPath 
            : '';
    }

    /**
     * Устанавливает рабочую директорию на сервере
     */
    async setWorkspace(workspacePath?: string): Promise<boolean> {
        const path = workspacePath || this.workspaceRoot;
        if (!path) {
            vscode.window.showErrorMessage('Workspace не определён');
            return false;
        }

        try {
            const response = await this.client.request('/files/set-workspace', {
                workspace_path: path
            });
            
            if (response.success) {
                this.workspaceRoot = path;
                this.outputChannel.appendLine(`✅ Workspace: ${path}`);
                return true;
            } else {
                vscode.window.showErrorMessage(`Ошибка: ${response.error}`);
                return false;
            }
        } catch (error) {
            this.outputChannel.appendLine(`❌ setWorkspace error: ${error}`);
            return false;
        }
    }

    /**
     * Читает файл
     */
    async readFile(
        filePath: string, 
        startLine: number = 1, 
        endLine?: number
    ): Promise<ReadFileResult> {
        try {
            const response = await this.client.request('/files/read', {
                path: filePath,
                start_line: startLine,
                end_line: endLine
            });
            
            return response as ReadFileResult;
        } catch (error) {
            return { success: false, error: String(error) };
        }
    }

    /**
     * Записывает файл
     */
    async writeFile(filePath: string, content: string): Promise<boolean> {
        try {
            const response = await this.client.request('/files/write', {
                path: filePath,
                content: content
            });
            
            if (response.success) {
                this.outputChannel.appendLine(`📝 Записано: ${filePath}`);
                return true;
            } else {
                vscode.window.showErrorMessage(`Ошибка записи: ${response.error}`);
                return false;
            }
        } catch (error) {
            this.outputChannel.appendLine(`❌ writeFile error: ${error}`);
            return false;
        }
    }

    /**
     * Редактирует файл (замена текста)
     */
    async editFile(
        filePath: string, 
        oldText: string, 
        newText: string
    ): Promise<boolean> {
        try {
            const response = await this.client.request('/files/edit', {
                path: filePath,
                old_text: oldText,
                new_text: newText
            });
            
            if (response.success) {
                this.outputChannel.appendLine(`✏️ Отредактировано: ${filePath}`);
                return true;
            } else {
                vscode.window.showErrorMessage(`Ошибка редактирования: ${response.error}`);
                return false;
            }
        } catch (error) {
            this.outputChannel.appendLine(`❌ editFile error: ${error}`);
            return false;
        }
    }

    /**
     * Поиск по содержимому файлов (grep)
     */
    async searchInFiles(
        query: string,
        options?: {
            path?: string;
            filePattern?: string;
            isRegex?: boolean;
            caseSensitive?: boolean;
            maxResults?: number;
        }
    ): Promise<SearchResponse> {
        try {
            const response = await this.client.request('/files/search', {
                query,
                path: options?.path || '.',
                file_pattern: options?.filePattern || '*',
                is_regex: options?.isRegex || false,
                case_sensitive: options?.caseSensitive || false,
                max_results: options?.maxResults || 100
            });
            
            return response as SearchResponse;
        } catch (error) {
            return { success: false, error: String(error) };
        }
    }

    /**
     * Список файлов в директории
     */
    async listDirectory(
        path: string = '.',
        options?: {
            showHidden?: boolean;
            recursive?: boolean;
            maxDepth?: number;
        }
    ): Promise<ListResponse> {
        try {
            const response = await this.client.request('/files/list', {
                path,
                show_hidden: options?.showHidden || false,
                recursive: options?.recursive || false,
                max_depth: options?.maxDepth || 3
            });
            
            return response as ListResponse;
        } catch (error) {
            return { success: false, error: String(error) };
        }
    }

    /**
     * Структура проекта
     */
    async getProjectStructure(maxDepth: number = 3): Promise<ProjectStructure> {
        try {
            const response = await this.client.request('/files/structure', {
                max_depth: maxDepth
            });
            
            return response as ProjectStructure;
        } catch (error) {
            return { success: false, error: String(error) };
        }
    }

    /**
     * Пакетное редактирование файлов
     */
    async applyEdits(edits: FileEdit[]): Promise<boolean> {
        try {
            const response = await this.client.request('/files/batch-edit', {
                edits
            });
            
            if (response.success) {
                this.outputChannel.appendLine(`📦 Применено ${edits.length} правок`);
                return true;
            } else {
                vscode.window.showErrorMessage(`Ошибка пакетного редактирования: ${response.error}`);
                return false;
            }
        } catch (error) {
            this.outputChannel.appendLine(`❌ applyEdits error: ${error}`);
            return false;
        }
    }

    /**
     * Показывает результаты поиска в QuickPick
     */
    async showSearchResults(query: string): Promise<void> {
        const result = await this.searchInFiles(query);
        
        if (!result.success || !result.results || result.results.length === 0) {
            vscode.window.showInformationMessage(`Ничего не найдено по запросу: ${query}`);
            return;
        }

        const items = result.results.map(r => ({
            label: `$(file) ${r.file_path}:${r.line_number}`,
            description: r.line_content.trim(),
            detail: `Строка ${r.line_number}`,
            filePath: r.file_path,
            lineNumber: r.line_number
        }));

        const selected = await vscode.window.showQuickPick(items, {
            placeHolder: `Найдено ${result.total_matches} совпадений`,
            matchOnDescription: true
        });

        if (selected) {
            // Открываем файл на нужной строке
            const uri = vscode.Uri.file(
                this.workspaceRoot 
                    ? `${this.workspaceRoot}/${selected.filePath}`
                    : selected.filePath
            );
            
            const doc = await vscode.workspace.openTextDocument(uri);
            await vscode.window.showTextDocument(doc, {
                selection: new vscode.Range(
                    selected.lineNumber - 1, 0,
                    selected.lineNumber - 1, 0
                )
            });
        }
    }

    /**
     * Показывает структуру проекта в TreeView
     */
    async showProjectStructure(): Promise<void> {
        const structure = await this.getProjectStructure();
        
        if (!structure.success) {
            vscode.window.showErrorMessage(`Ошибка: ${structure.error}`);
            return;
        }

        // Формируем информацию для отображения
        const stats = structure.stats;
        const info = [
            `📁 Директорий: ${stats?.total_dirs || 0}`,
            `📄 Файлов: ${stats?.total_files || 0}`,
            `💾 Размер: ${((stats?.total_size || 0) / 1024 / 1024).toFixed(2)} MB`,
            '',
            '📊 Основные языки:',
            ...(stats?.languages?.map(l => `   • ${l.name}: ${l.files} файлов`) || [])
        ];

        vscode.window.showInformationMessage(
            info.join('\n'),
            { modal: true }
        );
    }

    /**
     * Интерактивный поиск
     */
    async interactiveSearch(): Promise<void> {
        const query = await vscode.window.showInputBox({
            prompt: 'Поиск в файлах проекта',
            placeHolder: 'Введите текст или regex...'
        });

        if (query) {
            await this.showSearchResults(query);
        }
    }

    /**
     * Применяет правки с предварительным просмотром
     */
    async applyEditsWithPreview(edits: FileEdit[]): Promise<boolean> {
        // Показываем предварительный просмотр
        const previewItems = edits.map(e => ({
            label: `$(file) ${e.path}`,
            description: `${e.old_text.substring(0, 30)}... → ${e.new_text.substring(0, 30)}...`,
            edit: e
        }));

        const confirm = await vscode.window.showQuickPick(
            [
                { label: '$(check) Применить все правки', apply: true },
                { label: '$(x) Отмена', apply: false }
            ],
            { placeHolder: `${edits.length} файлов будет изменено` }
        );

        if (confirm?.apply) {
            return this.applyEdits(edits);
        }

        return false;
    }

    dispose(): void {
        this.outputChannel.dispose();
    }
}

/**
 * Регистрирует команды файловой системы
 */
export function registerFileSystemCommands(
    context: vscode.ExtensionContext,
    fsProvider: NeiraFileSystemProvider
): void {
    
    // Поиск в файлах
    context.subscriptions.push(
        vscode.commands.registerCommand('neira.searchInFiles', async () => {
            await fsProvider.interactiveSearch();
        })
    );

    // Структура проекта
    context.subscriptions.push(
        vscode.commands.registerCommand('neira.showProjectStructure', async () => {
            await fsProvider.showProjectStructure();
        })
    );

    // Установить workspace
    context.subscriptions.push(
        vscode.commands.registerCommand('neira.setWorkspace', async () => {
            const folders = vscode.workspace.workspaceFolders;
            if (folders && folders.length > 0) {
                const success = await fsProvider.setWorkspace(folders[0].uri.fsPath);
                if (success) {
                    vscode.window.showInformationMessage('Workspace установлен');
                }
            } else {
                vscode.window.showWarningMessage('Нет открытого workspace');
            }
        })
    );

    // Читать текущий файл через Neira
    context.subscriptions.push(
        vscode.commands.registerCommand('neira.readCurrentFile', async () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor) {
                vscode.window.showWarningMessage('Нет активного файла');
                return;
            }

            const result = await fsProvider.readFile(editor.document.uri.fsPath);
            if (result.success) {
                vscode.window.showInformationMessage(
                    `Файл прочитан: ${result.total_lines} строк, язык: ${result.language}`
                );
            }
        })
    );
}
