/**
 * Server Manager - Управление сервером Нейры
 * Автозапуск, остановка, мониторинг состояния
 */

import * as vscode from 'vscode';
import * as path from 'path';
import * as cp from 'child_process';
import { NeiraClient } from './neiraClient';

export enum ServerState {
    Stopped = 'stopped',
    Starting = 'starting',
    Running = 'running',
    Error = 'error'
}

export class NeiraServerManager {
    private client: NeiraClient;
    private serverProcess: cp.ChildProcess | undefined;
    private serverTerminal: vscode.Terminal | undefined;
    private statusBarItem: vscode.StatusBarItem;
    private state: ServerState = ServerState.Stopped;
    private healthCheckInterval: NodeJS.Timeout | undefined;
    private outputChannel: vscode.OutputChannel;
    
    private readonly onStateChangeEmitter = new vscode.EventEmitter<ServerState>();
    public readonly onStateChange = this.onStateChangeEmitter.event;

    constructor(client: NeiraClient) {
        this.client = client;
        this.outputChannel = vscode.window.createOutputChannel('Neira Server');
        
        // Создаём кнопку в статус-баре
        this.statusBarItem = vscode.window.createStatusBarItem(
            vscode.StatusBarAlignment.Left,
            50
        );
        this.statusBarItem.show();
        this.updateStatusBar();
    }

    /**
     * Инициализация при активации расширения
     */
    async initialize(): Promise<void> {
        const config = vscode.workspace.getConfiguration('neira');
        
        // Проверяем текущее состояние сервера
        const isRunning = await this.checkServerHealth();
        
        if (isRunning) {
            this.setState(ServerState.Running);
            this.log('✅ Сервер Нейры уже запущен');
        } else {
            // Автозапуск если включён
            const autoStart = config.get<boolean>('autoStartServer', false);
            if (autoStart) {
                this.log('🚀 Автозапуск сервера...');
                await this.startServer();
            } else {
                this.log('ℹ️ Сервер не запущен. Нажмите кнопку для запуска.');
            }
        }
        
        // Запускаем периодическую проверку состояния
        this.startHealthCheck();
    }

    /**
     * Запуск сервера
     */
    async startServer(): Promise<boolean> {
        if (this.state === ServerState.Running) {
            vscode.window.showInformationMessage('Сервер Нейры уже запущен');
            return true;
        }

        this.setState(ServerState.Starting);
        this.log('🚀 Запуск сервера Нейры...');

        const config = vscode.workspace.getConfiguration('neira');
        const pythonPath = config.get<string>('pythonPath', 'python');

        // Получаем путь к проекту (workspace → global → автопоиск)
        let projectPath = await this.getProjectPath();
        if (!projectPath) {
            vscode.window.showErrorMessage(
                'Не найден путь к проекту Neira. Укажите neira.projectPath в настройках.'
            );
            this.setState(ServerState.Error);
            return false;
        }

        this.log(`📁 Используется путь: ${projectPath}`);

        const serverScript = path.join(projectPath, 'neira_server.py');
        
        try {
            const isWindows = process.platform === 'win32';
            
            // На Windows используем cmd.exe с правильной кодировкой
            // PowerShell имеет проблемы с Unicode путями
            if (isWindows) {
                this.serverTerminal = vscode.window.createTerminal({
                    name: '🧠 Neira Server',
                    iconPath: new vscode.ThemeIcon('hubot'),
                    shellPath: 'cmd.exe',
                    shellArgs: ['/K', 'chcp 65001 > nul'],
                    env: {
                        'PYTHONIOENCODING': 'utf-8',
                        'PYTHONUTF8': '1'
                    }
                });
                
                // cmd.exe лучше работает с кириллицей
                // Используем cd /d для смены диска и папки
                this.serverTerminal.sendText(`cd /d "${projectPath}"`);
                this.serverTerminal.sendText(`"${pythonPath}" "${serverScript}"`);
            } else {
                this.serverTerminal = vscode.window.createTerminal({
                    name: '🧠 Neira Server',
                    cwd: projectPath,
                    iconPath: new vscode.ThemeIcon('hubot'),
                    env: {
                        'PYTHONIOENCODING': 'utf-8',
                        'PYTHONUTF8': '1'
                    }
                });
                this.serverTerminal.sendText(`"${pythonPath}" "${serverScript}"`);
            }
            
            this.log(`Запуск: ${pythonPath} ${serverScript}`);
            
            // Ждём запуска
            await this.waitForServer(15000);
            
            if (await this.checkServerHealth()) {
                this.setState(ServerState.Running);
                this.log('✅ Сервер успешно запущен!');
                vscode.window.showInformationMessage('🧠 Сервер Нейры запущен!');
                return true;
            } else {
                this.setState(ServerState.Error);
                this.log('❌ Сервер не отвечает после запуска');
                this.serverTerminal?.show();
                return false;
            }
            
        } catch (error: any) {
            this.setState(ServerState.Error);
            this.log(`❌ Ошибка запуска: ${error.message}`);
            vscode.window.showErrorMessage(`Ошибка запуска сервера: ${error.message}`);
            return false;
        }
    }

