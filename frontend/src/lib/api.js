/**
 * Loom API client — fetch wrappers for all Flask endpoints.
 */

import { instance } from '../stores/instance.svelte.js';

const BASE = '';  // same origin; change to 'http://localhost:5000' during dev if needed

const DEFAULT_TIMEOUT_MS = 30000;   // 30s for regular requests
const UPLOAD_TIMEOUT_MS = 300000;   // 5min for training uploads (large imports)

/** Current instance name for threading through requests. */
function inst() { return instance.current; }

/** Read the stored Google ID token (set by the auth store on sign-in). */
function authToken() {
    try { return localStorage.getItem('loom_id_token') || ''; } catch { return ''; }
}

/**
 * Shared fetch helper: attaches auth header, applies a timeout, checks res.ok,
 * and throws an Error carrying status + parsed error body on failure.
 * @param {string} url
 * @param {RequestInit} [options]
 * @param {number} [timeoutMs]
 * @returns {Promise<any>} Parsed JSON body.
 */
async function request(url, options = {}, timeoutMs = DEFAULT_TIMEOUT_MS) {
    const headers = { ...(options.headers || {}) };
    const token = authToken();
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const signal = options.signal ||
        (typeof AbortSignal !== 'undefined' && AbortSignal.timeout
            ? AbortSignal.timeout(timeoutMs)
            : undefined);

    const res = await fetch(url, { ...options, headers, signal });

    if (!res.ok) {
        let body = null;
        try { body = await res.json(); } catch { /* body isn't JSON */ }
        const message = (body && (body.error || body.message)) ||
            `Request failed: ${res.status} ${res.statusText}`;
        const err = new Error(message);
        err.status = res.status;
        err.body = body;
        throw err;
    }

    return res.json();
}

/**
 * GET /api/config
 * @returns {{ google_client_id: string } | { error: string }}
 */
export async function fetchConfig() {
    try {
        return await request(`${BASE}/api/config`);
    } catch (err) {
        return { error: err.message || 'Failed to fetch config' };
    }
}

/**
 * POST /api/chat
 */
export async function sendChat(message, user, email, conversationId) {
    try {
        // Training-style messages (/train, /load, pasted JSON arrays) can run long
        const trimmed = (message || '').trim().toLowerCase();
        const isTraining = trimmed.startsWith('[') ||
            /^\/?(train|load|load-all)\b/.test(trimmed);
        return await request(`${BASE}/api/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message, user, email, conversation_id: conversationId, instance: inst() })
        }, isTraining ? UPLOAD_TIMEOUT_MS : DEFAULT_TIMEOUT_MS);
    } catch (err) {
        return { error: err.message || 'Failed to send message' };
    }
}

/**
 * GET /api/graph
 */
export async function fetchGraph() {
    try {
        return await request(`${BASE}/api/graph?t=${Date.now()}&instance=${encodeURIComponent(inst())}`, {
            cache: 'no-store'
        });
    } catch (err) {
        return { error: err.message || 'Failed to fetch graph' };
    }
}

/**
 * POST /api/upload-training-batch
 */
export async function uploadTrainingBatch(files, user) {
    try {
        const formData = new FormData();
        for (const file of files) {
            formData.append('files', file);
        }
        if (user) {
            formData.append('user', user);
        }
        formData.append('instance', inst());
        return await request(`${BASE}/api/upload-training-batch`, {
            method: 'POST',
            body: formData
        }, UPLOAD_TIMEOUT_MS);
    } catch (err) {
        return { error: err.message || 'Failed to upload training files' };
    }
}

/**
 * GET /api/collaborators
 */
export async function fetchCollaborators(user, email) {
    try {
        const params = new URLSearchParams();
        if (user) params.set('user', user);
        if (email) params.set('email', email);
        params.set('instance', inst());
        return await request(`${BASE}/api/collaborators?${params}`);
    } catch (err) {
        return { error: err.message, total_collaborators: 0, by_neurons: [], by_corrections: [], by_messages: [] };
    }
}

/**
 * GET /api/style
 */
export async function fetchStyle(email) {
    try {
        return await request(`${BASE}/api/style?email=${encodeURIComponent(email || '')}&instance=${encodeURIComponent(inst())}`);
    } catch (err) {
        return { error: err.message };
    }
}

/**
 * POST /api/feedback
 */
export async function sendFeedback(payload) {
    try {
        return await request(`${BASE}/api/feedback`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ...payload, instance: inst() })
        });
    } catch (err) {
        return { error: err.message };
    }
}

/**
 * POST /api/response-edit
 */
export async function submitResponseEdit(payload) {
    try {
        return await request(`${BASE}/api/response-edit`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ...payload, instance: inst() })
        });
    } catch (err) {
        return { error: err.message };
    }
}

/**
 * GET /api/check-nickname?name=...
 */
export async function checkNickname(name) {
    try {
        return await request(`${BASE}/api/check-nickname?name=${encodeURIComponent(name)}&instance=${encodeURIComponent(inst())}`);
    } catch (err) {
        return { available: false, error: err.message };
    }
}

/**
 * GET /api/questions
 */
export async function fetchQuestions() {
    try {
        return await request(`${BASE}/api/questions?instance=${encodeURIComponent(inst())}`);
    } catch (err) {
        return { error: err.message || 'Failed to fetch questions' };
    }
}

// ==================== INSTANCE MANAGEMENT ====================

/**
 * GET /api/instances?email=...
 */
export async function fetchInstances(email) {
    try {
        const params = new URLSearchParams();
        if (email) params.set('email', email);
        return await request(`${BASE}/api/instances?${params}`);
    } catch (err) {
        return { instances: [], error: err.message };
    }
}

/**
 * POST /api/instances
 */
export async function createInstance(email, displayName) {
    try {
        return await request(`${BASE}/api/instances`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, display_name: displayName })
        });
    } catch (err) {
        return { error: err.message };
    }
}

/**
 * DELETE /api/instances
 */
export async function deleteInstance(email, instanceName) {
    try {
        return await request(`${BASE}/api/instances`, {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, instance_name: instanceName })
        });
    } catch (err) {
        return { error: err.message };
    }
}
