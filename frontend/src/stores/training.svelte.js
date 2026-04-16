/**
 * Training store — reactive spinner state (Svelte 5 runes).
 */

export const training = $state({
    active: false,
    text: '',
    sub: '',
    startTime: 0
});

/**
 * Show the training spinner.
 * @param {string} text — primary status message
 * @param {string} [sub] — secondary detail line
 */
export function showSpinner(text, sub) {
    training.active = true;
    training.text = text || '';
    training.sub = sub || '';
    training.startTime = Date.now();
}

/**
 * Hide the training spinner.
 */
export function hideSpinner() {
    training.active = false;
    training.text = '';
    training.sub = '';
    // keep startTime so elapsed time can still be read after hide
}
