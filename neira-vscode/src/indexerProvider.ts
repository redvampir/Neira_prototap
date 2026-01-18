/**
 * Neira Workspace Indexer Provider
 * 
 * Индексация и поиск символов в workspace.
 * Обеспечивает быстрый поиск по кодовой базе и получение контекста для LLM.
 */

import * as vscode from 'vscode';
import { NeiraClient } from './neiraClient';

// ==================== ИНТЕРФЕЙСЫ ====================

interface Symbol {
    name: string;
    type: 'function' | 'class' | 'method' | 'variable' | 'import' | 'constant';
    file_path: string;
    line: number;
    end_line?: number;
    docstring?: string;
    signature?: string;
    parent?: string;
}

interface IndexStats {
    total_files: number;
    total_symbols: number;
    indexed_at: string;
    languages: { [key: string]: number };
}

interface SearchResult {
    results: Symbol[];
    total: number;
}

// ==================== ПРОВАЙДЕР ====================

export class NeiraIndexerProvider implements vscode.TreeDataProvider<IndexItem> {
    private _onDidChangeTreeData = new vscode.EventEmitter<IndexItem | undefined | null | void>();
    readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

    private stats: IndexStats | null = null;
    private isIndexing = false;
    private searchResults: Symbol[] = [];

    constructor(private client: NeiraClient) {}

    // ==================== TREE DATA PROVIDER ====================

    getTreeItem(element: IndexItem): vscode.TreeItem {
        return element;
    }

    async getChildren(element?: IndexItem): Promise<IndexItem[]> {
        if (!element) {
            // Корневой уровень
            const items: IndexItem[] = [];

            // Статус индексации
            if (this.isIndexing) {
                items.push(new IndexItem(
                    '$(sync~spin) Идёт индексация...',
                    vscode.TreeItemCollapsibleState.None,
                    'status'
                ));
            } else if (this.stats) {
                items.push(new IndexItem(
                    `📊 ${this.stats.total_files} файлов, ${this.stats.total_symbols} символов`,
                    vscode.TreeItemCollapsibleState.None,
                    'stats',
                    `Последнее обновление: ${new Date(this.stats.indexed_at).toLocaleString()}`
                ));
            } else {
                items.push(new IndexItem(
                    '$(warning) Индекс не создан',
                    vscode.TreeItemCollapsibleState.None,
                    'status',
                    'Нажмите для индексации'
                ));
            }

            // Действия
            items.push(new IndexItem(
                '$(refresh) Переиндексировать',
                vscode.TreeItemCollapsibleState.None,
                'action',
                undefined,
                {
                    command: 'neira.indexWorkspace',
                    title: 'Индексировать workspace'
                }
            ));

            items.push(new IndexItem(
                '$(search) Поиск символов...',
                vscode.TreeItemCollapsibleState.None,
                'action',
                undefined,
                {
                    command: 'neira.searchSymbols',
                    title: 'Поиск символов'
                }
            ));

            // Результаты поиска
            if (this.searchResults.length > 0) {
                items.push(new IndexItem(
                    `🔍 Результаты поиска (${this.searchResults.length})`,
                    vscode.TreeItemCollapsibleState.Expanded,
                    'search-results'
                ));
            }

            return items;
        }

        // Дочерние элементы для результатов поиска
        if (element.contextValue === 'search-results') {
            return this.searchResults.map(symbol => {
                const icon = this.getSymbolIcon(symbol.type);
                const item = new IndexItem(
                    `${icon} ${symbol.name}`,
                    vscode.TreeItemCollapsibleState.None,
                    'symbol',
                    `${symbol.file_path}:${symbol.line}`
                );
                
                // Клик открывает файл
                item.command = {
                    command: 'vscode.open',
                    title: 'Открыть',
                    arguments: [
                        vscode.Uri.file(symbol.file_path),
                        { selection: new vscode.Range(symbol.line - 1, 0, symbol.line - 1, 0) }
                    ]
                };
                
                return item;
            });
        }

        return [];
    }

    // ==================== ИНДЕКСАЦИЯ ====================

