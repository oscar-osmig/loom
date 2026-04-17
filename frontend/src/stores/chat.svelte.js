/**
 * Chat store — reactive message list with sessionStorage persistence (Svelte 5 runes).
 */

const STORAGE_KEY = 'loom_chat_history';
const CONV_ID_KEY = 'loom_conversation_id';

function generateUUID() {
    // Browser-native UUID when available, fallback otherwise
    if (typeof crypto !== 'undefined' && crypto.randomUUID) {
        return crypto.randomUUID();
    }
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
        const r = Math.random() * 16 | 0;
        const v = c === 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });
}

function loadConversationId() {
    try {
        let id = sessionStorage.getItem(CONV_ID_KEY);
        if (!id) {
            id = generateUUID();
            sessionStorage.setItem(CONV_ID_KEY, id);
        }
        return id;
    } catch {
        return generateUUID();
    }
}

export const conversationId = loadConversationId();

export function resetConversation() {
    const newId = generateUUID();
    try { sessionStorage.setItem(CONV_ID_KEY, newId); } catch {}
    return newId;
}

function loadMessages() {
    try {
        const raw = sessionStorage.getItem(STORAGE_KEY);
        if (raw) {
            const msgs = JSON.parse(raw);
            if (Array.isArray(msgs)) return msgs;
        }
    } catch {}
    return [];
}

function persistMessages() {
    try {
        sessionStorage.setItem(STORAGE_KEY, JSON.stringify(chat.messages));
    } catch {}
}

const loaded = loadMessages();
let nextId = loaded.length > 0 ? Math.max(...loaded.map(m => m.id || 0)) + 1 : 1;

export const chat = $state({
    messages: loaded,
    isTyping: false,
});

export function addMessage(content, type, meta) {
    chat.messages.push({
        id: nextId++,
        content,
        type,
        meta: meta || undefined
    });
    persistMessages();
}

export function setTyping(value) {
    chat.isTyping = value;
}

export function clearMessages() {
    chat.messages.length = 0;
    nextId = 1;
    try { sessionStorage.removeItem(STORAGE_KEY); } catch {}
}

/**
 * Format the conversation as clean text for clipboard.
 */
export function formatConversation() {
    if (chat.messages.length === 0) return '';

    const lines = [];
    for (const msg of chat.messages) {
        const prefix = msg.type === 'user' ? 'You' : 'Loom';
        // Strip HTML tags for clean text
        const text = (msg.content || '')
            .replace(/<br\s*\/?>/gi, '\n')
            .replace(/<[^>]+>/g, '')
            .replace(/&amp;/g, '&')
            .replace(/&lt;/g, '<')
            .replace(/&gt;/g, '>')
            .replace(/&quot;/g, '"')
            .replace(/&#x27;/g, "'")
            .trim();
        if (text) {
            lines.push(`${prefix}: ${text}`);
        }
    }
    return lines.join('\n\n');
}
