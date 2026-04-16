/**
 * graph-utils.js
 * Shared utility functions for the graph visualizer.
 */

/**
 * Simple deterministic string hash (djb2 variant).
 * Returns a positive 32-bit integer.
 * @param {string} str
 * @returns {number}
 */
export function hashString(str) {
    let hash = 5381;
    for (let i = 0; i < str.length; i++) {
        hash = ((hash << 5) + hash + str.charCodeAt(i)) | 0;
    }
    return hash >>> 0; // ensure unsigned
}

/**
 * Returns an HSL color string for a cluster/category name.
 * Distributes hues evenly based on the hash, with consistent
 * saturation and lightness for readability on dark backgrounds.
 * @param {string} category
 * @returns {string} HSL color string
 */
export function getClusterColor(category) {
    const h = hashString(category) % 360;
    return `hsl(${h}, 70%, 55%)`;
}

/**
 * Returns a consistent HSL color for a given node ID.
 * Uses a blue-pink bioluminescent palette range (hue 200-320).
 * @param {string} id
 * @returns {string} HSL color string
 */
export function getNodeColor(id) {
    const h = 200 + (hashString(id) % 120); // 200-320 range
    const s = 65 + (hashString(id + '_s') % 20); // 65-85
    const l = 55 + (hashString(id + '_l') % 15); // 55-70
    return `hsl(${h}, ${s}%, ${l}%)`;
}