    async indexWorkspace(force: boolean = false): Promise<void> {
        if (this.isIndexing) {
            vscode.window.showWarningMessage('Индексация уже выполняется');
            return;
        }

        this.isIndexing = true;
        this._onDidChangeTreeData.fire();

        try {
            const response = await this.client.request('/index/workspace', { force });

            if (response.success && response.data) {
                this.stats = {
                    total_files: response.data.total_files,
                    total_symbols: response.data.total_symbols,
                    indexed_at: new Date().toISOString(),
                    languages: response.data.languages || {}
                };

                vscode.window.showInformationMessage(
                    `✅ Проиндексировано: ${response.data.total_files} файлов, ${response.data.total_symbols} символов`
                );
            } else {
                throw new Error(response.error || 'Неизвестная ошибка');
            }
        } catch (error) {
            vscode.window.showErrorMessage(`Ошибка индексации: ${error}`);
        } finally {
            this.isIndexing = false;
            this._onDidChangeTreeData.fire();
        }
    }

    // ==================== ПОИСК ====================

    async searchSymbols(): Promise<void> {
        const query = await vscode.window.showInputBox({
            prompt: 'Поиск символов (функции, классы, методы)',
            placeHolder: 'Например: handle_chat или User'
        });

        if (!query) {
            return;
        }

        await this.executeSearch(query);
    }

    async executeSearch(query: string, symbolType?: string): Promise<Symbol[]> {
        try {
            const response = await this.client.request('/index/search', {
                query,
                symbol_type: symbolType,
                limit: 30
            });

            if (response.success && response.data) {
                this.searchResults = response.data.results;
                this._onDidChangeTreeData.fire();
                return this.searchResults;
            } else {
                throw new Error(response.error || 'Ошибка поиска');
            }
        } catch (error) {
            vscode.window.showErrorMessage(`Ошибка поиска: ${error}`);
            return [];
        }
    }

    async searchAndShow(): Promise<void> {
        const query = await vscode.window.showInputBox({
            prompt: 'Поиск символов',
            placeHolder: 'Введите имя функции, класса или метода'
        });

        if (!query) {
            return;
        }

        const results = await this.executeSearch(query);

        if (results.length === 0) {
            vscode.window.showInformationMessage(`Символы не найдены: ${query}`);
            return;
        }

        // Показать QuickPick для выбора
        const items = results.map(s => ({
            label: `${this.getSymbolIcon(s.type)} ${s.name}`,
            description: s.type,
            detail: `${s.file_path}:${s.line}${s.signature ? ' - ' + s.signature : ''}`,
            symbol: s
        }));

        const selected = await vscode.window.showQuickPick(items, {
            placeHolder: 'Выберите символ для перехода',
            matchOnDescription: true,
            matchOnDetail: true
        });

        if (selected) {
            const uri = vscode.Uri.file(selected.symbol.file_path);
            const doc = await vscode.workspace.openTextDocument(uri);
            const editor = await vscode.window.showTextDocument(doc);
            
            const position = new vscode.Position(selected.symbol.line - 1, 0);
            editor.selection = new vscode.Selection(position, position);
            editor.revealRange(
                new vscode.Range(position, position),
                vscode.TextEditorRevealType.InCenter
            );
        }
    }

    // ==================== ПОЛУЧЕНИЕ КОНТЕКСТА ====================

    async getContextForQuery(query: string, currentFile?: string): Promise<string> {
        try {
            const response = await this.client.request('/index/context', {
                query,
                current_file: currentFile,
                max_symbols: 10
            });

            if (response.success && response.data) {
                return response.data.context;
            }
            return '';
        } catch {
            return '';
        }
    }

    async getContextForActiveFile(): Promise<string> {
        const editor = vscode.window.activeTextEditor;
        if (!editor) {
            return '';
        }

        // Получаем слово под курсором или выделение
        const selection = editor.selection;
        let query: string;

        if (selection.isEmpty) {
            const wordRange = editor.document.getWordRangeAtPosition(selection.active);
            query = wordRange ? editor.document.getText(wordRange) : '';
        } else {
            query = editor.document.getText(selection);
        }

        if (!query) {
            return '';
        }

        return this.getContextForQuery(query, editor.document.uri.fsPath);
    }

    // ==================== СТАТИСТИКА ====================

    async refreshStats(): Promise<void> {
        try {
            const response = await this.client.request('/index/stats', {});

            if (response.success && response.data) {
                this.stats = response.data;
                this._onDidChangeTreeData.fire();
            }
        } catch {
            // Игнорируем ошибки при обновлении статистики
        }
    }

