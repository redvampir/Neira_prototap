/**
 * Neira VS Code Extension - Main Entry Point
 * Локальный AI-ассистент для VS Code и Cursor
 */

import * as vscode from 'vscode';
import { NeiraClient } from './neiraClient';
import { NeiraChatViewProvider } from './chatViewProvider';
import { NeiraStatusViewProvider } from './statusViewProvider';
import { NeiraInlineCompletionProvider } from './inlineCompletionProvider';
import { NeiraCodeActionProvider, NeiraCodeLensProvider } from './codeActionProvider';
import { NeiraGitProvider } from './gitProvider';
import { NeiraFileSystemProvider, registerFileSystemCommands } from './fileSystemProvider';
import { NeiraToolProvider, registerToolCommands } from './toolProvider';
import { NeiraMultiEditProvider, registerMultiEditCommands } from './multiEditProvider';
import { NeiraIndexerProvider, NeiraWorkspaceSymbolProvider, NeiraHoverWithContext } from './indexerProvider';
import { NeiraContextProvider, TokenCountStatusBar, registerContextCommands } from './contextProvider';
import { NeiraSelfAwareProvider, NeiraFeedbackProvider, registerSelfAwareCommands } from './selfAwareProvider';
import { NeiraLearningProvider, registerLearningCommands } from './learningProvider';
import { NeiraServerManager, registerServerCommands } from './serverManager';
import { NeiraActionsProvider, registerActionsView } from './actionsViewProvider';
import { NeiraModelsProvider, registerModelsView } from './modelsViewProvider';
import { registerCopilotChatParticipant, PARTICIPANT_ID } from './copilotChatParticipant';

let client: NeiraClient;
let serverManager: NeiraServerManager;
let actionsProvider: NeiraActionsProvider;
let statusBarItem: vscode.StatusBarItem;
let inlineCompletionProvider: NeiraInlineCompletionProvider;
let gitProvider: NeiraGitProvider;
let fsProvider: NeiraFileSystemProvider;
let toolProvider: NeiraToolProvider;
let multiEditProvider: NeiraMultiEditProvider;
let indexerProvider: NeiraIndexerProvider;
let contextProvider: NeiraContextProvider;
let tokenStatusBar: TokenCountStatusBar;
let selfAwareProvider: NeiraSelfAwareProvider;
let feedbackProvider: NeiraFeedbackProvider;
let learningProvider: NeiraLearningProvider;

