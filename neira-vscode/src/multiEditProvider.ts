/**
 * Multi-file Edit Provider — Пакетное редактирование с Diff Preview
 * 
 * Позволяет:
 * - Применять правки к нескольким файлам
 * - Предварительный просмотр изменений (diff)
 * - Откат изменений
 * - Workspace Edit API интеграция
 */

import * as vscode from 'vscode';
import * as path from 'path';

export interface FileEdit {
    /** Путь к файлу (относительный или абсолютный) */
    filePath: string;
    /** Текст для замены */
    oldText: string;
    /** Новый текст */
    newText: string;
    /** Описание изменения */
    description?: string;
}

export interface EditPlan {
    /** Название плана */
    name: string;
    /** Описание */
    description: string;
    /** Список правок */
    edits: FileEdit[];
    /** Дата создания */
    createdAt: Date;
}

export interface EditResult {
    filePath: string;
    success: boolean;
    error?: string;
}

export class NeiraMultiEditProvider {
    private outputChannel: vscode.OutputChannel;
    private editHistory: EditPlan[] = [];
    private undoStack: Map<string, string> = new Map(); // filePath -> originalContent

    constructor() {
        this.outputChannel = vscode.window.createOutputChannel('Neira Edits');
    }

    /**
     * Создаёт план редактирования
     */
    createPlan(name: string, description: string, edits: FileEdit[]): EditPlan {
        const plan: EditPlan = {
            name,
            description,
            edits,
            createdAt: new Date()
        };
        
        this.editHistory.push(plan);
        return plan;
    }

    /**
     * Применяет план редактирования с предварительным просмотром
     */
    async applyPlanWithPreview(plan: EditPlan): Promise<boolean> {
        // Показываем preview
        const confirmed = await this.showDiffPreview(plan);
        
        if (!confirmed) {
            vscode.window.showInformationMessage('Редактирование отменено');
            return false;
        }

        return this.applyPlan(plan);
    }

    /**
     * Применяет план редактирования
     */
    async applyPlan(plan: EditPlan): Promise<boolean> {
        const workspaceEdit = new vscode.WorkspaceEdit();
        const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '';
        
        this.outputChannel.appendLine(`\n📦 Применяю план: ${plan.name}`);
        this.outputChannel.appendLine(`   Файлов: ${plan.edits.length}`);
        
        // Сохраняем оригиналы для undo
        for (const edit of plan.edits) {
            const fullPath = path.isAbsolute(edit.filePath) 
                ? edit.filePath 
                : path.join(workspaceRoot, edit.filePath);
            
            try {
                const uri = vscode.Uri.file(fullPath);
                const doc = await vscode.workspace.openTextDocument(uri);
                this.undoStack.set(fullPath, doc.getText());
            } catch {
                // Новый файл
            }
        }

        // Собираем все правки
        for (const edit of plan.edits) {
            const fullPath = path.isAbsolute(edit.filePath) 
                ? edit.filePath 
                : path.join(workspaceRoot, edit.filePath);
            
            const uri = vscode.Uri.file(fullPath);

            try {
                const doc = await vscode.workspace.openTextDocument(uri);
                const content = doc.getText();
                
                // Находим позицию для замены
                const startIndex = content.indexOf(edit.oldText);
                
                if (startIndex === -1) {
                    this.outputChannel.appendLine(`❌ ${edit.filePath}: текст не найден`);
                    continue;
                }

                const startPos = doc.positionAt(startIndex);
                const endPos = doc.positionAt(startIndex + edit.oldText.length);
                const range = new vscode.Range(startPos, endPos);

                workspaceEdit.replace(uri, range, edit.newText);
                this.outputChannel.appendLine(`✏️ ${edit.filePath}: ${edit.description || 'редактирование'}`);
                
            } catch (error) {
                // Файл не существует - создаём новый
                if (edit.oldText === '' && edit.newText) {
                    workspaceEdit.createFile(uri, { 
                        overwrite: false, 
                        ignoreIfExists: false 
                    });
                    workspaceEdit.insert(uri, new vscode.Position(0, 0), edit.newText);
                    this.outputChannel.appendLine(`📄 ${edit.filePath}: создан новый файл`);
                } else {
                    this.outputChannel.appendLine(`❌ ${edit.filePath}: ${error}`);
                }
            }
        }

        // Применяем все правки атомарно
        const success = await vscode.workspace.applyEdit(workspaceEdit);
        
        if (success) {
            this.outputChannel.appendLine(`\n✅ План "${plan.name}" применён успешно`);
            vscode.window.showInformationMessage(
                `✅ Изменено ${plan.edits.length} файлов`,
                'Показать Diff'
            ).then(selection => {
                if (selection === 'Показать Diff') {
                    this.outputChannel.show();
                }
            });
        } else {
            this.outputChannel.appendLine(`\n❌ Ошибка применения плана`);
            vscode.window.showErrorMessage('Ошибка при применении изменений');
        }

        return success;
    }

