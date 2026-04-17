/**
 * Loom API client — fetch wrappers for all Flask endpoints.
 */

const BASE = '';  // same origin; change to 'http://localhost:5000' during dev if needed

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
 * @param {string} message
 * @param {string} user
 * @param {string} email
 * @returns {{ response: string, type: string, meta?: object } | { error: string }}
 */
export async function sendChat(message, user, email, conversationId) {
    try {
        const res = await fetch(`${BASE}/api/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message, user, email, conversation_id: conversationId })
        });
        return await res.json();
    } catch (err) {
        return { error: err.message || 'Failed to send message' };
    }
}

/**
 * GET /api/graph
 * @returns {{ nodes: Array, edges: Array, ... } | { error: string }}
 */
export async function fetchGraph() {
    try {
        const res = await fetch(`${BASE}/api/graph`);
        return await res.json();
    } catch (err) {
        return { error: err.message || 'Failed to fetch graph' };
    }
}

/**
 * POST /api/upload-training-batch
 * @param {FileList|File[]} files
 * @param {string} user
 * @returns {{ total_loaded: number, files_processed: number, files: Array, errors?: Array } | { error: string }}
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
 * GET /api/style
 * Returns what Loom has learned about writing style.
 */
export async function fetchStyle(email) {
    try {
        const res = await fetch(`${BASE}/api/style?email=${encodeURIComponent(email || '')}`);
        return await res.json();
    } catch (err) {
        return { error: err.message };
    }
}

/**
 * POST /api/feedback
 * Records a like/dislike on an assistant response.
 */
export async function sendFeedback(payload) {
    try {
        const res = await fetch(`${BASE}/api/feedback`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        return await res.json();
    } catch (err) {
        return { error: err.message };
    }
}

/**
 * GET /api/check-nickname?name=...
 * @param {string} name
 * @returns {{ available: boolean }}
 */
export async function checkNickname(name) {
    try {
        const res = await fetch(`${BASE}/api/check-nickname?name=${encodeURIComponent(name)}`);
        return await res.json();
    } catch (err) {
        return { available: false, error: err.message };
    }
}

/**
 * GET /api/questions
 * @returns {{ questions: Array, count: number, type: string } | { error: string }}
 */
export async function fetchQuestions() {
    try {
        const res = await fetch(`${BASE}/api/questions`);
        return await res.json();
    } catch (err) {
        return { error: err.message || 'Failed to fetch questions' };
    }
}