export async function activate(context: vscode.ExtensionContext) {

        // ...existing code...
    console.log('🧠 Neira Extension активируется...');

    // Инициализация клиента
    const config = vscode.workspace.getConfiguration('neira');
    const serverUrl = config.get<string>('serverUrl', 'http://127.0.0.1:8765');
    client = new NeiraClient(serverUrl);

    // Инициализация провайдеров
    inlineCompletionProvider = new NeiraInlineCompletionProvider(client);
    gitProvider = new NeiraGitProvider(client);
    fsProvider = new NeiraFileSystemProvider(client);
    toolProvider = new NeiraToolProvider(client);
    multiEditProvider = new NeiraMultiEditProvider();
    indexerProvider = new NeiraIndexerProvider(client);
    contextProvider = new NeiraContextProvider(client);
    tokenStatusBar = new TokenCountStatusBar(contextProvider);
    selfAwareProvider = new NeiraSelfAwareProvider(client);
    feedbackProvider = new NeiraFeedbackProvider(client, selfAwareProvider);

    // Регистрируем команды файловой системы
    registerFileSystemCommands(context, fsProvider);
    
    // Регистрируем команды инструментов
    registerToolCommands(context, toolProvider);
    
    // Регистрируем команды multi-edit
    registerMultiEditCommands(context, multiEditProvider);
    
    // Регистрируем команды самоосознания
    registerSelfAwareCommands(context, selfAwareProvider, feedbackProvider);
    
    // Регистрируем команды обучения
    learningProvider = new NeiraLearningProvider(client);
    registerLearningCommands(context, learningProvider);

    // Инициализируем менеджер сервера (автозапуск и кнопка)
    serverManager = new NeiraServerManager(client);
    registerServerCommands(context, serverManager);
    context.subscriptions.push({ dispose: () => serverManager.dispose() });
    
    // Инициализация сервера (проверка/автозапуск)
    await serverManager.initialize();

    // Устанавливаем workspace на сервере при активации
    fsProvider.setWorkspace().catch(() => {
        // Игнорируем если сервер недоступен
    });

    // Создаём Status Bar
    statusBarItem = vscode.window.createStatusBarItem(
        vscode.StatusBarAlignment.Right,
        100
    );
    statusBarItem.command = 'neira.openChat';
    context.subscriptions.push(statusBarItem);

    // Показываем статус
    if (config.get<boolean>('showStatusBar', true)) {
        updateStatusBar('checking');
        statusBarItem.show();
    }

    // Регистрируем Chat View Provider
    const chatViewProvider = new NeiraChatViewProvider(context.extensionUri, client, context);
    context.subscriptions.push(
        vscode.window.registerWebviewViewProvider(
            'neira.chatView',
            chatViewProvider
        )
    );

    // Регистрируем Status View Provider
    const statusViewProvider = new NeiraStatusViewProvider();
    context.subscriptions.push(
        vscode.window.registerTreeDataProvider(
            'neira.statusView',
            statusViewProvider
        )
    );

    // Регистрируем Actions View Provider (панель быстрых действий)
    actionsProvider = registerActionsView(context, client);

    // Регистрируем Inline Completion Provider (Ghost Text)
    if (config.get<boolean>('enableInlineCompletions', true)) {
        context.subscriptions.push(
            vscode.languages.registerInlineCompletionItemProvider(
                { pattern: '**' },  // Все файлы
                inlineCompletionProvider
            )
        );
        console.log('✅ Inline completions включены');
    }

    // Регистрируем Code Action Provider (Quick Fix)
    const codeActionProvider = new NeiraCodeActionProvider(client);
    context.subscriptions.push(
        vscode.languages.registerCodeActionsProvider(
            { pattern: '**' },
            codeActionProvider,
            {
                providedCodeActionKinds: NeiraCodeActionProvider.providedCodeActionKinds
            }
        )
    );

    // Регистрируем Code Lens Provider (кнопки над функциями)
    if (config.get<boolean>('enableCodeLens', true)) {
        const codeLensProvider = new NeiraCodeLensProvider();
        context.subscriptions.push(
            vscode.languages.registerCodeLensProvider(
                { pattern: '**' },
                codeLensProvider
            )
        );
    }

    // Регистрируем Indexer Tree View
    context.subscriptions.push(
        vscode.window.registerTreeDataProvider(
            'neira.indexerView',
            indexerProvider
        )
    );

    // Регистрируем Models View
    const modelsProvider = registerModelsView(context, client);

    // Регистрируем Workspace Symbol Provider (Ctrl+T)
    context.subscriptions.push(
        vscode.languages.registerWorkspaceSymbolProvider(
            new NeiraWorkspaceSymbolProvider(client)
        )
    );

    // Регистрируем Hover Provider с контекстом из индекса
    context.subscriptions.push(
        vscode.languages.registerHoverProvider(
            { scheme: 'file', language: 'python' },
            new NeiraHoverWithContext(client, indexerProvider)
        )
    );

    // Регистрируем команды индексатора
    registerIndexerCommands(context, indexerProvider);

    // Регистрируем команды контекст-менеджера
    registerContextCommands(context, contextProvider);
    
    // Активируем статус-бар с токенами
    tokenStatusBar.activate(context);

    // Регистрируем команды
    registerCommands(context, chatViewProvider, statusViewProvider);

    // Регистрируем участника чата (Copilot Chat)
    registerCopilotChatParticipant(context, client);

    // === Команды управления слоями (выполняются через Neira Server) ===
    context.subscriptions.push(
        vscode.commands.registerCommand('neira.listLayers', async () => {
            const resp = await client.listLayers();
            if (!resp.success || !resp.data || !resp.data.models) {
                return vscode.window.showErrorMessage(resp.error || 'Не удалось получить список слоёв');
            }

            const models = Object.keys(resp.data.models || {});
            if (!models.length) {
                return vscode.window.showInformationMessage('Слои не найдены.');
            }

            const pickedModel = await vscode.window.showQuickPick(models, { placeHolder: 'Выберите модель' });
            if (!pickedModel) return;

            const layers = resp.data.models[pickedModel] || [];
            if (!layers.length) {
                return vscode.window.showInformationMessage('У модели нет слоёв.');
            }

            const items: vscode.QuickPickItem[] = layers.map((l: any) => ({
                label: l.id,
                description: `${l.kind} - ${l.description || ''}`
            }));
            const picked = await vscode.window.showQuickPick(items, { placeHolder: 'Слои модели' });
            if (picked) {
                vscode.window.showInformationMessage(`Слой: ${picked.label}`);
            }
        })
    );

    context.subscriptions.push(
        vscode.commands.registerCommand('neira.activateLayer', async () => {
            const resp = await client.listLayers();
            if (!resp.success || !resp.data || !resp.data.models) {
                return vscode.window.showErrorMessage(resp.error || 'Не удалось получить список слоёв');
            }
            const models = Object.keys(resp.data.models || {});
            const model = await vscode.window.showQuickPick(models, { placeHolder: 'Выберите модель' });
            if (!model) return;

            const layers = resp.data.models[model] || [];
            const choices = [{ label: 'Очистить активный слой', id: '' }].concat(layers.map((l: any) => ({ label: l.id, id: l.id })));
            const pick = await vscode.window.showQuickPick(choices.map(c => c.label), { placeHolder: 'Выберите слой для активации' });
            if (pick === undefined) return;
            const chosen = choices.find(c => c.label === pick);
            const id = chosen && chosen.id ? chosen.id : null;
            const res = await client.activateLayer(model, id);
            if (res.success) {
                vscode.window.showInformationMessage('Активный слой обновлён.');
                actionsProvider.refresh();
            } else {
                vscode.window.showErrorMessage(res.error || 'Ошибка при активации слоя');
            }
        })
    );

    context.subscriptions.push(
        vscode.commands.registerCommand('neira.addLayer', async () => {
            const model = await vscode.window.showInputBox({ prompt: 'Имя модели (как в Ollama)' });
            if (!model) return;
            const id = await vscode.window.showInputBox({ prompt: 'ID слоя (например: code-assistant-lora)' });
            if (!id) return;
            const kind = await vscode.window.showInputBox({ prompt: 'Тип слоя', value: 'ollama_adapter' });
            const description = await vscode.window.showInputBox({ prompt: 'Описание (опционально)', value: '' });
            const size = await vscode.window.showInputBox({ prompt: 'Размер в ГБ (опционально)', value: '' });
            const activatePick = await vscode.window.showQuickPick(['Да', 'Нет'], { placeHolder: 'Сделать активным?' });
            const activate = activatePick === 'Да';

            const layer: any = { id, kind: kind || 'ollama_adapter', description: description || '' };
            if (size) layer.size_gb = parseFloat(size);

            const res = await client.addLayer(model, layer, activate, false);
            if (res.success) {
                vscode.window.showInformationMessage('Слой добавлен.');
                actionsProvider.refresh();
            } else {
                vscode.window.showErrorMessage(res.error || 'Ошибка при добавлении слоя');
            }
        })
    );

    context.subscriptions.push(
        vscode.commands.registerCommand('neira.deleteLayer', async () => {
            const resp = await client.listLayers();
            if (!resp.success || !resp.data || !resp.data.models) {
                return vscode.window.showErrorMessage(resp.error || 'Не удалось получить список слоёв');
            }
            const models = Object.keys(resp.data.models || {});
            const model = await vscode.window.showQuickPick(models, { placeHolder: 'Выберите модель' });
            if (!model) return;

            const layers = resp.data.models[model] || [];
            const pick = await vscode.window.showQuickPick(layers.map((l: any) => l.id), { placeHolder: 'Выберите слой для удаления' });
            if (!pick) return;

            const confirm = await vscode.window.showWarningMessage(`Удалить слой ${pick} у модели ${model}?`, { modal: true }, 'Удалить');
            if (confirm !== 'Удалить') return;

            const res = await client.deleteLayer(model, pick);
            if (res.success) {
                vscode.window.showInformationMessage('Слой удалён.');
                actionsProvider.refresh();
            } else {
                vscode.window.showErrorMessage(res.error || 'Ошибка при удалении слоя');
            }
        })
    );

    // Команда: сделать Neira активной моделью/участником для Copilot Chat
    context.subscriptions.push(
        vscode.commands.registerCommand('neira.setAsCopilotModel', async () => {
            // Сохраняем предпочитаемую настройку
            try {
                await vscode.workspace.getConfiguration('neira').update('preferForCopilot', true, vscode.ConfigurationTarget.Global);
            } catch {}

            // Попытка открыть Chat с участником Neira (если API доступен)
            const chatApi = (vscode as any).chat;
            let opened = false;
            try {
                if (chatApi?.openChat) {
                    // API openChat может принимать опции; пытаемся вызвать безопасно
                    await chatApi.openChat?.({ participants: [PARTICIPANT_ID] });
                    opened = true;
                }
            } catch {}

            if (opened) {
                vscode.window.showInformationMessage('Neira открыта в Copilot Chat.');
            } else {
                vscode.window.showInformationMessage('Neira зарегистрирована как участник Copilot Chat. Откройте Chat и выберите Neira в списке участников.');
            }
        })
    );

    // Проверяем статус сервера
    checkServerStatus(statusViewProvider);
    
    // Подписываемся на изменения состояния сервера
    serverManager.onStateChange(async () => {
        await checkServerStatus(statusViewProvider);
        actionsProvider.refresh();
    });

    // Периодическая проверка статуса (каждые 15 сек)
    const statusInterval = global.setInterval(() => {
        checkServerStatus(statusViewProvider);
    }, 15000);

    context.subscriptions.push({
        dispose: () => global.clearInterval(statusInterval)
    });

    console.log('✅ Neira Extension активирован!');
}

