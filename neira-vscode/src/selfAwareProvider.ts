/**
 * Neira Self-Aware Provider
 * 
 * Интеграция уникальных возможностей Нейры:
 * - Introspection (самосознание)
 * - Experience (накопленный опыт)
 * - Curiosity (любопытство и проактивность)
 * - Memory (долгосрочная память)
 */

import * as vscode from 'vscode';
import { NeiraClient } from './neiraClient';

// ==================== ИНТЕРФЕЙСЫ ====================

interface OrganInfo {
    name: string;
    file: string;
    description: string;
    capabilities: string[];
    status: 'active' | 'dormant' | 'growing';
}

interface ExperienceEntry {
    timestamp: string;
    task_type: string;
    verdict: string;
    score: number;
    lesson: string;
}

interface PersonalityTraits {
    curiosity: number;
    helpfulness: number;
    self_awareness: number;
    creativity: number;
}

interface NeiraState {
    organs: OrganInfo[];
    experience: ExperienceEntry[];
    personality: PersonalityTraits;
    memory_stats: {
        short_term: number;
        long_term: number;
    };
}

// ==================== SELF-AWARE PROVIDER ====================

export class NeiraSelfAwareProvider {
    private state: NeiraState | null = null;
    private curiosityEnabled = true;
    private lastCuriosityQuestion: string | null = null;

    constructor(private client: NeiraClient) {}

    // ==================== INTROSPECTION ====================

    /**
     * Получить информацию о состоянии Нейры
     */
    async getNeiraState(): Promise<NeiraState | null> {
        try {
            const response = await this.client.request('/introspection', {});
            
            if (response.success && response.data) {
                this.state = response.data;
                return this.state;
            }
        } catch {
            // Fallback - минимальное состояние
        }
        return null;
    }

    /**
     * Показать самосознание Нейры
     */
    async showIntrospection(): Promise<void> {
        const state = await this.getNeiraState();
        
        if (!state) {
            vscode.window.showErrorMessage('Не удалось получить состояние Нейры');
            return;
        }

        const md = this.formatStateAsMarkdown(state);
        
        const doc = await vscode.workspace.openTextDocument({
            content: md,
            language: 'markdown'
        });
        await vscode.window.showTextDocument(doc);
    }

    private formatStateAsMarkdown(state: NeiraState): string {
        let md = '# 🧬 Состояние Нейры\n\n';

        // Личность
        md += '## Личность\n\n';
        md += `- 🔍 Любопытство: ${this.bar(state.personality.curiosity)}\n`;
        md += `- 💡 Самосознание: ${this.bar(state.personality.self_awareness)}\n`;
        md += `- 🎨 Креативность: ${this.bar(state.personality.creativity)}\n`;
        md += `- 🤝 Отзывчивость: ${this.bar(state.personality.helpfulness)}\n\n`;

        // Память
        md += '## Память\n\n';
        md += `- Краткосрочная: ${state.memory_stats.short_term} записей\n`;
        md += `- Долгосрочная: ${state.memory_stats.long_term} записей\n\n`;

        // Органы
        md += '## Активные органы\n\n';
        for (const organ of state.organs) {
            const status = organ.status === 'active' ? '🟢' : organ.status === 'growing' ? '🟡' : '⚪';
            md += `### ${status} ${organ.name}\n`;
            md += `*${organ.description}*\n\n`;
            md += `Возможности: ${organ.capabilities.join(', ')}\n\n`;
        }

        // Последний опыт
        if (state.experience.length > 0) {
            md += '## Последний опыт\n\n';
            for (const exp of state.experience.slice(-5)) {
                const emoji = exp.score >= 8 ? '✅' : exp.score >= 5 ? '⚠️' : '❌';
                md += `- ${emoji} **${exp.task_type}** (${exp.score}/10): ${exp.lesson}\n`;
            }
        }

        return md;
    }

    private bar(value: number): string {
        const filled = Math.round(value * 10);
        return '█'.repeat(filled) + '░'.repeat(10 - filled) + ` ${Math.round(value * 100)}%`;
    }

    // ==================== EXPERIENCE ====================

    /**
     * Получить релевантный опыт для задачи
     */
    async getRelevantExperience(taskType: string): Promise<string[]> {
        try {
            const response = await this.client.request('/experience/relevant', {
                task_type: taskType,
                limit: 5
            });

            if (response.success && response.data) {
                return response.data.lessons || [];
            }
        } catch {
            // Ignore
        }
        return [];
    }

    /**
     * Записать опыт после выполнения задачи
     */
    async recordExperience(
        taskType: string,
        userInput: string,
        verdict: 'ПРИНЯТ' | 'ДОРАБОТАТЬ' | 'ОТКЛОНЁН',
        score: number,
        problems: string
    ): Promise<void> {
        try {
            await this.client.request('/experience/record', {
                task_type: taskType,
                user_input: userInput,
                verdict,
                score,
                problems
            });
        } catch {
            // Ignore
        }
    }