    /**
     * Остановка сервера
     */
    async stopServer(): Promise<void> {
        this.log('⏹️ Остановка сервера...');
        
        // Пытаемся остановить через API
        try {
            await this.client.request('/shutdown', { method: 'POST' });
        } catch {
            // Игнорируем — сервер может быть уже остановлен
        }
        
        // Закрываем терминал
        if (this.serverTerminal) {
            this.serverTerminal.dispose();
            this.serverTerminal = undefined;
        }
        
        // Убиваем процесс если запущен
        if (this.serverProcess) {
            this.serverProcess.kill();
            this.serverProcess = undefined;
        }
        
        this.setState(ServerState.Stopped);
        this.log('✅ Сервер остановлен');
        vscode.window.showInformationMessage('Сервер Нейры остановлен');
    }

    /**
     * Перезапуск сервера
     */
    async restartServer(): Promise<void> {
        await this.stopServer();
        await new Promise(resolve => setTimeout(resolve, 1000));
        await this.startServer();
    }

    /**
     * Переключение состояния (для кнопки)
     */
    async toggleServer(): Promise<void> {
        if (this.state === ServerState.Running) {
            await this.stopServer();
        } else {
            await this.startServer();
        }
    }

    /**
     * Получить текущее состояние
     */
    getState(): ServerState {
        return this.state;
    }

    /**
     * Проверка здоровья сервера
     */
    async checkServerHealth(): Promise<boolean> {
        try {
            const response = await this.client.checkHealth();
            return response?.success === true;
        } catch {
            return false;
        }
    }

    /**
     * Показать лог сервера
     */
    showOutput(): void {
        this.outputChannel.show();
        if (this.serverTerminal) {
            this.serverTerminal.show();
        }
    }

    /**
     * Освобождение ресурсов
     */
    dispose(): void {
        if (this.healthCheckInterval) {
            clearInterval(this.healthCheckInterval);
        }
        this.statusBarItem.dispose();
        this.outputChannel.dispose();
        if (this.serverTerminal) {
            this.serverTerminal.dispose();
        }
        this.onStateChangeEmitter.dispose();
    }

    // === Приватные методы ===

    private setState(state: ServerState): void {
        this.state = state;
        this.updateStatusBar();
        this.onStateChangeEmitter.fire(state);
    }

    private updateStatusBar(): void {
        switch (this.state) {
            case ServerState.Running:
                this.statusBarItem.text = '$(hubot) Нейра';
                this.statusBarItem.tooltip = 'Сервер Нейры работает. Нажмите для остановки.';
                this.statusBarItem.backgroundColor = undefined;
                this.statusBarItem.command = 'neira.toggleServer';
                break;
                
            case ServerState.Starting:
                this.statusBarItem.text = '$(loading~spin) Нейра...';
                this.statusBarItem.tooltip = 'Запуск сервера Нейры...';
                this.statusBarItem.backgroundColor = new vscode.ThemeColor('statusBarItem.warningBackground');
                this.statusBarItem.command = undefined;
                break;
                
            case ServerState.Stopped:
                this.statusBarItem.text = '$(debug-start) Нейра';
                this.statusBarItem.tooltip = 'Сервер остановлен. Нажмите для запуска.';
                this.statusBarItem.backgroundColor = undefined;
                this.statusBarItem.command = 'neira.toggleServer';
                break;
                
            case ServerState.Error:
                this.statusBarItem.text = '$(error) Нейра';
                this.statusBarItem.tooltip = 'Ошибка сервера. Нажмите для перезапуска.';
                this.statusBarItem.backgroundColor = new vscode.ThemeColor('statusBarItem.errorBackground');
                this.statusBarItem.command = 'neira.startServer';
                break;
        }
    }