// ==================== КОМАНДЫ ИНДЕКСАТОРА ====================

function registerIndexerCommands(
    context: vscode.ExtensionContext,
    indexer: NeiraIndexerProvider
) {
    // Индексировать workspace
    context.subscriptions.push(
        vscode.commands.registerCommand('neira.indexWorkspace', async () => {
            await indexer.indexWorkspace(false);
        })
    );

    // Переиндексировать (принудительно)
    context.subscriptions.push(
        vscode.commands.registerCommand('neira.reindexWorkspace', async () => {
            await indexer.indexWorkspace(true);
        })
    );

    // Поиск символов
    context.subscriptions.push(
        vscode.commands.registerCommand('neira.searchSymbols', async () => {
            await indexer.searchAndShow();
        })
    );

    // Очистить результаты поиска
    context.subscriptions.push(
        vscode.commands.registerCommand('neira.clearSearchResults', () => {
            indexer.clearSearchResults();
        })
    );

    // Получить контекст для текущего файла
    context.subscriptions.push(
        vscode.commands.registerCommand('neira.getContext', async () => {
            const context = await indexer.getContextForActiveFile();
            if (context) {
                // Показать в новом документе
                const doc = await vscode.workspace.openTextDocument({
                    content: context,
                    language: 'markdown'
                });
                await vscode.window.showTextDocument(doc);
            } else {
                vscode.window.showInformationMessage('Контекст не найден');
            }
        })
    );
}