    /**
     * Добавить контекст опыта к запросу
     */
    async enrichWithExperience(query: string, taskType: string): Promise<string> {
        const lessons = await this.getRelevantExperience(taskType);
        
        if (lessons.length === 0) {
            return query;
        }

        const experienceContext = lessons.map(l => `- ${l}`).join('\n');
        
        return `${query}\n\n[Из моего опыта]\n${experienceContext}`;
    }

    // ==================== CURIOSITY ====================

    /**
     * Получить вопрос от любопытной Нейры
     */
    async getCuriosityQuestion(userMessage: string, neiraResponse: string): Promise<string | null> {
        if (!this.curiosityEnabled) {
            return null;
        }

        try {
            const response = await this.client.request('/curiosity/question', {
                user_message: userMessage,
                neira_response: neiraResponse
            });

            if (response.success && response.data?.question) {
                this.lastCuriosityQuestion = response.data.question;
                return response.data.question;
            }
        } catch {
            // Ignore
        }
        return null;
    }

    /**
     * Показать рефлексию Нейры
     */
    async showReflection(): Promise<void> {
        try {
            const response = await this.client.request('/curiosity/reflect', {});

            if (response.success && response.data?.reflection) {
                vscode.window.showInformationMessage(
                    `💭 ${response.data.reflection}`,
                    'Интересно!'
                );
            }
        } catch {
            vscode.window.showWarningMessage('Нейра сейчас не в настроении для рефлексии');
        }
    }

    /**
     * Искра любопытства - Нейра спрашивает о теме
     */
    async sparkCuriosity(topic: string): Promise<string | null> {
        try {
            const response = await this.client.request('/curiosity/spark', {
                topic
            });

            if (response.success && response.data?.question) {
                return response.data.question;
            }
        } catch {
            // Ignore
        }
        return null;
    }

    toggleCuriosity(): boolean {
        this.curiosityEnabled = !this.curiosityEnabled;
        return this.curiosityEnabled;
    }

    // ==================== MEMORY INTEGRATION ====================

    /**
     * Поиск в памяти Нейры
     */
    async searchMemory(query: string): Promise<string[]> {
        try {
            const response = await this.client.request('/memory/search', {
                query,
                limit: 10
            });

            if (response.success && response.data?.memories) {
                return response.data.memories;
            }
        } catch {
            // Ignore
        }
        return [];
    }

    /**
     * Запомнить важное
     */
    async remember(content: string, category: string = 'code'): Promise<boolean> {
        try {
            const response = await this.client.request('/memory/remember', {
                content,
                category
            });

            return response.success;
        } catch {
            return false;
        }
    }

    /**
     * Добавить контекст из памяти к запросу
     */
    async enrichWithMemory(query: string): Promise<string> {
        const memories = await this.searchMemory(query);
        
        if (memories.length === 0) {
            return query;
        }

        const memoryContext = memories.slice(0, 3).map(m => `- ${m}`).join('\n');
        
        return `${query}\n\n[Из моей памяти]\n${memoryContext}`;
    }

    // ==================== SMART CONTEXT ====================

    /**
     * Собрать умный контекст с учётом всех систем Нейры
     */
    async buildSmartContext(
        query: string,
        currentCode: string | null,
        taskType: string
    ): Promise<{
        enrichedQuery: string;
        context: string[];
    }> {
        const context: string[] = [];
        let enrichedQuery = query;

        // 1. Добавляем релевантный опыт
        const lessons = await this.getRelevantExperience(taskType);
        if (lessons.length > 0) {
            context.push(`📚 Опыт: ${lessons.join('; ')}`);
        }

        // 2. Ищем в памяти
        const memories = await this.searchMemory(query);
        if (memories.length > 0) {
            context.push(`🧠 Память: ${memories.slice(0, 2).join('; ')}`);
        }

        // 3. Добавляем состояние личности
        if (this.state) {
            const traits = this.state.personality;
            if (traits.creativity > 0.7) {
                context.push('🎨 Сейчас в креативном настроении');
            }
            if (traits.curiosity > 0.8) {
                context.push('🔍 Высокий уровень любопытства');
            }
        }

        return {
            enrichedQuery,
            context
        };
    }
}

// ==================== FEEDBACK SYSTEM ====================

export class NeiraFeedbackProvider {
    constructor(
        private client: NeiraClient,
        private selfAware: NeiraSelfAwareProvider
    ) {}

