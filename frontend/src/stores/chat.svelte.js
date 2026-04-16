/**
 * Chat store — reactive message list (Svelte 5 runes).
 */

let nextId = 1;

export const chat = $state({
    messages: [],
    isTyping: false,
});

export function addMessage(content, type, meta) {
    chat.messages.push({
        id: nextId++,
        content,
        type,
        meta: meta || undefined
    });
}

export function setTyping(value) {
    chat.isTyping = value;
}

export function clearMessages() {
    chat.messages.length = 0;
}
