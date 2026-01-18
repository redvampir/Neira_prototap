/**
 * Neira Git Provider
 * Генерация commit messages и помощь с Git
 */

import * as vscode from 'vscode';
import { NeiraClient } from './neiraClient';

export class NeiraGitProvider {
    private _client: NeiraClient;

    constructor(client: NeiraClient) {
        this._client = client;
    }

    /**
     * Генерирует commit message на основе staged изменений
     */
    async generateCommitMessage(): Promise<string | undefined> {
        // Получаем Git extension
        const gitExtension = vscode.extensions.getExtension('vscode.git');
        if (!gitExtension) {
            vscode.window.showErrorMessage('Git extension не найден');
            return undefined;
        }

        const git = gitExtension.exports.getAPI(1);
        if (!git.repositories.length) {
            vscode.window.showErrorMessage('Git репозиторий не найден');
            return undefined;
        }

        const repo = git.repositories[0];
        
        // Получаем staged changes
        const stagedChanges = repo.state.indexChanges;
        if (!stagedChanges.length) {
            vscode.window.showWarningMessage('Нет staged изменений. Добавьте файлы через git add.');
            return undefined;
        }

        // Собираем diff
        let diff = '';
        try {
            diff = await repo.diff(true); // true = staged only
        } catch (error) {
            console.error('Error getting diff:', error);
            vscode.window.showErrorMessage('Не удалось получить diff');
            return undefined;
        }

        if (!diff || diff.trim().length === 0) {
            vscode.window.showWarningMessage('Diff пуст');
            return undefined;
        }

        // Ограничиваем размер diff
        const maxDiffLength = 4000;
        if (diff.length > maxDiffLength) {
            diff = diff.substring(0, maxDiffLength) + '\n\n... (diff обрезан)';
        }

        // Запрашиваем у Нейры commit message
        const response = await vscode.window.withProgress({
            location: vscode.ProgressLocation.Notification,
            title: '🧠 Нейра генерирует commit message...',
            cancellable: false
        }, async () => {
            return this._client.generateCommitMessage(diff);
        });

        if (response.success && response.data?.message) {
            return response.data.message;
        }

        vscode.window.showErrorMessage('Не удалось сгенерировать commit message');
        return undefined;
    }

    /**
     * Генерирует и вставляет commit message в поле ввода SCM
     */
    async generateAndInsertCommitMessage(): Promise<void> {
        const message = await this.generateCommitMessage();
        
        if (message) {
            const gitExtension = vscode.extensions.getExtension('vscode.git');
            if (gitExtension) {
                const git = gitExtension.exports.getAPI(1);
                if (git.repositories.length > 0) {
                    const repo = git.repositories[0];
                    repo.inputBox.value = message;
                    
                    vscode.window.showInformationMessage(
                        '✅ Commit message сгенерирован! Проверьте и нажмите Commit.',
                        'Commit'
                    ).then(selection => {
                        if (selection === 'Commit') {
                            vscode.commands.executeCommand('git.commit');
                        }
                    });
                }
            }
        }
    }

    /**
     * Объясняет текущий diff
     */
    async explainChanges(): Promise<void> {
        const gitExtension = vscode.extensions.getExtension('vscode.git');
        if (!gitExtension) {
            vscode.window.showErrorMessage('Git extension не найден');
            return;
        }

        const git = gitExtension.exports.getAPI(1);
        if (!git.repositories.length) {
            vscode.window.showErrorMessage('Git репозиторий не найден');
            return;
        }

        const repo = git.repositories[0];
        
        let diff = '';
        try {
            // Сначала пробуем staged, потом unstaged
            diff = await repo.diff(true);
            if (!diff.trim()) {
                diff = await repo.diff(false);
            }
        } catch (error) {
            console.error('Error getting diff:', error);
        }

        if (!diff || !diff.trim()) {
            vscode.window.showWarningMessage('Нет изменений для анализа');
            return;
        }

        // Ограничиваем размер
        const maxDiffLength = 4000;
        if (diff.length > maxDiffLength) {
            diff = diff.substring(0, maxDiffLength) + '\n\n... (diff обрезан)';
        }

        const response = await vscode.window.withProgress({
            location: vscode.ProgressLocation.Notification,
            title: '🧠 Нейра анализирует изменения...',
            cancellable: false
        }, async () => {
            return this._client.explainDiff(diff);
        });

        if (response.success && response.data?.explanation) {
            // Показываем в новом документе
            const doc = await vscode.workspace.openTextDocument({
                content: `# 📊 Анализ изменений от Нейры\n\n${response.data.explanation}`,
                language: 'markdown'
            });
            await vscode.window.showTextDocument(doc, { preview: true });
        } else {
            vscode.window.showErrorMessage('Не удалось проанализировать изменения');
        }
    }
}