    /**
     * Показывает preview изменений
     */
    async showDiffPreview(plan: EditPlan): Promise<boolean> {
        const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '';
        
        // Создаём виртуальные документы для сравнения
        const diffs: { file: string; before: string; after: string }[] = [];
        
        for (const edit of plan.edits) {
            const fullPath = path.isAbsolute(edit.filePath) 
                ? edit.filePath 
                : path.join(workspaceRoot, edit.filePath);
            
            try {
                const uri = vscode.Uri.file(fullPath);
                const doc = await vscode.workspace.openTextDocument(uri);
                const before = doc.getText();
                const after = before.replace(edit.oldText, edit.newText);
                
                diffs.push({
                    file: edit.filePath,
                    before,
                    after
                });
            } catch {
                // Новый файл
                diffs.push({
                    file: edit.filePath,
                    before: '',
                    after: edit.newText
                });
            }
        }

        // Показываем QuickPick с файлами
        const items = diffs.map(d => ({
            label: `$(file) ${d.file}`,
            description: d.before ? 'Изменён' : 'Новый файл',
            detail: this.getShortDiff(d.before, d.after),
            diff: d
        }));

        items.unshift({
            label: '$(check) Применить все изменения',
            description: `${plan.edits.length} файлов`,
            detail: plan.description,
            diff: null as any
        });

        items.push({
            label: '$(x) Отмена',
            description: '',
            detail: '',
            diff: null as any
        });

        const selected = await vscode.window.showQuickPick(items, {
            placeHolder: `Preview: ${plan.name}`,
            matchOnDetail: true
        });

        if (!selected) {
            return false;
        }

        if (selected.label.includes('Применить')) {
            return true;
        }

        if (selected.label.includes('Отмена')) {
            return false;
        }

        // Показываем diff для конкретного файла
        if (selected.diff) {
            await this.showFileDiff(selected.diff.file, selected.diff.before, selected.diff.after);
            // После просмотра diff спрашиваем снова
            return this.showDiffPreview(plan);
        }

        return false;
    }

    /**
     * Показывает diff для одного файла
     */
    async showFileDiff(filename: string, before: string, after: string): Promise<void> {
        // Создаём временные URI для сравнения
        const beforeUri = vscode.Uri.parse(`neira-diff:before/${filename}`);
        const afterUri = vscode.Uri.parse(`neira-diff:after/${filename}`);

        // Регистрируем провайдер для виртуальных документов
        const provider = new (class implements vscode.TextDocumentContentProvider {
            contents = new Map<string, string>();
            
            provideTextDocumentContent(uri: vscode.Uri): string {
                return this.contents.get(uri.toString()) || '';
            }
        })();

        provider.contents.set(beforeUri.toString(), before);
        provider.contents.set(afterUri.toString(), after);

        const disposable = vscode.workspace.registerTextDocumentContentProvider('neira-diff', provider);

        try {
            await vscode.commands.executeCommand('vscode.diff', 
                beforeUri, 
                afterUri, 
                `${filename} (Предпросмотр изменений)`
            );
        } finally {
            // Не удаляем сразу, иначе diff не покажется
            setTimeout(() => disposable.dispose(), 60000);
        }
    }

