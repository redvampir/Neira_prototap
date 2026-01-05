/**
 * Neira Copilot Chat Participant
 * Интеграция Нейры в чат VS Code (Copilot Chat)
 */

import * as vscode from 'vscode';
import { NeiraClient } from './neiraClient';

export const PARTICIPANT_ID = 'neira.neira';
const MAX_PROMPT_CHARS = 12000;
const MAX_REFERENCE_CHARS = 2000;

export function registerCopilotChatParticipant(
    context: vscode.ExtensionContext,
    client: NeiraClient
): void {
    const chatApi = (vscode as { chat?: typeof vscode.chat }).chat;
    if (!chatApi?.createChatParticipant) {
        return;
    }

    const participant = chatApi.createChatParticipant(
        PARTICIPANT_ID,
        async (request, _chatContext, response, token) => {
            const prompt = request.prompt.trim();
            if (!prompt) {
                response.markdown('Сообщение пустое.');
                return { errorDetails: { message: 'Пустой запрос' } };
            }

            const fullPrompt = buildPrompt(request);
            response.progress('Нейра обрабатывает запрос...');

            if (token.isCancellationRequested) {
                return;
            }

            const result = await client.chat(fullPrompt);
            if (token.isCancellationRequested) {
                return;
            }

            if (!result.success || !result.data?.response) {
                const message = result.error || 'Нет ответа от сервера';
                response.markdown(`**Ошибка:** ${message}`);
                return { errorDetails: { message } };
            }

            response.markdown(result.data.response);
            return {
                metadata: {
                    model: result.data.model,
                    model_source: result.data.model_source,
                    request_id: result.request_id
                }
            };
        }
    );

    const iconPath = vscode.Uri.joinPath(context.extensionUri, 'media', 'neira-icon.png');
    participant.iconPath = { light: iconPath, dark: iconPath };

    context.subscriptions.push(participant);
}

function buildPrompt(request: vscode.ChatRequest): string {
    const parts: string[] = [];

    if (request.command) {
        parts.push(`Команда: /${request.command}`);
    }

    parts.push(truncate(request.prompt.trim(), MAX_PROMPT_CHARS));

    const references = formatReferences(request.references);
    if (references) {
        parts.push(`Контекст из ссылок:\n${references}`);
    }

    return parts.join('\n\n');
}

function formatReferences(references: readonly vscode.ChatPromptReference[]): string {
    if (!references.length) {
        return '';
    }

    return references
        .map((ref) => {
            const label = ref.modelDescription || ref.id;
            const value = describeReferenceValue(ref.value);
            return `- ${label}: ${value}`;
        })
        .join('\n');
}

function describeReferenceValue(value: unknown): string {
    if (typeof value === 'string') {
        return truncate(value, MAX_REFERENCE_CHARS);
    }

    if (value instanceof vscode.Uri) {
        return value.fsPath;
    }

    if (value && typeof value === 'object' && 'uri' in value) {
        const location = value as vscode.Location;
        const uri = location.uri;
        if (uri) {
            const line = location.range.start.line + 1;
            const column = location.range.start.character + 1;
            return `${uri.fsPath}:${line}:${column}`;
        }
    }

    try {
        return truncate(JSON.stringify(value), MAX_REFERENCE_CHARS);
    } catch {
        return String(value);
    }
}

function truncate(value: string, maxLength: number): string {
    if (value.length <= maxLength) {
        return value;
    }
    return `${value.slice(0, maxLength)}...`;
}
