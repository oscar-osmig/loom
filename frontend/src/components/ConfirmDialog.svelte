<script>
    let { open, title, message, onConfirm, onCancel } = $props();

    function handleKeydown(e) {
        if (e.key === 'Escape' && open) {
            onCancel?.();
        }
    }
</script>

<svelte:window onkeydown={handleKeydown} />

{#if open}
    <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
    <div class="overlay" onclick={onCancel}>
        <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
        <div class="dialog" onclick={(e) => e.stopPropagation()}>
            <h2 class="dialog-title">{title}</h2>
            <p class="dialog-message">{message}</p>

            <div class="actions">
                <button class="btn btn-cancel" onclick={onCancel}>
                    Cancel
                </button>
                <button class="btn btn-confirm" onclick={onConfirm}>
                    Confirm
                </button>
            </div>
        </div>
    </div>
{/if}

<style>
    .overlay {
        position: fixed;
        inset: 0;
        z-index: 9200;
        display: flex;
        align-items: center;
        justify-content: center;
        background: rgba(0, 0, 0, 0.6);
        backdrop-filter: blur(6px);
        -webkit-backdrop-filter: blur(6px);
        animation: fadeIn 0.2s ease forwards;
    }

    .dialog {
        width: 90%;
        max-width: 400px;
        background: var(--bg-secondary, #1a1a1a);
        border: 1px solid var(--border, #2e2e2e);
        border-radius: 12px;
        padding: 1.5rem;
        box-shadow: 0 16px 48px rgba(0, 0, 0, 0.5);
        animation: scaleIn 0.25s cubic-bezier(0.16, 1, 0.3, 1) forwards;
    }

    .dialog-title {
        font-size: 1rem;
        font-weight: 600;
        color: var(--text-primary, #ffffff);
        margin-bottom: 0.5rem;
    }

    .dialog-message {
        font-size: 0.875rem;
        color: var(--text-secondary, #a1a1aa);
        line-height: 1.5;
        margin-bottom: 1.5rem;
    }

    .actions {
        display: flex;
        justify-content: flex-end;
        gap: 0.625rem;
    }

    .btn {
        padding: 0.5rem 1rem;
        font-size: 0.8125rem;
        font-weight: 500;
        border: none;
        border-radius: 6px;
        cursor: pointer;
        transition: background 0.15s, color 0.15s, box-shadow 0.15s;
    }

    .btn-cancel {
        background: var(--bg-tertiary, #252525);
        color: var(--text-secondary, #a1a1aa);
    }

    .btn-cancel:hover {
        background: var(--border, #2e2e2e);
        color: var(--text-primary, #ffffff);
    }

    .btn-confirm {
        background: var(--error, #ef4444);
        color: #ffffff;
    }

    .btn-confirm:hover {
        background: #dc2626;
        box-shadow: 0 0 12px rgba(239, 68, 68, 0.3);
    }

    @keyframes fadeIn {
        from { opacity: 0; }
        to { opacity: 1; }
    }

    @keyframes scaleIn {
        from {
            transform: scale(0.95);
            opacity: 0;
        }
        to {
            transform: scale(1);
            opacity: 1;
        }
    }
</style>
