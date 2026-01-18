import * as vscode from 'vscode';
import { NeiraClient } from './neiraClient';

class ModelTreeItem extends vscode.TreeItem {
    constructor(public readonly key: string, public readonly info: any) {
        super(info.name || key, vscode.TreeItemCollapsibleState.None);
        this.description = `${info.type || ''} ${info.size_gb ? `· ${info.size_gb}GB` : ''}`.trim();
        this.contextValue = 'modelItem';
        this.command = {
            command: 'neira.switchModel',
            title: 'Switch Model',
            arguments: [this]
        } as any;
    }
}

export class NeiraModelsProvider implements vscode.TreeDataProvider<vscode.TreeItem> {
    private _onDidChangeTreeData = new vscode.EventEmitter<vscode.TreeItem | undefined | void>();
    readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

    constructor(private client: NeiraClient) {}

    refresh(): void {
        this._onDidChangeTreeData.fire();
    }

    getTreeItem(element: vscode.TreeItem): vscode.TreeItem {
        return element;
    }

    async getChildren(element?: vscode.TreeItem): Promise<vscode.TreeItem[]> {
        if (element) return [];
        try {
            const resp = await this.client.listModels();
            const anyResp: any = resp as any;
            const data = anyResp?.models ? anyResp.models : resp.data?.models;
            if (!data) return [];
            return Object.keys(data).map(k => new ModelTreeItem(k, data[k]));
        } catch {
            return [];
        }
    }
}

export function registerModelsView(context: vscode.ExtensionContext, client: NeiraClient): NeiraModelsProvider {
    const provider = new NeiraModelsProvider(client);
    context.subscriptions.push(vscode.window.registerTreeDataProvider('neira.modelsView', provider));

    context.subscriptions.push(vscode.commands.registerCommand('neira.refreshModels', () => provider.refresh()));

    context.subscriptions.push(vscode.commands.registerCommand('neira.switchModel', async (item: any) => {
        const key = item && item.key ? item.key : await vscode.window.showInputBox({ prompt: 'Model key' });
        if (!key) return;
        const res = await client.request('/models/switch', { key });
        if (res && res.success) {
            vscode.window.showInformationMessage(`Switched to ${key}`);
        } else {
            vscode.window.showErrorMessage(res?.error || 'Switch failed');
        }
    }));

    return provider;
}
