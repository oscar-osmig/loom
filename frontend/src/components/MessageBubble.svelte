<script>
    let { content, type = 'assistant', meta = undefined } = $props();

    const metaText = $derived.by(() => {
        if (!meta) return '';
        const parts = [];
        if (meta.chunks) parts.push(`${meta.chunks} chunk${meta.chunks !== 1 ? 's' : ''}`);
        if (meta.facts_added) parts.push(`${meta.facts_added} fact${meta.facts_added !== 1 ? 's' : ''}`);
        return parts.join(' / ');
    });
</script>

<div class="message {type}">
    {@html content}
    {#if meta && metaText}
        <div class="meta-badge">{metaText}</div>
    {/if}
</div>

<style>
    .message {
        max-width: 80%;
        padding: 1rem 1.25rem;
        border-radius: 16px;
        line-height: 1.6;
        animation: slideIn 0.3s ease;
        font-size: 0.9375rem;
        word-break: break-word;
    }

    @keyframes slideIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }

    .message.user {
        background: var(--user-msg);
        color: white;
        align-self: flex-end;
        border-bottom-right-radius: 4px;
    }

    .message.assistant,
    .message.response {
        background: var(--assistant-msg);
        color: var(--text-primary);
        align-self: flex-start;
        border-bottom-left-radius: 4px;
        border: 1px solid var(--border);
    }

    .message.info {
        background: var(--bg-tertiary);
        color: var(--text-secondary);
        align-self: flex-start;
        border-left: 3px solid var(--accent);
        font-family: 'JetBrains Mono', 'Fira Code', monospace;
        font-size: 0.8125rem;
        white-space: pre-wrap;
        max-width: 90%;
    }

    .message.error {
        background: rgba(239, 68, 68, 0.1);
        color: var(--error);
        align-self: flex-start;
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
</style>
