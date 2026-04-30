<script>
    import { sendFeedback, submitResponseEdit } from '../lib/api.js';
    import { auth } from '../stores/auth.svelte.js';
    import { updateMessage, markFeedback } from '../stores/chat.svelte.js';

    let { id, content, type = 'assistant', meta = undefined, userInput = '', feedbackRating = null } = $props();

    let feedbackGiven = $state(!!feedbackRating);
    let feedbackSubmitting = $state(false);

    // Edit state
    let isEditing = $state(false);
    let editText = $state('');
    let editSaving = $state(false);
    let editSaved = $state(false);

    const canEdit = $derived(
        (type === 'assistant' || type === 'response') &&
        content && content.length > 0
    );

    function stripHtml(html) {
        return (html || '')
            .replace(/<br\s*\/?>/gi, '\n')
            .replace(/<[^>]+>/g, '')
            .replace(/&amp;/g, '&')
            .replace(/&lt;/g, '<')
            .replace(/&gt;/g, '>')
            .replace(/&quot;/g, '"')
            .replace(/&#x27;/g, "'")
            .trim();
    }

    function startEdit() {
        editText = stripHtml(content);
        isEditing = true;
        editSaved = false;
    }

    function cancelEdit() {
        isEditing = false;
    }

    async function saveEdit() {
        const cleaned = editText.trim();
        if (!cleaned || cleaned === stripHtml(content)) {
            isEditing = false;
            return;
        }
        editSaving = true;
        try {
            await submitResponseEdit({
                message_id: id,
                original_response: content,
                edited_response: cleaned,
                user: auth.user,
                input_text: userInput,
            });
            updateMessage(id, cleaned);
            editSaved = true;
        } catch {}
        editSaving = false;
        isEditing = false;
    }

    function handleEditKeydown(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            saveEdit();
        } else if (e.key === 'Escape') {
            cancelEdit();
        }
    }

    const metaText = $derived.by(() => {
        if (!meta) return '';
        const parts = [];
        if (meta.chunks) parts.push(`${meta.chunks} chunk${meta.chunks !== 1 ? 's' : ''}`);
        if (meta.facts_added) parts.push(`${meta.facts_added} fact${meta.facts_added !== 1 ? 's' : ''}`);
        return parts.join(' / ');
    });

    // Show feedback only on actual responses (not errors/info)
    const showFeedback = $derived(
        !feedbackGiven &&
        (type === 'assistant' || type === 'response') &&
        content && content.length > 0
    );

    // Long-form responses get feedback below, short ones get feedback inline
    const inlineFeedback = $derived(content && content.length < 120);

    async function handleFeedback(rating) {
        if (feedbackSubmitting || feedbackGiven) return;
        feedbackSubmitting = true;
        try {
            await sendFeedback({
                message_id: id,
                rating,
                user: auth.user,
                input_text: userInput,
                response_text: content,
            });
        } catch {}
        markFeedback(id, rating);
        feedbackGiven = true;
        feedbackSubmitting = false;
    }
</script>

