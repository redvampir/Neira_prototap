/**
 * Neira Status View Provider
 * TreeView для отображения статуса
 */

import * as vscode from 'vscode';

interface ServerStatus {
    status: string;
    neira_ready: boolean;
    uptime_seconds: number;
    requests_processed: number;
    websocket_clients: number;
    version: string;
}

export class NeiraStatusViewProvider implements vscode.TreeDataProvider<vscode.TreeItem> {
    private _onDidChangeTreeData = new vscode.EventEmitter<vscode.TreeItem | undefined | null | void>();
    readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

    private _online: boolean = false;
    private _status: ServerStatus | null = null;

    updateStatus(online: boolean, status: ServerStatus | null) {
        this._online = online;
        this._status = status;
        this._onDidChangeTreeData.fire();
    }

    getTreeItem(element: vscode.TreeItem): vscode.TreeItem {
        return element;
    }

    getChildren(): vscode.TreeItem[] {
        const items: vscode.TreeItem[] = [];

        if (this._online && this._status) {
            const statusItem = new vscode.TreeItem('Статус', vscode.TreeItemCollapsibleState.None);
            statusItem.description = '🟢 Онлайн';
            statusItem.iconPath = new vscode.ThemeIcon('check');
            items.push(statusItem);

            const neiraItem = new vscode.TreeItem('Нейра', vscode.TreeItemCollapsibleState.None);
            neiraItem.description = this._status.neira_ready ? 'Готова' : 'Загружается...';
            neiraItem.iconPath = new vscode.ThemeIcon(this._status.neira_ready ? 'symbol-misc' : 'loading~spin');
            items.push(neiraItem);

            const requestsItem = new vscode.TreeItem('Запросов', vscode.TreeItemCollapsibleState.None);
            requestsItem.description = String(this._status.requests_processed);
            requestsItem.iconPath = new vscode.ThemeIcon('graph');
            items.push(requestsItem);

            const uptimeItem = new vscode.TreeItem('Аптайм', vscode.TreeItemCollapsibleState.None);
            uptimeItem.description = this.formatUptime(this._status.uptime_seconds);
            uptimeItem.iconPath = new vscode.ThemeIcon('clock');
            items.push(uptimeItem);

            const versionItem = new vscode.TreeItem('Версия', vscode.TreeItemCollapsibleState.None);
            versionItem.description = this._status.version;
            versionItem.iconPath = new vscode.ThemeIcon('tag');
            items.push(versionItem);

        } else {
            const offlineItem = new vscode.TreeItem('Статус', vscode.TreeItemCollapsibleState.None);
            offlineItem.description = '🔴 Офлайн';
            offlineItem.iconPath = new vscode.ThemeIcon('warning');
            items.push(offlineItem);

            const actionItem = new vscode.TreeItem('Действие', vscode.TreeItemCollapsibleState.None);
            actionItem.description = 'Запустите neira_server.py';
            actionItem.iconPath = new vscode.ThemeIcon('play');
            items.push(actionItem);
        }

        return items;
    }

    private formatUptime(seconds: number): string {
        if (seconds < 60) {
            return `${Math.round(seconds)} сек`;
        } else if (seconds < 3600) {
            return `${Math.round(seconds / 60)} мин`;
        } else {
            const hours = Math.floor(seconds / 3600);
            const mins = Math.round((seconds % 3600) / 60);
            return `${hours} ч ${mins} мин`;
        }
    }
}