function registerCommands(
    context: vscode.ExtensionContext,
    chatViewProvider: NeiraChatViewProvider,
    statusViewProvider: NeiraStatusViewProvider
) {
    // Открыть чат
    context.subscriptions.push(
        vscode.commands.registerCommand('neira.openChat', () => {
            vscode.commands.executeCommand('neira.chatView.focus');
        })
    );

    // Объяснить код
    context.subscriptions.push(
        vscode.commands.registerCommand('neira.explainCode', async () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor) {
                vscode.window.showWarningMessage('Нет активного редактора');
                return;
            }

            const selection = editor.selection;
            const code = editor.document.getText(selection);

            if (!code) {
                vscode.window.showWarningMessage('Выделите код для объяснения');
                return;
            }

            const language = editor.document.languageId;
            const filename = editor.document.fileName;

            await vscode.window.withProgress({
                location: vscode.ProgressLocation.Notification,
                title: '🧠 Нейра анализирует код...',
                cancellable: false
            }, async () => {
                try {
                    const response = await client.explainCode(code, language, filename);
                    if (response.success && response.data) {
                        chatViewProvider.addMessage('user', `Объясни этот код:\n\`\`\`${language}\n${code}\n\`\`\``);
                        chatViewProvider.addMessage('assistant', response.data.response || '');
                        vscode.commands.executeCommand('neira.chatView.focus');
                    } else {
                        vscode.window.showErrorMessage(
                            `Ошибка: ${response.error || 'Неизвестная ошибка'}`
                        );
                    }
                } catch (error) {
                    vscode.window.showErrorMessage(`Ошибка: ${error}`);
                }
            });
        })
    );

    // Сгенерировать код
    context.subscriptions.push(
        vscode.commands.registerCommand('neira.generateCode', async () => {
            const description = await vscode.window.showInputBox({
                prompt: 'Опишите, какой код нужно сгенерировать',
                placeHolder: 'Например: функция сортировки массива'
            });

            if (!description) {
                return;
            }

            const editor = vscode.window.activeTextEditor;
            const language = editor?.document.languageId || 'python';

            await vscode.window.withProgress({
                location: vscode.ProgressLocation.Notification,
                title: '🧠 Нейра генерирует код...',
                cancellable: false
            }, async () => {
                try {
                    const response = await client.generateCode(description, language);
                    if (response.success && response.data) {
                        chatViewProvider.addMessage('user', `Сгенерируй: ${description}`);
                        chatViewProvider.addMessage('assistant', response.data.response || '');
                        vscode.commands.executeCommand('neira.chatView.focus');
                    } else {
                        vscode.window.showErrorMessage(
                            `Ошибка: ${response.error || 'Неизвестная ошибка'}`
                        );
                    }
                } catch (error) {
                    vscode.window.showErrorMessage(`Ошибка: ${error}`);
                }
            });
        })
    );

    // Спросить о выделенном
    context.subscriptions.push(
        vscode.commands.registerCommand('neira.askAboutSelection', async () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor) {
                return;
            }

            const selection = editor.selection;
            const selectedText = editor.document.getText(selection);

            if (!selectedText) {
                vscode.window.showWarningMessage('Выделите текст или код');
                return;
            }

            const question = await vscode.window.showInputBox({
                prompt: 'Что вы хотите спросить об этом коде?',
                placeHolder: 'Например: что делает эта функция?'
            });

            if (!question) {
                return;
            }

            await vscode.window.withProgress({
                location: vscode.ProgressLocation.Notification,
                title: '🧠 Нейра думает...',
                cancellable: false
            }, async () => {
                try {
                    const response = await client.chat(question, selectedText);
                    if (response.success && response.data) {
                        chatViewProvider.addMessage('user', question);
                        chatViewProvider.addMessage('assistant', response.data.response || '');
                        vscode.commands.executeCommand('neira.chatView.focus');
                    } else {
                        vscode.window.showErrorMessage(
                            `Ошибка: ${response.error || 'Неизвестная ошибка'}`
                        );
                    }
                } catch (error) {
                    vscode.window.showErrorMessage(`Ошибка: ${error}`);
                }
            });
        })
    );

    // Проверить статус
    context.subscriptions.push(
        vscode.commands.registerCommand('neira.checkStatus', async () => {
            await checkServerStatus(statusViewProvider);
            const status = await client.checkHealth();
            if (status.success) {
                vscode.window.showInformationMessage(
                    `🧠 Neira онлайн! Обработано запросов: ${status.data?.requests_processed || 0}`
                );
            } else {
                vscode.window.showWarningMessage(
                    '⚠️ Сервер Нейры недоступен. Запустите: python neira_server.py'
                );
            }
        })
    );

    // Выполнить команду в терминале
    context.subscriptions.push(
        vscode.commands.registerCommand('neira.runInTerminal', async () => {
            const command = await vscode.window.showInputBox({
                prompt: 'Введите команду для выполнения',
                placeHolder: 'Например: pip install requests'
            });

            if (!command) {
                return;
            }

            const terminal = vscode.window.createTerminal('Neira Terminal');
            terminal.sendText(command);
            terminal.show();
        })
    );

    // Выполнить выделенный код в терминале
    context.subscriptions.push(
        vscode.commands.registerCommand('neira.runSelectedInTerminal', async () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor) {
                vscode.window.showWarningMessage('Нет активного редактора');
                return;
            }

            const selection = editor.selection;
            const code = editor.document.getText(selection);

            if (!code) {
                vscode.window.showWarningMessage('Выделите код для выполнения');
                return;
            }

            const terminal = vscode.window.createTerminal('Neira Run');
            terminal.sendText(code);
            terminal.show();
        })
    );

    // Исправить код
    context.subscriptions.push(
        vscode.commands.registerCommand('neira.fixCode', async () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor) {
                vscode.window.showWarningMessage('Нет активного редактора');
                return;
            }

            const selection = editor.selection;
            const code = editor.document.getText(selection);

            if (!code) {
                vscode.window.showWarningMessage('Выделите код для исправления');
                return;
            }

            const language = editor.document.languageId;

            await vscode.window.withProgress({
                location: vscode.ProgressLocation.Notification,
                title: '🔧 Нейра исправляет код...',
                cancellable: false
            }, async () => {
                try {
                    const response = await client.chat(
                        `Найди и исправь ошибки в этом ${language} коде. Верни только исправленный код без объяснений:\n\`\`\`${language}\n${code}\n\`\`\``,
                        code
                    );
                    if (response.success && response.data) {
                        chatViewProvider.addMessage('user', `Исправь код:\n\`\`\`${language}\n${code}\n\`\`\``);
                        chatViewProvider.addMessage('assistant', response.data.response || '');
                        vscode.commands.executeCommand('neira.chatView.focus');
                    } else {
                        vscode.window.showErrorMessage(
                            `Ошибка: ${response.error || 'Неизвестная ошибка'}`
                        );
                    }
                } catch (error) {
                    vscode.window.showErrorMessage(`Ошибка: ${error}`);
                }
            });
        })
    );

    // Улучшить код
    context.subscriptions.push(
        vscode.commands.registerCommand('neira.improveCode', async () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor) {
                vscode.window.showWarningMessage('Нет активного редактора');
                return;
            }

            const selection = editor.selection;
            const code = editor.document.getText(selection);

            if (!code) {
                vscode.window.showWarningMessage('Выделите код для улучшения');
                return;
            }

            const language = editor.document.languageId;

            await vscode.window.withProgress({
                location: vscode.ProgressLocation.Notification,
                title: '🚀 Нейра улучшает код...',
                cancellable: false
            }, async () => {
                try {
                    const response = await client.chat(
                        `Улучши этот ${language} код: добавь типизацию, оптимизируй, улучши читаемость. Верни улучшенный код с краткими комментариями:\n\`\`\`${language}\n${code}\n\`\`\``,
                        code
                    );
                    if (response.success && response.data) {
                        chatViewProvider.addMessage('user', `Улучши код:\n\`\`\`${language}\n${code}\n\`\`\``);
                        chatViewProvider.addMessage('assistant', response.data.response || '');
                        vscode.commands.executeCommand('neira.chatView.focus');
                    } else {
                        vscode.window.showErrorMessage(
                            `Ошибка: ${response.error || 'Неизвестная ошибка'}`
                        );
                    }
                } catch (error) {
                    vscode.window.showErrorMessage(`Ошибка: ${error}`);
                }
            });
        })
    );

    // === НОВЫЕ КОМАНДЫ ===

    // Исправление ошибки (Quick Fix)
    context.subscriptions.push(
        vscode.commands.registerCommand('neira.fixError', async (document: vscode.TextDocument, diagnostic: vscode.Diagnostic) => {
            const range = diagnostic.range;
            const errorLine = document.getText(range);
            const surroundingCode = getSurroundingCode(document, range.start.line, 5);

            await vscode.window.withProgress({
                location: vscode.ProgressLocation.Notification,
                title: '🔧 Нейра исправляет ошибку...',
                cancellable: false
            }, async () => {
                try {
                    const response = await client.fixError(
                        surroundingCode,
                        diagnostic.message,
                        document.languageId
                    );

                    if (response.success && response.data?.fix) {
                        // Показываем исправление в чате
                        chatViewProvider.addMessage('user', `Исправь ошибку: ${diagnostic.message}`);
                        chatViewProvider.addMessage('assistant', response.data.fix);
                        vscode.commands.executeCommand('neira.chatView.focus');
                    } else {
                        vscode.window.showErrorMessage('Не удалось исправить ошибку');
                    }
                } catch (error) {
                    vscode.window.showErrorMessage(`Ошибка: ${error}`);
                }
            });
        })
    );

    // Генерация документации
    context.subscriptions.push(
        vscode.commands.registerCommand('neira.generateDocs', async (document?: vscode.TextDocument, range?: vscode.Range) => {
            const editor = vscode.window.activeTextEditor;
            const doc = document || editor?.document;
            const sel = range || editor?.selection;

            if (!doc || !sel) {
                vscode.window.showWarningMessage('Нет выделенного кода');
                return;
            }

            // Расширяем выделение до всей функции/класса
            const code = getFullFunctionOrClass(doc, sel.start.line);

            await vscode.window.withProgress({
                location: vscode.ProgressLocation.Notification,
                title: '📝 Нейра генерирует документацию...',
                cancellable: false
            }, async () => {
                try {
                    const response = await client.generateDocs(code, doc.languageId);

                    if (response.success && response.data?.docs) {
                        chatViewProvider.addMessage('user', 'Сгенерируй документацию для этого кода');
                        chatViewProvider.addMessage('assistant', response.data.docs);
                        vscode.commands.executeCommand('neira.chatView.focus');
                    } else {
                        vscode.window.showErrorMessage('Не удалось сгенерировать документацию');
                    }
                } catch (error) {
                    vscode.window.showErrorMessage(`Ошибка: ${error}`);
                }
            });
        })
    );

    // Генерация тестов
    context.subscriptions.push(
        vscode.commands.registerCommand('neira.generateTests', async (document?: vscode.TextDocument, range?: vscode.Range) => {
            const editor = vscode.window.activeTextEditor;
            const doc = document || editor?.document;
            const sel = range || editor?.selection;

            if (!doc || !sel) {
                vscode.window.showWarningMessage('Нет выделенного кода');
                return;
            }

            const code = getFullFunctionOrClass(doc, sel.start.line);

            await vscode.window.withProgress({
                location: vscode.ProgressLocation.Notification,
                title: '🧪 Нейра генерирует тесты...',
                cancellable: false
            }, async () => {
                try {
                    const response = await client.generateTests(code, doc.languageId);

                    if (response.success && response.data?.tests) {
                        chatViewProvider.addMessage('user', 'Сгенерируй тесты для этого кода');
                        chatViewProvider.addMessage('assistant', response.data.tests);
                        vscode.commands.executeCommand('neira.chatView.focus');
                    } else {
                        vscode.window.showErrorMessage('Не удалось сгенерировать тесты');
                    }
                } catch (error) {
                    vscode.window.showErrorMessage(`Ошибка: ${error}`);
                }
            });
        })
    );

    // Рефакторинг кода
    context.subscriptions.push(
        vscode.commands.registerCommand('neira.refactorCode', async (document?: vscode.TextDocument, range?: vscode.Range) => {
            const editor = vscode.window.activeTextEditor;
            const doc = document || editor?.document;
            const sel = range || editor?.selection;

            if (!doc || !sel) {
                vscode.window.showWarningMessage('Выделите код для рефакторинга');
                return;
            }

            const code = doc.getText(sel);

            const instruction = await vscode.window.showInputBox({
                prompt: 'Как улучшить код? (оставьте пустым для общего рефакторинга)',
                placeHolder: 'Например: разбить на функции, добавить типы'
            });

            await vscode.window.withProgress({
                location: vscode.ProgressLocation.Notification,
                title: '♻️ Нейра рефакторит код...',
                cancellable: false
            }, async () => {
                try {
                    const response = await client.refactorCode(code, doc.languageId, instruction);

                    if (response.success && response.data?.refactored) {
                        chatViewProvider.addMessage('user', `Рефакторинг: ${instruction || 'общее улучшение'}`);
                        chatViewProvider.addMessage('assistant', response.data.refactored);
                        vscode.commands.executeCommand('neira.chatView.focus');
                    } else {
                        vscode.window.showErrorMessage('Не удалось выполнить рефакторинг');
                    }
                } catch (error) {
                    vscode.window.showErrorMessage(`Ошибка: ${error}`);
                }
            });
        })
    );

    // Генерация commit message
    context.subscriptions.push(
        vscode.commands.registerCommand('neira.generateCommitMessage', async () => {
            await gitProvider.generateAndInsertCommitMessage();
        })
    );

    // Объяснение изменений
    context.subscriptions.push(
        vscode.commands.registerCommand('neira.explainChanges', async () => {
            await gitProvider.explainChanges();
        })
    );

    // Включить/выключить inline completions
    context.subscriptions.push(
        vscode.commands.registerCommand('neira.toggleInlineCompletions', () => {
            const enabled = !inlineCompletionProvider.isEnabled();
            inlineCompletionProvider.setEnabled(enabled);
            vscode.window.showInformationMessage(
                enabled 
                    ? '✅ Автодополнение Нейры включено'
                    : '❌ Автодополнение Нейры выключено'
            );
        })
    );

    // Очистить кэш completions
    context.subscriptions.push(
        vscode.commands.registerCommand('neira.clearCompletionCache', () => {
            inlineCompletionProvider.clearCache();
            vscode.window.showInformationMessage('🗑️ Кэш автодополнения очищен');
        })
    );
}

// === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===

function getSurroundingCode(document: vscode.TextDocument, line: number, contextLines: number): string {
    const startLine = Math.max(0, line - contextLines);
    const endLine = Math.min(document.lineCount - 1, line + contextLines);
    
    const lines: string[] = [];
    for (let i = startLine; i <= endLine; i++) {
        lines.push(document.lineAt(i).text);
    }
    return lines.join('\n');
}

function getFullFunctionOrClass(document: vscode.TextDocument, startLine: number): string {
    const languageId = document.languageId;
    let endLine = startLine;
    let braceCount = 0;
    let foundStart = false;

    // Для Python - ищем по отступам
    if (languageId === 'python') {
        const startIndent = document.lineAt(startLine).firstNonWhitespaceCharacterIndex;
        for (let i = startLine + 1; i < document.lineCount; i++) {
            const line = document.lineAt(i);
            if (line.text.trim() === '') continue;
            if (line.firstNonWhitespaceCharacterIndex <= startIndent) {
                endLine = i - 1;
                break;
            }
            endLine = i;
        }
    } else {
        // Для C-подобных языков - ищем по скобкам
        for (let i = startLine; i < document.lineCount; i++) {
            const lineText = document.lineAt(i).text;
            for (const char of lineText) {
                if (char === '{') {
                    braceCount++;
                    foundStart = true;
                } else if (char === '}') {
                    braceCount--;
                }
            }
            if (foundStart && braceCount === 0) {
                endLine = i;
                break;
            }
            endLine = i;
        }
    }

    const range = new vscode.Range(startLine, 0, endLine, document.lineAt(endLine).text.length);
    return document.getText(range);
}