<div class="message-wrapper {type}">
    {#if canEdit && !isEditing}
        <div class="edit-btn-row">
            <button class="edit-btn" onclick={startEdit} aria-label="Edit this response" title="Suggest a better response">
                {#if editSaved}
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <polyline points="20 6 9 17 4 12"/>
                    </svg>
                {:else}
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/>
                        <path d="m15 5 4 4"/>
                    </svg>
                {/if}
            </button>
        </div>
    {/if}
    <div class="message {type}">
        {#if isEditing}
            <div class="edit-area">
                <!-- svelte-ignore a11y_autofocus -->
                <textarea
                    class="edit-textarea"
                    bind:value={editText}
                    onkeydown={handleEditKeydown}
                    autofocus
                    rows={Math.max(2, editText.split('\n').length)}
                ></textarea>
                <div class="edit-actions">
                    <button class="edit-save-btn" onclick={saveEdit} disabled={editSaving}>
                        {editSaving ? 'Saving...' : 'Save'}
                    </button>
                    <button class="edit-cancel-btn" onclick={cancelEdit}>Cancel</button>
                    <span class="edit-hint">Enter to save, Esc to cancel</span>
                </div>
            </div>
        {:else}
            {@html content}
        {/if}
        {#if meta && metaText && !isEditing}
            <div class="meta-badge">{metaText}</div>
        {/if}
        {#if showFeedback && inlineFeedback && !isEditing}
            <span class="feedback-inline">
                <button class="fb-btn" onclick={() => handleFeedback('like')} aria-label="I like this response">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M7 10v12"/><path d="M15 5.88 14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H7V10l4-8h.17a2 2 0 0 1 1.73 1l2.1 2.88Z"/>
                    </svg>
                </button>
                <button class="fb-btn dislike" onclick={() => handleFeedback('dislike')} aria-label="I don't like this response">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M17 14V2"/><path d="M9 18.12 10 14H4.17a2 2 0 0 1-1.92-2.56l2.33-8A2 2 0 0 1 6.5 2H17v12l-4 8h-.17a2 2 0 0 1-1.73-1l-2.1-2.88Z"/>
                    </svg>
                </button>
            </span>
        {/if}
    </div>
    {#if showFeedback && !inlineFeedback && !isEditing}
        <div class="feedback-row">
            <button class="fb-btn" onclick={() => handleFeedback('like')} aria-label="I like this response">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M7 10v12"/><path d="M15 5.88 14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H7V10l4-8h.17a2 2 0 0 1 1.73 1l2.1 2.88Z"/>
                </svg>
            </button>
            <button class="fb-btn dislike" onclick={() => handleFeedback('dislike')} aria-label="I don't like this response">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M17 14V2"/><path d="M9 18.12 10 14H4.17a2 2 0 0 1-1.92-2.56l2.33-8A2 2 0 0 1 6.5 2H17v12l-4 8h-.17a2 2 0 0 1-1.73-1l-2.1-2.88Z"/>
                </svg>
            </button>
        </div>
    {/if}
</div>

<style>
    .message-wrapper {
        display: flex;
        flex-direction: column;
        max-width: 80%;
    }
    .message-wrapper.user { align-self: flex-end; }
    .message-wrapper.assistant,
    .message-wrapper.response,
    .message-wrapper.info,
    .message-wrapper.error { align-self: flex-start; }

    .message {
        padding: 1rem 1.25rem;
        border-radius: 16px;
        line-height: 1.6;
        animation: slideIn 0.3s ease;
        font-size: 0.9375rem;
        word-break: break-word;
        position: relative;
    }

    @keyframes slideIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }

    .message.user {
        background: var(--user-msg);
        color: white;
        border-bottom-right-radius: 4px;
    }

    .message.assistant,
    .message.response {
        background: var(--assistant-msg);
        color: var(--text-primary);
        border-bottom-left-radius: 4px;
        border: 1px solid var(--border);
    }

    .message.info {
        background: var(--bg-tertiary);
        color: var(--text-secondary);
        border-left: 3px solid var(--accent);
        font-family: 'JetBrains Mono', 'Fira Code', monospace;
        font-size: 0.8125rem;
        white-space: pre-wrap;
    }

    .message.error {
        background: rgba(239, 68, 68, 0.1);
        color: var(--error);
        border-left: 3px solid var(--error);
    }

    .message :global(b) {
        color: var(--accent-hover);
        font-weight: 600;
    }

    .meta-badge {
        display: inline-block;
        background: var(--accent);
        color: white;
        font-size: 0.6875rem;
        padding: 0.25rem 0.625rem;
        border-radius: 100px;
        margin-top: 0.75rem;
        font-weight: 500;
    }

    /* ── Feedback buttons ── */

    .feedback-inline {
        display: inline-flex;
        gap: 0.25rem;
        margin-left: 0.5rem;
        vertical-align: middle;
        opacity: 0.4;
        transition: opacity 0.2s;
    }

    .message:hover .feedback-inline {
        opacity: 1;
    }

    .feedback-row {
        display: flex;
        gap: 0.375rem;
        margin-top: 0.5rem;
        padding-left: 0.5rem;
        opacity: 0.5;
        transition: opacity 0.2s;
    }

    .message-wrapper:hover .feedback-row {
        opacity: 1;
    }

    .fb-btn {
        background: transparent;
        border: 1px solid var(--border);
        color: var(--text-muted);
        padding: 0.25rem 0.4rem;
        border-radius: 6px;
        cursor: pointer;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        transition: all 0.15s;
    }

    .fb-btn:hover {
        color: var(--success);
        border-color: var(--success);
        background: rgba(34, 197, 94, 0.1);
    }

    .fb-btn.dislike:hover {
        color: var(--error);
        border-color: var(--error);
        background: rgba(239, 68, 68, 0.1);
    }

    /* ── Edit button ── */

    .edit-btn-row {
        display: flex;
        justify-content: flex-end;
        opacity: 0;
        transition: opacity 0.15s;
    }

    .message-wrapper:hover .edit-btn-row {
        opacity: 1;
    }

    .edit-btn {
        background: transparent;
        border: 1px solid transparent;
        color: var(--text-muted);
        padding: 0.2rem 0.3rem;
        border-radius: 5px;
        cursor: pointer;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        transition: all 0.15s;
    }

    .edit-btn:hover {
        color: var(--accent);
        border-color: var(--border);
        background: var(--bg-secondary);
    }

    /* ── Edit area ── */

    .edit-area {
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
        width: 100%;
    }

    .edit-textarea {
        width: 100%;
        min-height: 2.5rem;
        padding: 0.5rem 0.625rem;
        background: var(--bg-primary);
        color: var(--text-primary);
        border: 1px solid var(--accent);
        border-radius: 8px;
        font-family: inherit;
        font-size: 0.9375rem;
        line-height: 1.6;
        resize: vertical;
        outline: none;
        box-sizing: border-box;
    }

    .edit-textarea:focus {
        border-color: var(--accent-hover);
        box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.15);
    }

    .edit-actions {
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }

    .edit-save-btn {
        background: var(--accent);
        color: white;
        border: none;
        padding: 0.3rem 0.75rem;
        border-radius: 6px;
        font-size: 0.8125rem;
        font-weight: 500;
        cursor: pointer;
        transition: background 0.15s;
    }

    .edit-save-btn:hover:not(:disabled) {
        background: var(--accent-hover);
    }

    .edit-save-btn:disabled {
        opacity: 0.6;
        cursor: not-allowed;
    }

    .edit-cancel-btn {
        background: transparent;
        color: var(--text-muted);
        border: 1px solid var(--border);
        padding: 0.3rem 0.75rem;
        border-radius: 6px;
        font-size: 0.8125rem;
        cursor: pointer;
        transition: all 0.15s;
    }

    .edit-cancel-btn:hover {
        color: var(--text-primary);
        border-color: var(--text-muted);
    }

    .edit-hint {
        font-size: 0.6875rem;
        color: var(--text-muted);
        margin-left: auto;
    }
</style>
