/**
 * Learning Provider — Обучение Нейры из источников
 * 
 * Поддерживает:
 * - Текстовые файлы
 * - Веб-страницы (статьи, документация)
 * - YouTube видео (транскрипты)
 * - PDF документы
 */

import * as vscode from 'vscode';
import { NeiraClient } from './neiraClient';

interface LearnResult {
    success: boolean;
    title?: string;
    source_type?: string;
    word_count?: number;
    chunks?: number;
    summary?: string;
    message?: string;
    error?: string;
}

interface LearningStats {
    success: boolean;
    total_sources: number;
    total_words: number;
    by_type: Record<string, number>;
    by_category: Record<string, number>;
    recent: Array<{
        title: string;
        source_type: string;
        word_count: number;
        learned_at: string;
    }>;
}

interface ExtractResult {
    success: boolean;
    title?: string;
    source_type?: string;
    word_count?: number;
    preview?: string;
    error?: string;
}

export class NeiraLearningProvider {
    private client: NeiraClient;
    private outputChannel: vscode.OutputChannel;

    constructor(client: NeiraClient) {
        this.client = client;
        this.outputChannel = vscode.window.createOutputChannel('Neira Learning');
    }

    /**
     * Обучение из одного источника
     */
    async learnFromSource(source: string, category: string = 'knowledge'): Promise<LearnResult> {
        try {
            const result = await this.client.request('/learn', {
                source,
                category,
                summarize: true
            });
            
            if (result.success) {
                this.outputChannel.appendLine(`✓ Изучено: ${result.title} (${result.word_count} слов)`);
                if (result.summary) {
                    this.outputChannel.appendLine(`  Summary: ${result.summary.substring(0, 200)}...`);
                }
            }
            
            return result;
        } catch (error) {
            return {
                success: false,
                error: String(error)
            };
        }
    }

    /**
     * Пакетное обучение
     */
    async learnBatch(sources: string[], category: string = 'knowledge'): Promise<any> {
        try {
            return await this.client.request('/learn/batch', {
                sources,
                category
            });
        } catch (error) {
            return {
                success: false,
                error: String(error)
            };
        }
    }

    /**
     * Получение статистики обучения
     */
    async getStats(): Promise<LearningStats> {
        try {
            return await this.client.request('/learn/stats', {});
        } catch (error) {
            return {
                success: false,
                total_sources: 0,
                total_words: 0,
                by_type: {},
                by_category: {},
                recent: []
            };
        }
    }

    /**
     * Превью контента без сохранения
     */
    async extractPreview(source: string): Promise<ExtractResult> {
        try {
            return await this.client.request('/learn/extract', { source });
        } catch (error) {
            return {
                success: false,
                error: String(error)
            };
        }
    }

    /**
     * Показать диалог обучения
     */
    async showLearnDialog(): Promise<void> {
        const sourceType = await vscode.window.showQuickPick(
            [
                { label: '📁 Файл', description: 'Выбрать файл из workspace', value: 'file' },
                { label: '🌐 URL', description: 'Веб-страница или статья', value: 'url' },
                { label: '▶️ YouTube', description: 'Видео (извлечёт транскрипт)', value: 'youtube' },
                { label: '📚 Несколько источников', description: 'Ввести список', value: 'batch' }
            ],
            { placeHolder: 'Выберите тип источника для обучения' }
        );

        if (!sourceType) {
            return;
        }

        switch (sourceType.value) {
            case 'file':
                await this.learnFromFile();
                break;
            case 'url':
                await this.learnFromUrl();
                break;
            case 'youtube':
                await this.learnFromYoutube();
                break;
            case 'batch':
                await this.learnFromBatch();
                break;
        }
    }

    /**
     * Обучение из файла
     */
    private async learnFromFile(): Promise<void> {
        const files = await vscode.window.showOpenDialog({
            canSelectMany: true,
            filters: {
                'Все файлы': ['*'],
                'Текстовые': ['txt', 'md', 'rst'],
                'Код': ['py', 'js', 'ts', 'java', 'cpp'],
                'Документы': ['pdf']
            },
            title: 'Выберите файлы для обучения'
        });

        if (!files || files.length === 0) {
            return;
        }

        const category = await this.selectCategory();
        
        await vscode.window.withProgress({
            location: vscode.ProgressLocation.Notification,
            title: 'Нейра изучает файлы...',
            cancellable: false
        }, async (progress) => {
            const sources = files.map(f => f.fsPath);
            
            if (sources.length === 1) {
                const result = await this.learnFromSource(sources[0], category);
                this.showResult(result);
            } else {
                const result = await this.learnBatch(sources, category);
                this.showBatchResult(result);
            }
        });
    }

