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
