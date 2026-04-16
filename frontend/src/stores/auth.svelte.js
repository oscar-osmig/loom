/**
 * Auth store — reactive authentication state (Svelte 5 runes).
 */

import { fetchConfig } from '../lib/api.js';

function readStorage(key) {
    try { return localStorage.getItem(key) || ''; } catch { return ''; }
}

function writeStorage(key, value) {
    try {
        if (value) localStorage.setItem(key, value);
        else localStorage.removeItem(key);
    } catch {}
}

export const auth = $state({
    user: readStorage('loom_user'),
    email: readStorage('loom_user_email'),
    picture: readStorage('loom_user_picture'),
    authMethod: readStorage('loom_auth_method') || '', // 'guest' | 'google'
    googleClientId: null,
});

export function isAuthenticated() {
    return !!auth.user;
}

/** Guest = typed a name in chat (no email). */
export function isGuest() {
    return auth.authMethod === 'guest';
}

/** Google-authenticated user (has email). */
export function isGoogleUser() {
    return auth.authMethod === 'google';
}

export function setUser(name, opts) {
    auth.user = name || '';
    writeStorage('loom_user', auth.user);
    if (opts?.email !== undefined) {
        auth.email = opts.email || '';
        writeStorage('loom_user_email', auth.email);
    }
    if (opts?.picture !== undefined) {
        auth.picture = opts.picture || '';
        writeStorage('loom_user_picture', auth.picture);
    }
    if (opts?.authMethod !== undefined) {
        auth.authMethod = opts.authMethod;
        writeStorage('loom_auth_method', auth.authMethod);
    }
}

export function signOut() {
    auth.user = '';
    auth.email = '';
    auth.picture = '';
    auth.authMethod = '';
    writeStorage('loom_user', '');
    writeStorage('loom_user_email', '');
    writeStorage('loom_user_picture', '');
    writeStorage('loom_auth_method', '');
}

export async function initGoogle() {
    const config = await fetchConfig();
    if (config?.google_client_id) {
        auth.googleClientId = config.google_client_id;
    }
}