    /**
     * Обучение из URL
     */
    private async learnFromUrl(): Promise<void> {
        const url = await vscode.window.showInputBox({
            prompt: 'Введите URL статьи или документации',
            placeHolder: 'https://docs.python.org/3/...',
            validateInput: (value) => {
                if (!value.startsWith('http://') && !value.startsWith('https://')) {
                    return 'URL должен начинаться с http:// или https://';
                }
                return null;
            }
        });

        if (!url) {
            return;
        }

        // Сначала показываем превью
        const preview = await this.extractPreview(url);
        
        if (!preview.success) {
            vscode.window.showErrorMessage(`Ошибка извлечения: ${preview.error}`);
            return;
        }

        const confirm = await vscode.window.showQuickPick(
            [
                { label: '✅ Изучить', description: `${preview.word_count} слов`, value: true },
                { label: '❌ Отмена', value: false }
            ],
            { 
                placeHolder: `${preview.title} — ${preview.word_count} слов. Изучить?` 
            }
        );

        if (!confirm?.value) {
            return;
        }

        const category = await this.selectCategory();
        
        await vscode.window.withProgress({
            location: vscode.ProgressLocation.Notification,
            title: `Нейра изучает: ${preview.title}`,
            cancellable: false
        }, async () => {
            const result = await this.learnFromSource(url, category);
            this.showResult(result);
        });
    }

    /**
     * Обучение из YouTube
     */
    private async learnFromYoutube(): Promise<void> {
        const url = await vscode.window.showInputBox({
            prompt: 'Введите ссылку на YouTube видео',
            placeHolder: 'https://www.youtube.com/watch?v=...',
            validateInput: (value) => {
                if (!value.includes('youtube.com') && !value.includes('youtu.be')) {
                    return 'Это не ссылка на YouTube';
                }
                return null;
            }
        });

        if (!url) {
            return;
        }

        const category = await this.selectCategory();

        await vscode.window.withProgress({
            location: vscode.ProgressLocation.Notification,
            title: 'Нейра извлекает транскрипт видео...',
            cancellable: false
        }, async () => {
            const result = await this.learnFromSource(url, category);
            this.showResult(result);
        });
    }

    /**
     * Пакетное обучение
     */
    private async learnFromBatch(): Promise<void> {
        const input = await vscode.window.showInputBox({
            prompt: 'Введите источники (по одному на строку)',
            placeHolder: 'URL или пути к файлам, разделённые переносом строки'
        });

        if (!input) {
            return;
        }

        // Парсим источники
        const sources = input
            .split(/[\n,;]/)
            .map(s => s.trim())
            .filter(s => s.length > 0);

        if (sources.length === 0) {
            vscode.window.showWarningMessage('Не найдено источников');
            return;
        }

        const category = await this.selectCategory();

        await vscode.window.withProgress({
            location: vscode.ProgressLocation.Notification,
            title: `Нейра изучает ${sources.length} источников...`,
            cancellable: false
        }, async (progress) => {
            const result = await this.learnBatch(sources, category);
            this.showBatchResult(result);
        });
    }

    /**
     * Выбор категории
     */
    private async selectCategory(): Promise<string> {
        const category = await vscode.window.showQuickPick(
            [
                { label: '📚 Знания', value: 'knowledge' },
                { label: '💻 Код/Паттерны', value: 'code' },
                { label: '📖 Документация', value: 'documentation' },
                { label: '🎓 Туториал', value: 'tutorial' },
                { label: '🔧 Решения проблем', value: 'solutions' },
                { label: '📝 Заметки', value: 'notes' }
            ],
            { placeHolder: 'Категория знаний' }
        );

        return category?.value || 'knowledge';
    }

    /**
     * Показать результат обучения
     */
    private showResult(result: LearnResult): void {
        if (result.success) {
            vscode.window.showInformationMessage(
                `🎓 ${result.message || 'Изучено успешно!'}\n${result.word_count} слов, ${result.chunks} чанков`
            );
        } else {
            vscode.window.showErrorMessage(`Ошибка обучения: ${result.error}`);
        }
    }

    /**
     * Показать результат пакетного обучения
     */
    private showBatchResult(result: any): void {
        if (result.success > 0) {
            vscode.window.showInformationMessage(
                `🎓 Изучено: ${result.success}/${result.total} источников (${result.total_words} слов)`
            );
        } else {
            vscode.window.showErrorMessage(`Все источники не удалось обработать`);
        }
    }

