/**
 * Loom API client — fetch wrappers for all Flask endpoints.
 */

import { instance } from '../stores/instance.svelte.js';

const BASE = '';  // same origin; change to 'http://localhost:5000' during dev if needed

/** Current instance name for threading through requests. */
function inst() { return instance.current; }

/**
 * GET /api/config
 * @returns {{ google_client_id: string } | { error: string }}
 */
export async function fetchConfig() {
    try {
        const res = await fetch(`${BASE}/api/config`);
        return await res.json();
    } catch (err) {
        return { error: err.message || 'Failed to fetch config' };
    }
}

/**
 * POST /api/chat
 */
export async function sendChat(message, user, email, conversationId) {
    try {
        const res = await fetch(`${BASE}/api/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message, user, email, conversation_id: conversationId, instance: inst() })
        });
        return await res.json();
    } catch (err) {
        return { error: err.message || 'Failed to send message' };
    }
}

/**
 * GET /api/graph
 */
export async function fetchGraph() {
    try {
        const res = await fetch(`${BASE}/api/graph?t=${Date.now()}&instance=${encodeURIComponent(inst())}`, {
            cache: 'no-store'
        });
        return await res.json();
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
        const res = await fetch(`${BASE}/api/upload-training-batch`, {
            method: 'POST',
            body: formData
        });
        return await res.json();
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
        const res = await fetch(`${BASE}/api/collaborators?${params}`);
        return await res.json();
    } catch (err) {
        return { error: err.message, total_collaborators: 0, by_neurons: [], by_corrections: [], by_messages: [] };
    }
}

/**
 * GET /api/style
 */
export async function fetchStyle(email) {
    try {
        const res = await fetch(`${BASE}/api/style?email=${encodeURIComponent(email || '')}&instance=${encodeURIComponent(inst())}`);
        return await res.json();
    } catch (err) {
        return { error: err.message };
    }
}

/**
 * POST /api/feedback
 */
export async function sendFeedback(payload) {
    try {
        const res = await fetch(`${BASE}/api/feedback`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ...payload, instance: inst() })
        });
        return await res.json();
    } catch (err) {
        return { error: err.message };
    }
}

/**
 * POST /api/response-edit
 */
export async function submitResponseEdit(payload) {
    try {
        const res = await fetch(`${BASE}/api/response-edit`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ...payload, instance: inst() })
        });
        return await res.json();
    } catch (err) {
        return { error: err.message };
    }
}

/**
 * GET /api/check-nickname?name=...
 */
export async function checkNickname(name) {
    try {
        const res = await fetch(`${BASE}/api/check-nickname?name=${encodeURIComponent(name)}&instance=${encodeURIComponent(inst())}`);
        return await res.json();
    } catch (err) {
        return { available: false, error: err.message };
    }
}

/**
 * GET /api/questions
 */
export async function fetchQuestions() {
    try {
        const res = await fetch(`${BASE}/api/questions?instance=${encodeURIComponent(inst())}`);
        return await res.json();
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
        const res = await fetch(`${BASE}/api/instances?${params}`);
        return await res.json();
    } catch (err) {
        return { instances: [], error: err.message };
    }
}

/**
 * POST /api/instances
 */
export async function createInstance(email, displayName) {
    try {
        const res = await fetch(`${BASE}/api/instances`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, display_name: displayName })
        });
        return await res.json();
    } catch (err) {
        return { error: err.message };
    }
}

/**
 * DELETE /api/instances
 */
export async function deleteInstance(email, instanceName) {
    try {
        const res = await fetch(`${BASE}/api/instances`, {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, instance_name: instanceName })
        });
        return await res.json();
    } catch (err) {
        return { error: err.message };
    }
}
