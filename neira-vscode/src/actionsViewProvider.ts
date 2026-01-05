/**
 * Actions View Provider - Панель быстрых действий
 * Кнопки управления сервером, обучения, памяти
 */

import * as vscode from 'vscode';
import { NeiraClient } from './neiraClient';

interface ActionItem {
    id: string;
    label: string;
    description?: string;
    icon: string;
    command: string;
    category: 'server' | 'learn' | 'memory' | 'tools' | 'code' | 'layers';
}

const ACTIONS: ActionItem[] = [
        // Слои моделей
        {
            id: 'listLayers',
            label: 'Список слоёв',
            description: 'В разработке: список слоёв моделей',
            icon: 'layers',
            command: 'neira.listLayers',
            category: 'layers'
        },
        {
            id: 'activateLayer',
            label: 'Активировать слой',
            description: 'В разработке: сделать слой активным',
            icon: 'check',
            command: 'neira.activateLayer',
            category: 'layers'
        },
        {
            id: 'addLayer',
            label: 'Добавить слой',
            description: 'В разработке: добавить слой модели',
            icon: 'add',
            command: 'neira.addLayer',
            category: 'layers'
        },
        {
            id: 'deleteLayer',
            label: 'Удалить слой',
            description: 'В разработке: удалить слой модели',
            icon: 'trash',
            command: 'neira.deleteLayer',
            category: 'layers'
        },
    // Сервер
    {
        id: 'startServer',
        label: 'Запустить сервер',
        description: 'Запустить Neira Server',
        icon: 'play',
        command: 'neira.startServer',
        category: 'server'
    },
    {
        id: 'stopServer',
        label: 'Остановить сервер',
        description: 'Остановить Neira Server',
        icon: 'debug-stop',
        command: 'neira.stopServer',
        category: 'server'
    },
    {
        id: 'restartServer',
        label: 'Перезапустить',
        description: 'Перезапустить сервер',
        icon: 'refresh',
        command: 'neira.restartServer',
        category: 'server'
    },
    {
        id: 'serverLog',
        label: 'Показать логи',
        description: 'Открыть лог сервера',
        icon: 'output',
        command: 'neira.showServerLog',
        category: 'server'
    },
    
    // Обучение
    {
        id: 'learn',
        label: 'Обучить Нейру',
        description: 'Выбрать источник обучения',
        icon: 'mortar-board',
        command: 'neira.learn',
        category: 'learn'
    },
    {
        id: 'learnFromFile',
        label: 'Из файла',
        description: 'Загрузить файл для обучения',
        icon: 'file-text',
        command: 'neira.learnFromFile',
        category: 'learn'
    },
    {
        id: 'learnFromUrl',
        label: 'Из URL',
        description: 'Загрузить статью/документацию',
        icon: 'globe',
        command: 'neira.learnFromUrl',
        category: 'learn'
    },
    {
        id: 'learnFromSelection',
        label: 'Из выделенного',
        description: 'Требуется выделение в редакторе',
        icon: 'selection',
        command: 'neira.learnFromSelection',
        category: 'learn'
    },
    {
        id: 'learningStats',
        label: 'Статистика обучения',
        description: 'Что изучено',
        icon: 'graph',
        command: 'neira.learningStats',
        category: 'learn'
    },
    
    // Память и самосознание
    {
        id: 'introspection',
        label: 'Состояние Нейры',
        description: 'Интроспекция органов',
        icon: 'heart',
        command: 'neira.showIntrospection',
        category: 'memory'
    },
    {
        id: 'reflection',
        label: 'Рефлексия',
        description: 'Размышление о действиях',
        icon: 'lightbulb',
        command: 'neira.reflect',
        category: 'memory'
    },
    {
        id: 'memorySearch',
        label: 'Поиск в памяти',
        description: 'Семантический поиск',
        icon: 'search',
        command: 'neira.searchMemory',
        category: 'memory'
    },
    {
        id: 'rememberSelection',
        label: 'Запомнить выделенное',
        description: 'Требуется выделение в редакторе',
        icon: 'bookmark',
        command: 'neira.rememberSelection',
        category: 'memory'
    },
    
    // Инструменты
    {
        id: 'indexWorkspace',
        label: 'Индексировать проект',
        description: 'Создать индекс кода',
        icon: 'database',
        command: 'neira.indexWorkspace',
        category: 'tools'
    },
    {
        id: 'searchSymbols',
        label: 'Поиск символов',
        description: 'Найти функции/классы',
        icon: 'symbol-method',
        command: 'neira.searchSymbols',
        category: 'tools'
    },
    {
        id: 'projectStructure',
        label: 'Структура проекта',
        description: 'Показать дерево файлов',
        icon: 'list-tree',
        command: 'neira.showProjectStructure',
        category: 'tools'
    },
    
    // Код
    {
        id: 'explainCode',
        label: 'Объяснить код',
        description: 'Требуется выделенный фрагмент',
        icon: 'comment-discussion',
        command: 'neira.explainCode',
        category: 'code'
    },
    {
        id: 'generateCode',
        label: 'Генерировать код',
        description: 'Создать код по описанию',
        icon: 'sparkle',
        command: 'neira.generateCode',
        category: 'code'
    },
    {
        id: 'fixCode',
        label: 'Исправить код',
        description: 'Требуется выделенный фрагмент',
        icon: 'wrench',
        command: 'neira.fixCode',
        category: 'code'
    },
    {
        id: 'improveCode',
        label: 'Улучшить код',
        description: 'Требуется выделенный фрагмент',
        icon: 'rocket',
        command: 'neira.improveCode',
        category: 'code'
    },
    {
        id: 'generateTests',
        label: 'Сгенерировать тесты',
        description: 'Курсор в функции/классе или выделение',
        icon: 'beaker',
        command: 'neira.generateTests',
        category: 'code'
    },
    {
        id: 'generateDocs',
        label: 'Документация',
        description: 'Курсор в функции/классе или выделение',
        icon: 'book',
        command: 'neira.generateDocs',
        category: 'code'
    }
];