    /**
     * Генерирует короткий diff для preview
     */
    private getShortDiff(before: string, after: string): string {
        const beforeLines = before.split('\n').length;
        const afterLines = after.split('\n').length;
        
        const added = afterLines - beforeLines;
        const changed = before !== after;
        
        if (!before) {
            return `+${afterLines} строк (новый файл)`;
        }
        
        if (added > 0) {
            return `+${added} строк`;
        } else if (added < 0) {
            return `${added} строк`;
        } else if (changed) {
            return 'Изменено содержимое';
        }
        
        return 'Без изменений';
    }

    /**
     * Откатывает последний план
     */
    async undoLastPlan(): Promise<boolean> {
        if (this.undoStack.size === 0) {
            vscode.window.showInformationMessage('Нечего отменять');
            return false;
        }

        const workspaceEdit = new vscode.WorkspaceEdit();

        for (const [filePath, originalContent] of this.undoStack) {
            const uri = vscode.Uri.file(filePath);
            
            try {
                const doc = await vscode.workspace.openTextDocument(uri);
                const fullRange = new vscode.Range(
                    doc.positionAt(0),
                    doc.positionAt(doc.getText().length)
                );
                workspaceEdit.replace(uri, fullRange, originalContent);
            } catch {
                continue;
            }
        }

        const success = await vscode.workspace.applyEdit(workspaceEdit);
        
        if (success) {
            this.undoStack.clear();
            vscode.window.showInformationMessage('✅ Изменения отменены');
        }

        return success;
    }

    /**
     * Парсит правки из ответа LLM
     */
    parseEditsFromLLM(text: string): FileEdit[] {
        const edits: FileEdit[] = [];
        
        // Ищем блоки вида:
        // ```edit:path/to/file.py
        // <<<< OLD
        // старый код
        // ====
        // новый код
        // >>>> NEW
        // ```
        
        const editBlockPattern = /```edit:([^\n]+)\n<<<< OLD\n([\s\S]*?)\n====\n([\s\S]*?)\n>>>> NEW\n```/g;
        
        let match;
        while ((match = editBlockPattern.exec(text)) !== null) {
            edits.push({
                filePath: match[1].trim(),
                oldText: match[2],
                newText: match[3]
            });
        }

        // Альтернативный формат:
        // FILE: path/to/file.py
        // REPLACE:
        // ```
        // old code
        // ```
        // WITH:
        // ```
        // new code
        // ```
        
        const altPattern = /FILE:\s*([^\n]+)\nREPLACE:\s*\n```[^\n]*\n([\s\S]*?)\n```\s*\nWITH:\s*\n```[^\n]*\n([\s\S]*?)\n```/g;
        
        while ((match = altPattern.exec(text)) !== null) {
            edits.push({
                filePath: match[1].trim(),
                oldText: match[2],
                newText: match[3]
            });
        }

        return edits;
    }

    /**
     * Создаёт и применяет правки из ответа LLM
     */
    async applyLLMEdits(llmResponse: string, description: string = 'AI-generated edits'): Promise<boolean> {
        const edits = this.parseEditsFromLLM(llmResponse);
        
        if (edits.length === 0) {
            vscode.window.showWarningMessage('Не найдено правок в ответе');
            return false;
        }

        const plan = this.createPlan('AI Edits', description, edits);
        return this.applyPlanWithPreview(plan);
    }

    /**
     * История редактирований
     */
    getHistory(): EditPlan[] {
        return [...this.editHistory];
    }

    dispose(): void {
        this.outputChannel.dispose();
    }
}

/**
 * Регистрирует команды multi-file edit
 */
export function registerMultiEditCommands(
    context: vscode.ExtensionContext,
    multiEditProvider: NeiraMultiEditProvider
): void {
    
    // Отменить последние изменения
    context.subscriptions.push(
        vscode.commands.registerCommand('neira.undoEdits', async () => {
            await multiEditProvider.undoLastPlan();
        })
    );

    // Показать историю редактирований
    context.subscriptions.push(
        vscode.commands.registerCommand('neira.editHistory', async () => {
            const history = multiEditProvider.getHistory();
            
            if (history.length === 0) {
                vscode.window.showInformationMessage('История редактирований пуста');
                return;
            }

            const items = history.map(h => ({
                label: h.name,
                description: `${h.edits.length} файлов`,
                detail: h.description
            }));

            await vscode.window.showQuickPick(items, {
                placeHolder: 'История редактирований'
            });
        })
    );
}
