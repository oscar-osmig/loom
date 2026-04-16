<script>
    import { toast, hideToast } from '../stores/toast.svelte.js';
</script>

{#if toast.visible}
    <div class="toast-wrapper" class:visible={toast.visible}>
        <div class="toast" class:success={toast.type === 'success'} class:error={toast.type === 'error'} class:warning={toast.type === 'warning'} class:info={toast.type === 'info'}>
            <span class="icon">
                {#if toast.type === 'success'}
                    <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                        <path d="M16.667 5L7.5 14.167 3.333 10" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                {:else if toast.type === 'error'}
                    <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                        <path d="M15 5L5 15M5 5l10 10" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                {:else if toast.type === 'warning'}
                    <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                        <path d="M10 7v4m0 2h.01M3.072 17h13.856c1.078 0 1.756-1.167 1.218-2.1L11.218 3.1c-.539-.933-1.897-.933-2.436 0L1.854 14.9C1.316 15.833 1.994 17 3.072 17z" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                {:else}
                    <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                        <circle cx="10" cy="10" r="8" stroke="currentColor" stroke-width="1.5"/>
                        <path d="M10 9v4m0-6h.01" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                    </svg>
                {/if}
            </span>

            <div class="content">
                {#if toast.title}
                    <strong class="title">{toast.title}</strong>
                {/if}
                {#if toast.message}
                    <span class="message">{toast.message}</span>
                {/if}
            </div>

            <button class="close" onclick={hideToast} aria-label="Dismiss notification">
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                    <path d="M12 4L4 12M4 4l8 8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
            </button>
        </div>
    </div>
{/if}

<style>
    .toast-wrapper {
        position: fixed;
        top: 1.25rem;
        right: 1.25rem;
        z-index: 9999;
        animation: slideIn 0.3s cubic-bezier(0.16, 1, 0.3, 1) forwards;
    }

    .toast {
        display: flex;
        align-items: flex-start;
        gap: 0.75rem;
        min-width: 300px;
        max-width: 420px;
        padding: 0.875rem 1rem;
        background: var(--bg-secondary, #1a1a1a);
        border: 1px solid var(--border, #2e2e2e);
        border-left: 4px solid var(--border, #2e2e2e);
        border-radius: 8px;
        box-shadow: 0 8px 30px rgba(0, 0, 0, 0.4), 0 2px 8px rgba(0, 0, 0, 0.2);
        color: var(--text-primary, #ffffff);
        font-size: 0.875rem;
    }

    .toast.success {
        border-left-color: var(--success, #22c55e);
    }
    .toast.success .icon {
        color: var(--success, #22c55e);
    }

    .toast.error {
        border-left-color: var(--error, #ef4444);
    }
    .toast.error .icon {
        color: var(--error, #ef4444);
    }

    .toast.warning {
        border-left-color: var(--warning, #f59e0b);
    }
    .toast.warning .icon {
        color: var(--warning, #f59e0b);
    }

    .toast.info {
        border-left-color: var(--accent, #6366f1);
    }
    .toast.info .icon {
        color: var(--accent, #6366f1);
    }

    .icon {
        flex-shrink: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        margin-top: 1px;
    }

    .content {
        flex: 1;
        display: flex;
        flex-direction: column;
        gap: 0.2rem;
    }

    .title {
        font-weight: 600;
        line-height: 1.3;
    }

    .message {
        color: var(--text-secondary, #a1a1aa);
        line-height: 1.4;
    }

    .close {
        flex-shrink: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        width: 24px;
        height: 24px;
        border: none;
        border-radius: 4px;
        background: transparent;
        color: var(--text-muted, #71717a);
        cursor: pointer;
        transition: color 0.15s, background 0.15s;
    }

    .close:hover {
        color: var(--text-primary, #ffffff);
        background: var(--bg-tertiary, #252525);
    }

    @keyframes slideIn {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
</style>
