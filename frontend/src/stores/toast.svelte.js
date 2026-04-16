/**
 * Toast store — reactive notification banner (Svelte 5 runes).
 */

let hideTimer = null;

export const toast = $state({
    visible: false,
    type: '',
    title: '',
    message: ''
});

/**
 * Show a toast notification. Auto-hides after a delay.
 * @param {'success' | 'error' | 'warning' | 'info'} type
 * @param {string} title
 * @param {string} message
 */
export function showToast(type, title, message) {
    // Clear any pending auto-hide
    if (hideTimer) {
        clearTimeout(hideTimer);
        hideTimer = null;
    }

    toast.visible = true;
    toast.type = type;
    toast.title = title;
    toast.message = message;

    const delay = type === 'success' ? 4000 : 5000;
    hideTimer = setTimeout(() => {
        hideToast();
    }, delay);
}

/**
 * Hide the toast immediately.
 */
export function hideToast() {
    if (hideTimer) {
        clearTimeout(hideTimer);
        hideTimer = null;
    }
    toast.visible = false;
    toast.type = '';
    toast.title = '';
    toast.message = '';
}