    /**
     * Показать статистику обучения
     */
    async showStats(): Promise<void> {
        const stats = await this.getStats();

        if (!stats.success) {
            vscode.window.showErrorMessage('Не удалось получить статистику');
            return;
        }

        // Формируем отчёт
        const lines = [
            '# 📊 Статистика обучения Нейры\n',
            `**Всего источников:** ${stats.total_sources}`,
            `**Всего слов:** ${stats.total_words.toLocaleString()}\n`,
            '## По типам:',
            ...Object.entries(stats.by_type).map(([k, v]) => `- ${k}: ${v}`),
            '\n## По категориям:',
            ...Object.entries(stats.by_category).map(([k, v]) => `- ${k}: ${v}`),
        ];

        if (stats.recent.length > 0) {
            lines.push('\n## Последние изученные:');
            stats.recent.forEach(item => {
                lines.push(`- **${item.title}** (${item.source_type}, ${item.word_count} слов)`);
            });
        }

        // Показываем в новом документе
        const doc = await vscode.workspace.openTextDocument({
            content: lines.join('\n'),
            language: 'markdown'
        });
        await vscode.window.showTextDocument(doc, { preview: true });
    }

    /**
     * Обучение из выделенного текста
     */
    async learnFromSelection(): Promise<void> {
        const editor = vscode.window.activeTextEditor;
        if (!editor || editor.selection.isEmpty) {
            vscode.window.showWarningMessage('Выделите текст для обучения');
            return;
        }

        const text = editor.document.getText(editor.selection);
        
        if (text.length < 50) {
            vscode.window.showWarningMessage('Выделите больше текста (минимум 50 символов)');
            return;
        }

        // Создаём временный файл
        const tempPath = `${vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '.'}/temp_learn_${Date.now()}.txt`;
        
        try {
            const fs = require('fs');
            fs.writeFileSync(tempPath, text, 'utf-8');
            
            const category = await this.selectCategory();
            const result = await this.learnFromSource(tempPath, category);
            
            // Удаляем временный файл
            fs.unlinkSync(tempPath);
            
            this.showResult(result);
        } catch (error) {
            vscode.window.showErrorMessage(`Ошибка: ${error}`);
        }
    }
}

/**
 * Регистрация команд обучения
 */
export function registerLearningCommands(
    context: vscode.ExtensionContext,
    provider: NeiraLearningProvider
): void {
    // Главная команда обучения
    context.subscriptions.push(
        vscode.commands.registerCommand('neira.learn', () => {
            provider.showLearnDialog();
        })
    );

    // Обучение из URL
    context.subscriptions.push(
        vscode.commands.registerCommand('neira.learnFromUrl', async () => {
            const url = await vscode.window.showInputBox({
                prompt: 'URL для обучения',
                placeHolder: 'https://...'
            });
            if (url) {
                await vscode.window.withProgress({
                    location: vscode.ProgressLocation.Notification,
                    title: 'Нейра изучает...'
                }, async () => {
                    const result = await provider.learnFromSource(url);
                    if (result.success) {
                        vscode.window.showInformationMessage(`🎓 Изучено: ${result.title}`);
                    } else {
                        vscode.window.showErrorMessage(`Ошибка: ${result.error}`);
                    }
                });
            }
        })
    );

    // Обучение из файла
    context.subscriptions.push(
        vscode.commands.registerCommand('neira.learnFromFile', async () => {
            const files = await vscode.window.showOpenDialog({
                canSelectMany: false,
                title: 'Выберите файл для обучения'
            });
            if (files && files.length > 0) {
                await vscode.window.withProgress({
                    location: vscode.ProgressLocation.Notification,
                    title: 'Нейра изучает файл...'
                }, async () => {
                    const result = await provider.learnFromSource(files[0].fsPath);
                    if (result.success) {
                        vscode.window.showInformationMessage(`🎓 Изучено: ${result.title}`);
                    } else {
                        vscode.window.showErrorMessage(`Ошибка: ${result.error}`);
                    }
                });
            }
        })
    );

    // Статистика обучения
    context.subscriptions.push(
        vscode.commands.registerCommand('neira.learningStats', () => {
            provider.showStats();
        })
    );

    // Обучение из выделения
    context.subscriptions.push(
        vscode.commands.registerCommand('neira.learnFromSelection', () => {
            provider.learnFromSelection();
        })
    );
}
