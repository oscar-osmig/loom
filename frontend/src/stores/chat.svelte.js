/**
 * Chat store — reactive message list with per-instance sessionStorage persistence (Svelte 5 runes).
 */

import { instance } from './instance.svelte.js';

const STORAGE_PREFIX = 'loom_chat_';
const CONV_PREFIX = 'loom_conv_';

function generateUUID() {
    if (typeof crypto !== 'undefined' && crypto.randomUUID) {
        return crypto.randomUUID();
    }
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
        const r = Math.random() * 16 | 0;
        const v = c === 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });
}

function storageKey(inst) {
    return STORAGE_PREFIX + (inst || 'loom');
}

function convKey(inst) {
    return CONV_PREFIX + (inst || 'loom');
}

function loadConversationId(inst) {
    try {
        const key = convKey(inst);
        let id = sessionStorage.getItem(key);
        if (!id) {
            id = generateUUID();
            sessionStorage.setItem(key, id);
        }
        return id;
    } catch {
        return generateUUID();
    }
}

function loadMessages(inst) {
    try {
        const raw = sessionStorage.getItem(storageKey(inst));
        if (raw) {
            const msgs = JSON.parse(raw);
            if (Array.isArray(msgs)) return msgs;
        }
    } catch {}
    return [];
}

function persistMessages() {
    try {
        sessionStorage.setItem(storageKey(instance.current), JSON.stringify(chat.messages));
    } catch {}
}

const initialInstance = instance.current;
const loaded = loadMessages(initialInstance);
let nextId = loaded.length > 0 ? Math.max(...loaded.map(m => m.id || 0)) + 1 : 1;

export let conversationId = loadConversationId(initialInstance);

export function resetConversation() {
    const newId = generateUUID();
    try { sessionStorage.setItem(convKey(instance.current), newId); } catch {}
    conversationId = newId;
    return newId;
}

export const chat = $state({
    messages: loaded,
    isTyping: false,
});

// Watch for instance changes and swap chat history
let prevInstance = initialInstance;

export function syncInstance() {
    const cur = instance.current;
    if (cur === prevInstance) return;
    // Save current messages for the old instance
    try {
        sessionStorage.setItem(storageKey(prevInstance), JSON.stringify(chat.messages));
    } catch {}
    // Load messages for the new instance
    const msgs = loadMessages(cur);
    chat.messages.length = 0;
    for (const m of msgs) chat.messages.push(m);
    nextId = msgs.length > 0 ? Math.max(...msgs.map(m => m.id || 0)) + 1 : 1;
    chat.isTyping = false;
    conversationId = loadConversationId(cur);
    prevInstance = cur;
}

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

export function updateMessage(id, newContent) {
    const msg = chat.messages.find(m => m.id === id);
    if (msg) {
        msg.content = newContent;
        persistMessages();
    }
}

export function markFeedback(id, rating) {
    const msg = chat.messages.find(m => m.id === id);
    if (msg) {
        msg.feedbackRating = rating;
        persistMessages();
    }
}

export function clearMessages() {
    chat.messages.length = 0;
    nextId = 1;
    try { sessionStorage.removeItem(storageKey(instance.current)); } catch {}
}

/**
 * Format the conversation as clean text for clipboard.
 */
export function formatConversation() {
    if (chat.messages.length === 0) return '';

    const lines = [];
    for (const msg of chat.messages) {
        const prefix = msg.type === 'user' ? 'You' : 'Loom';
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
