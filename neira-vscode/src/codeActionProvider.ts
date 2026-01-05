/**
 * Neira Code Action Provider
 * Quick Fix для ошибок и генерация документации/тестов
 */

import * as vscode from 'vscode';
import { NeiraClient } from './neiraClient';

export class NeiraCodeActionProvider implements vscode.CodeActionProvider {
    public static readonly providedCodeActionKinds = [
        vscode.CodeActionKind.QuickFix,
        vscode.CodeActionKind.RefactorRewrite,
        vscode.CodeActionKind.Source
    ];

    private _client: NeiraClient;

    constructor(client: NeiraClient) {
        this._client = client;
    }

    provideCodeActions(
        document: vscode.TextDocument,
        range: vscode.Range | vscode.Selection,
        context: vscode.CodeActionContext,
        _token: vscode.CancellationToken
    ): vscode.CodeAction[] | undefined {
        const actions: vscode.CodeAction[] = [];

        // Quick Fix для каждой ошибки
        for (const diagnostic of context.diagnostics) {
            if (diagnostic.severity === vscode.DiagnosticSeverity.Error ||
                diagnostic.severity === vscode.DiagnosticSeverity.Warning) {
                
                const fixAction = this._createFixAction(document, diagnostic);
                actions.push(fixAction);
            }
        }

        // Если есть выделение - предлагаем рефакторинг
        if (!range.isEmpty) {
            actions.push(this._createDocstringAction(document, range));
            actions.push(this._createTestAction(document, range));
            actions.push(this._createRefactorAction(document, range));
            actions.push(this._createExplainAction(document, range));
        }

        // Если курсор на функции/классе - предлагаем документацию
        const lineText = document.lineAt(range.start.line).text;
        if (this._isFunctionOrClass(lineText, document.languageId)) {
            actions.push(this._createDocstringAction(document, range));
            actions.push(this._createTestAction(document, range));
        }

        return actions;
    }

    private _createFixAction(document: vscode.TextDocument, diagnostic: vscode.Diagnostic): vscode.CodeAction {
        const action = new vscode.CodeAction(
            `🧠 Нейра: Исправить "${diagnostic.message.substring(0, 50)}..."`,
            vscode.CodeActionKind.QuickFix
        );
        
        action.command = {
            command: 'neira.fixError',
            title: 'Fix with Neira',
            arguments: [document, diagnostic]
        };
        
        action.diagnostics = [diagnostic];
        action.isPreferred = false; // Не делаем предпочтительным, чтобы не мешать встроенным фиксам
        
        return action;
    }

    private _createDocstringAction(document: vscode.TextDocument, range: vscode.Range): vscode.CodeAction {
        const action = new vscode.CodeAction(
            '📝 Нейра: Добавить документацию',
            vscode.CodeActionKind.RefactorRewrite
        );
        
        action.command = {
            command: 'neira.generateDocs',
            title: 'Generate Documentation',
            arguments: [document, range]
        };
        
        return action;
    }

    private _createTestAction(document: vscode.TextDocument, range: vscode.Range): vscode.CodeAction {
        const action = new vscode.CodeAction(
            '🧪 Нейра: Сгенерировать тесты',
            vscode.CodeActionKind.Source
        );
        
        action.command = {
            command: 'neira.generateTests',
            title: 'Generate Tests',
            arguments: [document, range]
        };
        
        return action;
    }

    private _createRefactorAction(document: vscode.TextDocument, range: vscode.Range): vscode.CodeAction {
        const action = new vscode.CodeAction(
            '♻️ Нейра: Улучшить код',
            vscode.CodeActionKind.RefactorRewrite
        );
        
        action.command = {
            command: 'neira.refactorCode',
            title: 'Refactor Code',
            arguments: [document, range]
        };
        
        return action;
    }

    private _createExplainAction(document: vscode.TextDocument, range: vscode.Range): vscode.CodeAction {
        const action = new vscode.CodeAction(
            '💡 Нейра: Объяснить код',
            vscode.CodeActionKind.Source
        );
        
        action.command = {
            command: 'neira.explainCode',
            title: 'Explain Code',
            arguments: [document.getText(range)]
        };
        
        return action;
    }