    private log(message: string): void {
        const timestamp = new Date().toLocaleTimeString();
        this.outputChannel.appendLine(`[${timestamp}] ${message}`);
    }

    private async waitForServer(timeout: number): Promise<void> {
        const startTime = Date.now();
        const checkInterval = 500;
        
        while (Date.now() - startTime < timeout) {
            if (await this.checkServerHealth()) {
                return;
            }
            await new Promise(resolve => setTimeout(resolve, checkInterval));
        }
    }

    private startHealthCheck(): void {
        // Проверяем состояние каждые 30 секунд
        this.healthCheckInterval = setInterval(async () => {
            const wasRunning = this.state === ServerState.Running;
            const isRunning = await this.checkServerHealth();
            
            if (wasRunning && !isRunning) {
                this.setState(ServerState.Stopped);
                this.log('⚠️ Сервер остановился');
            } else if (!wasRunning && isRunning && this.state !== ServerState.Starting) {
                this.setState(ServerState.Running);
                this.log('✅ Сервер обнаружен');
            }
        }, 30000);
    }

    /**
     * Получить путь к проекту Neira
     * Приоритет: workspace settings → global settings → автопоиск → запрос у пользователя
     */
    private async getProjectPath(): Promise<string | undefined> {
        const config = vscode.workspace.getConfiguration('neira');
        
        // 1. Проверяем workspace-специфичные настройки (приоритет)
        const workspacePath = config.inspect<string>('projectPath')?.workspaceValue;
        if (workspacePath && await this.validateProjectPath(workspacePath)) {
            this.log(`✅ Используется workspace путь: ${workspacePath}`);
            return workspacePath;
        }
        
        // 2. Проверяем глобальные настройки
        const globalPath = config.inspect<string>('projectPath')?.globalValue;
        if (globalPath && await this.validateProjectPath(globalPath)) {
            this.log(`✅ Используется глобальный путь: ${globalPath}`);
            return globalPath;
        }
        
        // 3. Автопоиск
        this.log('🔍 Автоматический поиск проекта Neira...');
        const foundPath = await this.findProjectPath();
        if (foundPath) {
            this.log(`✅ Найден путь: ${foundPath}`);
            // Сохраняем в workspace settings (не глобально!)
            await this.saveProjectPath(foundPath, vscode.ConfigurationTarget.Workspace);
            return foundPath;
        }
        
        // 4. Спрашиваем пользователя
        return await this.askUserForProjectPath();
    }

    /**
     * Проверить валидность пути к проекту
     */
    private async validateProjectPath(projectPath: string): Promise<boolean> {
        if (!projectPath) return false;
        
        try {
            const serverPath = path.join(projectPath, 'neira_server.py');
            await vscode.workspace.fs.stat(vscode.Uri.file(serverPath));
            return true;
        } catch {
            return false;
        }
    }

    /**
     * Сохранить путь к проекту в настройки
     */
    private async saveProjectPath(projectPath: string, target: vscode.ConfigurationTarget): Promise<void> {
        try {
            await vscode.workspace.getConfiguration('neira').update(
                'projectPath',
                projectPath,
                target
            );
            const scope = target === vscode.ConfigurationTarget.Workspace ? 'workspace' : 'global';
            this.log(`💾 Путь сохранён (${scope}): ${projectPath}`);
        } catch (error: any) {
            this.log(`⚠️ Не удалось сохранить путь: ${error.message}`);
        }
    }

