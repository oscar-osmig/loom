/**
 * Loom utility functions.
 */

const GREETING_WORDS = new Set([
    'hello', 'hi', 'hey', 'bye', 'goodbye', 'thanks', 'thank',
    'please', 'yes', 'no', 'ok', 'okay', 'sure', 'welcome'
]);

/**
 * Validate a display name: 1-3 words, letters/numbers/hyphens only, max 30 chars,
 * and not a common greeting word.
 * @param {string} text
 * @returns {boolean}
 */
export function isValidName(text) {
    if (!text || typeof text !== 'string') return false;

    const trimmed = text.trim();
    if (trimmed.length === 0 || trimmed.length > 30) return false;

    // Only letters, numbers, hyphens, and spaces allowed
    if (!/^[a-zA-Z0-9\- ]+$/.test(trimmed)) return false;

    const words = trimmed.split(/\s+/);
    if (words.length < 1 || words.length > 3) return false;

    // Reject if the entire input is a single greeting word
    if (words.length === 1 && GREETING_WORDS.has(words[0].toLowerCase())) return false;

    return true;
}

/**
 * Escape HTML special characters to prevent XSS.
 * @param {string} str
 * @returns {string}
 */
export function escapeHtml(str) {
    if (!str || typeof str !== 'string') return '';

    return str
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

/**
 * Sanitize server-generated response HTML before rendering with {@html}.
 *
 * The backend composes responses with a small set of formatting tags
 * (<b>, <i>, <br>) and &nbsp; entities, but interpolates user-taught
 * concept names into them unescaped. Escape everything first, then
 * restore only the app's own known-safe formatting so injected markup
 * renders as inert text.
 * @param {string} str
 * @returns {string}
 */
export function sanitizeServerHtml(str) {
    if (!str || typeof str !== 'string') return '';

    return escapeHtml(str)
        // Restore the app's own formatting tags (no attributes allowed)
        .replace(/&lt;(\/?)(b|i|u|em|strong)&gt;/gi, '<$1$2>')
        .replace(/&lt;br\s*\/?&gt;/gi, '<br>')
        // Restore harmless character entities the server emits (e.g. &nbsp;)
        .replace(/&amp;(nbsp|amp|lt|gt|quot|#39|#x27|bull|middot);/gi, '&$1;');
}