class ActionTreeItem extends vscode.TreeItem {
    constructor(
        public readonly action: ActionItem,
        public readonly collapsibleState: vscode.TreeItemCollapsibleState
    ) {
        super(action.label, collapsibleState);
        this.tooltip = action.description;
        this.description = action.description;
        this.iconPath = new vscode.ThemeIcon(action.icon);
        this.command = {
            command: action.command,
            title: action.label
        };
        this.contextValue = action.id;
    }
}

class CategoryTreeItem extends vscode.TreeItem {
    constructor(
        public readonly category: string,
        public readonly categoryLabel: string,
        public readonly categoryIcon: string
    ) {
        super(categoryLabel, vscode.TreeItemCollapsibleState.Expanded);
        this.iconPath = new vscode.ThemeIcon(categoryIcon);
        this.contextValue = 'category';
    }
}

export class NeiraActionsProvider implements vscode.TreeDataProvider<vscode.TreeItem> {
    private _onDidChangeTreeData = new vscode.EventEmitter<vscode.TreeItem | undefined | void>();
    readonly onDidChangeTreeData = this._onDidChangeTreeData.event;
    
    private client: NeiraClient;
    private serverOnline = false;
    
    private categories = [
        { id: 'server', label: '🖥️ Сервер', icon: 'server' },
        { id: 'layers', label: '🧩 Слои', icon: 'layers' },
        { id: 'learn', label: '🎓 Обучение', icon: 'mortar-board' },
        { id: 'memory', label: '🧠 Память', icon: 'brain' },
        { id: 'tools', label: '🔧 Инструменты', icon: 'tools' },
        { id: 'code', label: '💻 Код', icon: 'code' }
    ];

    constructor(client: NeiraClient) {
        this.client = client;
        this.checkServerStatus();
        
        // Периодическая проверка статуса
        setInterval(() => this.checkServerStatus(), 30000);
    }

    private async checkServerStatus(): Promise<void> {
        try {
            const response = await this.client.checkHealth();
            const wasOnline = this.serverOnline;
            this.serverOnline = response?.success === true;
            
            if (wasOnline !== this.serverOnline) {
                this._onDidChangeTreeData.fire();
            }
        } catch {
            if (this.serverOnline) {
                this.serverOnline = false;
                this._onDidChangeTreeData.fire();
            }
        }
    }

    refresh(): void {
        this.checkServerStatus();
        this._onDidChangeTreeData.fire();
    }

    getTreeItem(element: vscode.TreeItem): vscode.TreeItem {
        return element;
    }

    getChildren(element?: vscode.TreeItem): Thenable<vscode.TreeItem[]> {
        if (!element) {
            // Корневой уровень - категории
            return Promise.resolve(
                this.categories.map(cat => 
                    new CategoryTreeItem(cat.id, cat.label, cat.icon)
                )
            );
        }
        
        if (element instanceof CategoryTreeItem) {
            // Действия в категории
            const categoryActions = ACTIONS.filter(a => a.category === element.category);
            return Promise.resolve(
                categoryActions.map(action => {
                    const item = new ActionTreeItem(action, vscode.TreeItemCollapsibleState.None);
                    
                    // Особая обработка для кнопок сервера
                    if (action.id === 'startServer') {
                        item.description = this.serverOnline ? '(онлайн)' : '(офлайн)';
                        if (this.serverOnline) {
                            item.iconPath = new vscode.ThemeIcon('check', new vscode.ThemeColor('charts.green'));
                        }
                    }
                    if (action.id === 'stopServer' && !this.serverOnline) {
                        item.description = '(сервер не запущен)';
                    }
                    
                    return item;
                })
            );
        }
        
        return Promise.resolve([]);
    }
}

export function registerActionsView(
    context: vscode.ExtensionContext,
    client: NeiraClient
): NeiraActionsProvider {
    const provider = new NeiraActionsProvider(client);
    
    context.subscriptions.push(
        vscode.window.registerTreeDataProvider('neira.actionsView', provider)
    );
    
    // Команда обновления
    context.subscriptions.push(
        vscode.commands.registerCommand('neira.refreshActions', () => {
            provider.refresh();
        })
    );
    
    return provider;
}