async function checkServerStatus(statusViewProvider: NeiraStatusViewProvider): Promise<void> {
    try {
        const status = await client.checkHealth();
        if (status.success && status.data) {
            updateStatusBar('online');
            statusViewProvider.updateStatus(true, {
                status: status.data.status || 'online',
                neira_ready: status.data.neira_ready || false,
                uptime_seconds: status.data.uptime_seconds || 0,
                requests_processed: status.data.requests_processed || 0,
                websocket_clients: status.data.websocket_clients || 0,
                version: status.data.version || '1.0.0'
            });
        } else {
            updateStatusBar('offline');
            statusViewProvider.updateStatus(false, null);
        }
    } catch {
        updateStatusBar('offline');
        statusViewProvider.updateStatus(false, null);
    }
}

function updateStatusBar(status: 'online' | 'offline' | 'checking'): void {
    switch (status) {
        case 'online':
            statusBarItem.text = '$(brain) Neira';
            statusBarItem.tooltip = 'Нейра онлайн — нажмите для чата';
            statusBarItem.backgroundColor = undefined;
            break;
        case 'offline':
            statusBarItem.text = '$(brain) Neira ⚠️';
            statusBarItem.tooltip = 'Нейра офлайн — запустите сервер через команду Neira: Запустить сервер';
            statusBarItem.backgroundColor = new vscode.ThemeColor(
                'statusBarItem.warningBackground'
            );
            break;
        case 'checking':
            statusBarItem.text = '$(sync~spin) Neira';
            statusBarItem.tooltip = 'Проверка соединения...';
            break;
    }
}

export function deactivate() {
    console.log('🧠 Neira Extension деактивирован');
}