    /**
     * Показать UI для оценки ответа Нейры
     */
    async showFeedbackUI(taskType: string, userInput: string): Promise<void> {
        const rating = await vscode.window.showQuickPick(
            [
                { label: '$(star-full) Отлично', value: 10 },
                { label: '$(star-half) Хорошо', value: 7 },
                { label: '$(star-empty) Нормально', value: 5 },
                { label: '$(thumbsdown) Плохо', value: 3 },
                { label: '$(x) Совсем не то', value: 1 }
            ],
            { placeHolder: 'Как Нейра справилась?' }
        );

        if (!rating) {
            return;
        }

        let problems = '';
        if (rating.value < 7) {
            problems = await vscode.window.showInputBox({
                prompt: 'Что было не так?',
                placeHolder: 'Опишите проблему'
            }) || '';
        }

        const verdict = rating.value >= 8 ? 'ПРИНЯТ' : rating.value >= 5 ? 'ДОРАБОТАТЬ' : 'ОТКЛОНЁН';

        await this.selfAware.recordExperience(
            taskType,
            userInput,
            verdict as any,
            rating.value,
            problems
        );

        vscode.window.showInformationMessage(
            `Спасибо за обратную связь! ${rating.value >= 7 ? '😊' : '📝 Учту на будущее'}`
        );
    }

    /**
     * Quick feedback через emoji
     */
    async quickFeedback(positive: boolean): Promise<void> {
        // Отправляем на сервер
        try {
            await this.client.request('/feedback/quick', {
                positive
            });
        } catch {
            // Ignore
        }
    }
}

// ==================== КОМАНДЫ ====================

export function registerSelfAwareCommands(
    context: vscode.ExtensionContext,
    provider: NeiraSelfAwareProvider,
    feedbackProvider?: NeiraFeedbackProvider
): void {
    // Показать состояние Нейры
    context.subscriptions.push(
        vscode.commands.registerCommand('neira.showIntrospection', () => {
            provider.showIntrospection();
        })
    );

    // Рефлексия
    context.subscriptions.push(
        vscode.commands.registerCommand('neira.reflect', () => {
            provider.showReflection();
        })
    );

    // Переключить любопытство
    context.subscriptions.push(
        vscode.commands.registerCommand('neira.toggleCuriosity', () => {
            const enabled = provider.toggleCuriosity();
            vscode.window.showInformationMessage(
                enabled ? '🔍 Любопытство включено' : '😶 Любопытство выключено'
            );
        })
    );

    // Запомнить выделенное
    context.subscriptions.push(
        vscode.commands.registerCommand('neira.rememberSelection', async () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor || editor.selection.isEmpty) {
                vscode.window.showWarningMessage('Выделите код для запоминания');
                return;
            }

            const selection = editor.document.getText(editor.selection);
            const category = await vscode.window.showQuickPick(
                ['code', 'pattern', 'bug_fix', 'solution', 'note'],
                { placeHolder: 'Категория' }
            );

            if (category) {
                const success = await provider.remember(selection, category);
                if (success) {
                    vscode.window.showInformationMessage('🧠 Запомнила!');
                }
            }
        })
    );

    // Поиск в памяти
    context.subscriptions.push(
        vscode.commands.registerCommand('neira.searchMemory', async () => {
            const query = await vscode.window.showInputBox({
                prompt: 'Что искать в памяти Нейры?',
                placeHolder: 'Например: как исправить ошибку с async'
            });

            if (!query) {
                return;
            }

            const memories = await provider.searchMemory(query);
            
            if (memories.length === 0) {
                vscode.window.showInformationMessage('Ничего не нашла 🤔');
                return;
            }

            const selected = await vscode.window.showQuickPick(
                memories.map((m, i) => ({
                    label: `${i + 1}. ${m.substring(0, 100)}...`,
                    detail: m,
                    memory: m
                })),
                { placeHolder: 'Результаты поиска' }
            );

            if (selected) {
                // Вставить в редактор как комментарий
                const editor = vscode.window.activeTextEditor;
                if (editor) {
                    editor.edit(edit => {
                        edit.insert(editor.selection.active, `# Из памяти Нейры:\n# ${selected.memory}\n`);
                    });
                }
            }
        })
    );

    // Быстрая обратная связь
    if (feedbackProvider) {
        context.subscriptions.push(
            vscode.commands.registerCommand('neira.quickFeedback', async () => {
                const rating = await vscode.window.showQuickPick(
                    [
                        { label: '👍 Отлично', value: true },
                        { label: '👎 Плохо', value: false }
                    ],
                    { placeHolder: 'Как тебе последний ответ Нейры?' }
                );

                if (rating !== undefined) {
                    await feedbackProvider.quickFeedback(rating.value);
                    vscode.window.showInformationMessage('Спасибо за обратную связь! 💝');
                }
            })
        );
    }
}