    /**
     * Автопоиск проекта в открытых workspace-папках и стандартных местах
     */
    private async findProjectPath(): Promise<string | undefined> {
        // 1. Проверяем открытые workspace-папки
        if (vscode.workspace.workspaceFolders) {
            for (const folder of vscode.workspace.workspaceFolders) {
                const serverPath = path.join(folder.uri.fsPath, 'neira_server.py');
                try {
                    await vscode.workspace.fs.stat(vscode.Uri.file(serverPath));
                    this.log(`🎯 Найден в workspace: ${folder.uri.fsPath}`);
                    return folder.uri.fsPath;
                } catch {
                    // Файл не найден, продолжаем
                }
            }
        }
        
        // 2. Проверяем родительскую папку расширения (для разработки)
        // Это может быть путь типа .../prototype/neira-vscode
        const extensionPath = vscode.extensions.getExtension('neira.neira-assistant')?.extensionPath;
        if (extensionPath) {
            const parentPath = path.dirname(extensionPath);
            const serverPath = path.join(parentPath, 'neira_server.py');
            try {
                await vscode.workspace.fs.stat(vscode.Uri.file(serverPath));
                this.log(`🎯 Найден рядом с расширением: ${parentPath}`);
                return parentPath;
            } catch {
                // Не найдено
            }
        }
        
        return undefined;
    }

    /**
     * Запросить у пользователя путь к проекту
     */
    private async askUserForProjectPath(): Promise<string | undefined> {
        const choice = await vscode.window.showWarningMessage(
            '⚠️ Не найден проект Neira. Выберите действие:',
            'Указать путь вручную',
            'Открыть папку с проектом',
            'Отмена'
        );

        if (choice === 'Отмена' || !choice) {
            return undefined;
        }

        if (choice === 'Открыть папку с проектом') {
            // Предлагаем открыть workspace с проектом
            vscode.commands.executeCommand('vscode.openFolder');
            return undefined;
        }

        // Диалог выбора папки
        const result = await vscode.window.showOpenDialog({
            canSelectFiles: false,
            canSelectFolders: true,
            canSelectMany: false,
            openLabel: 'Выбрать папку с Neira',
            title: 'Выберите папку проекта Neira (где находится neira_server.py)'
        });
        
        if (result && result[0]) {
            const selectedPath = result[0].fsPath;
            
            // Проверяем что там действительно есть neira_server.py
            if (await this.validateProjectPath(selectedPath)) {
                // Спрашиваем куда сохранить
                const saveChoice = await vscode.window.showQuickPick(
                    [
                        { label: 'Только для этого проекта', target: vscode.ConfigurationTarget.Workspace },
                        { label: 'Для всех проектов (глобально)', target: vscode.ConfigurationTarget.Global }
                    ],
                    { placeHolder: 'Куда сохранить путь к Neira?' }
                );
                
                const target = saveChoice?.target || vscode.ConfigurationTarget.Workspace;
                await this.saveProjectPath(selectedPath, target);
                return selectedPath;
            } else {
                vscode.window.showErrorMessage(
                    `❌ В выбранной папке не найден neira_server.py`
                );
                return undefined;
            }
        }
        
        return undefined;
    }
}

/**
 * Регистрация команд управления сервером
 */
export function registerServerCommands(
    context: vscode.ExtensionContext,
    serverManager: NeiraServerManager
): void {
    // Запуск сервера
    context.subscriptions.push(
        vscode.commands.registerCommand('neira.startServer', () => {
            serverManager.startServer();
        })
    );
    
    // Остановка сервера
    context.subscriptions.push(
        vscode.commands.registerCommand('neira.stopServer', () => {
            serverManager.stopServer();
        })
    );
    
    // Перезапуск сервера
    context.subscriptions.push(
        vscode.commands.registerCommand('neira.restartServer', () => {
            serverManager.restartServer();
        })
    );
    
    // Переключение состояния
    context.subscriptions.push(
        vscode.commands.registerCommand('neira.toggleServer', () => {
            serverManager.toggleServer();
        })
    );
    
    // Показать лог
    context.subscriptions.push(
        vscode.commands.registerCommand('neira.showServerLog', () => {
            serverManager.showOutput();
        })
    );
}