    // ==================== ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ====================

    private getSymbolIcon(type: string): string {
        const icons: { [key: string]: string } = {
            'function': '$(symbol-function)',
            'class': '$(symbol-class)',
            'method': '$(symbol-method)',
            'variable': '$(symbol-variable)',
            'import': '$(symbol-namespace)',
            'constant': '$(symbol-constant)'
        };
        return icons[type] || '$(symbol-misc)';
    }

    clearSearchResults(): void {
        this.searchResults = [];
        this._onDidChangeTreeData.fire();
    }

    refresh(): void {
        this._onDidChangeTreeData.fire();
    }
}

// ==================== TREE ITEM ====================

class IndexItem extends vscode.TreeItem {
    constructor(
        public readonly label: string,
        public readonly collapsibleState: vscode.TreeItemCollapsibleState,
        public readonly contextValue: string,
        public readonly description?: string,
        public command?: vscode.Command
    ) {
        super(label, collapsibleState);
        this.tooltip = description || label;
    }
}

// ==================== SYMBOL PROVIDER ====================

export class NeiraWorkspaceSymbolProvider implements vscode.WorkspaceSymbolProvider {
    constructor(private client: NeiraClient) {}

    async provideWorkspaceSymbols(
        query: string,
        token: vscode.CancellationToken
    ): Promise<vscode.SymbolInformation[]> {
        if (query.length < 2) {
            return [];
        }

        try {
            const response = await this.client.request('/index/search', {
                query,
                limit: 50
            });

            if (!response.success || !response.data) {
                return [];
            }

            return response.data.results.map((symbol: Symbol) => {
                const kind = this.getSymbolKind(symbol.type);
                const location = new vscode.Location(
                    vscode.Uri.file(symbol.file_path),
                    new vscode.Position(symbol.line - 1, 0)
                );

                return new vscode.SymbolInformation(
                    symbol.name,
                    kind,
                    symbol.parent || '',
                    location
                );
            });
        } catch {
            return [];
        }
    }

    private getSymbolKind(type: string): vscode.SymbolKind {
        const kinds: { [key: string]: vscode.SymbolKind } = {
            'function': vscode.SymbolKind.Function,
            'class': vscode.SymbolKind.Class,
            'method': vscode.SymbolKind.Method,
            'variable': vscode.SymbolKind.Variable,
            'import': vscode.SymbolKind.Module,
            'constant': vscode.SymbolKind.Constant
        };
        return kinds[type] || vscode.SymbolKind.Field;
    }
}

// ==================== ДОКУМЕНТАЦИЯ В HOVER ====================

export class NeiraHoverWithContext implements vscode.HoverProvider {
    constructor(
        private client: NeiraClient,
        private indexer: NeiraIndexerProvider
    ) {}

    async provideHover(
        document: vscode.TextDocument,
        position: vscode.Position,
        token: vscode.CancellationToken
    ): Promise<vscode.Hover | null> {
        const wordRange = document.getWordRangeAtPosition(position);
        if (!wordRange) {
            return null;
        }

        const word = document.getText(wordRange);
        if (word.length < 2) {
            return null;
        }

        try {
            // Ищем символ в индексе
            const response = await this.client.request('/index/search', {
                query: word,
                limit: 1
            });

            if (!response.success || !response.data || response.data.results.length === 0) {
                return null;
            }

            const symbol = response.data.results[0];
            
            // Точное совпадение имени
            if (symbol.name !== word) {
                return null;
            }

            // Формируем Markdown hover
            const md = new vscode.MarkdownString();
            md.isTrusted = true;

            // Заголовок
            md.appendMarkdown(`**${symbol.type}** \`${symbol.name}\`\n\n`);

            // Сигнатура
            if (symbol.signature) {
                md.appendCodeblock(symbol.signature, 'python');
            }

            // Документация
            if (symbol.docstring) {
                md.appendMarkdown(`---\n\n${symbol.docstring}\n\n`);
            }

            // Местоположение
            md.appendMarkdown(`📍 [${symbol.file_path}:${symbol.line}](${vscode.Uri.file(symbol.file_path)}#L${symbol.line})`);

            return new vscode.Hover(md, wordRange);
        } catch {
            return null;
        }
    }
}