    private _isFunctionOrClass(line: string, languageId: string): boolean {
        const trimmed = line.trim();
        
        switch (languageId) {
            case 'python':
                return trimmed.startsWith('def ') || 
                       trimmed.startsWith('class ') ||
                       trimmed.startsWith('async def ');
            
            case 'javascript':
            case 'typescript':
            case 'javascriptreact':
            case 'typescriptreact':
                return trimmed.startsWith('function ') ||
                       trimmed.startsWith('async function ') ||
                       trimmed.startsWith('class ') ||
                       trimmed.includes('=>') ||
                       /^\s*(export\s+)?(const|let|var)\s+\w+\s*=\s*(async\s+)?(\([^)]*\)|[^=])\s*=>/.test(line);
            
            case 'java':
            case 'csharp':
            case 'cpp':
            case 'c':
                return /^\s*(public|private|protected|static|async|virtual|override)?\s*(void|int|string|bool|Task|async)?\s*\w+\s*\(/.test(line) ||
                       trimmed.startsWith('class ');
            
            case 'go':
                return trimmed.startsWith('func ') || trimmed.startsWith('type ');
            
            case 'rust':
                return trimmed.startsWith('fn ') || 
                       trimmed.startsWith('pub fn ') ||
                       trimmed.startsWith('struct ') ||
                       trimmed.startsWith('impl ');
            
            default:
                return false;
        }
    }
}

/**
 * Code Lens Provider - показывает кнопки над функциями/классами
 */
export class NeiraCodeLensProvider implements vscode.CodeLensProvider {
    private _onDidChangeCodeLenses = new vscode.EventEmitter<void>();
    public readonly onDidChangeCodeLenses = this._onDidChangeCodeLenses.event;

    private _enabled = true;

    public setEnabled(enabled: boolean) {
        this._enabled = enabled;
        this._onDidChangeCodeLenses.fire();
    }

    provideCodeLenses(
        document: vscode.TextDocument,
        _token: vscode.CancellationToken
    ): vscode.CodeLens[] | undefined {
        if (!this._enabled) {
            return undefined;
        }

        const lenses: vscode.CodeLens[] = [];
        const languageId = document.languageId;

        for (let i = 0; i < document.lineCount; i++) {
            const line = document.lineAt(i);
            const text = line.text;

            if (this._isFunctionOrClassStart(text, languageId)) {
                const range = new vscode.Range(i, 0, i, text.length);

                // Кнопка "Документация"
                lenses.push(new vscode.CodeLens(range, {
                    title: '📝 Документация',
                    command: 'neira.generateDocs',
                    arguments: [document, range]
                }));

                // Кнопка "Тесты"
                lenses.push(new vscode.CodeLens(range, {
                    title: '🧪 Тесты',
                    command: 'neira.generateTests',
                    arguments: [document, range]
                }));
            }
        }

        return lenses;
    }

    private _isFunctionOrClassStart(line: string, languageId: string): boolean {
        const trimmed = line.trim();
        
        switch (languageId) {
            case 'python':
                return (trimmed.startsWith('def ') || 
                        trimmed.startsWith('class ') ||
                        trimmed.startsWith('async def ')) &&
                       !trimmed.startsWith('#');
            
            case 'javascript':
            case 'typescript':
            case 'javascriptreact':
            case 'typescriptreact':
                return (trimmed.startsWith('function ') ||
                        trimmed.startsWith('async function ') ||
                        trimmed.startsWith('class ') ||
                        trimmed.startsWith('export function ') ||
                        trimmed.startsWith('export async function ') ||
                        trimmed.startsWith('export class ')) &&
                       !trimmed.startsWith('//');
            
            case 'java':
            case 'csharp':
                return (trimmed.startsWith('public ') ||
                        trimmed.startsWith('private ') ||
                        trimmed.startsWith('protected ') ||
                        trimmed.startsWith('class ')) &&
                       !trimmed.startsWith('//');
            
            default:
                return false;
        }
    }
}
