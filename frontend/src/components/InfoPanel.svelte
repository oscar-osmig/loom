<script>
    import { ui, closeInfoPanel } from '../stores/ui.svelte.js';

    // Plain variables — NOT $state — to avoid reactive loops with the timer
    let hovered = false;
    let autoCloseTimer = null;

    function startAutoClose() {
        clearAutoClose();
        autoCloseTimer = setTimeout(() => {
            autoCloseTimer = null;
            closeInfoPanel();
        }, 5000);
    }

    function clearAutoClose() {
        if (autoCloseTimer) {
            clearTimeout(autoCloseTimer);
            autoCloseTimer = null;
        }
    }

    function handleMouseEnter() {
        hovered = true;
        clearAutoClose();
    }

    function handleMouseLeave() {
        hovered = false;
        if (ui.infoPanelOpen) {
            startAutoClose();
        }
    }

    function handleKeydown(e) {
        if (e.key === 'Escape' && ui.infoPanelOpen) {
            closeInfoPanel();
        }
    }

    // Only react to the panel opening/closing
    $effect(() => {
        const open = ui.infoPanelOpen;
        if (open) {
            // Always start auto-close when panel opens (mouse isn't on it yet)
            startAutoClose();
        } else {
            clearAutoClose();
            hovered = false;
        }
    });

    $effect(() => {
        return () => clearAutoClose();
    });
</script>

<svelte:window onkeydown={handleKeydown} />

{#if ui.infoPanelOpen}
    <!-- svelte-ignore a11y_click_events_have_key_events -->
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div class="info-backdrop" onclick={() => closeInfoPanel()}></div>

    <div
        class="info-panel"
        role="complementary"
        aria-label={ui.infoPanelTitle}
        onmouseenter={handleMouseEnter}
        onmouseleave={handleMouseLeave}
    >
        <div class="info-panel-header">
            <h3>{ui.infoPanelTitle}</h3>
            <!-- svelte-ignore a11y_click_events_have_key_events -->
            <!-- svelte-ignore a11y_no_static_element_interactions -->
            <div class="info-panel-close" onclick={() => closeInfoPanel()}>&#x2715;</div>
        </div>
        <div class="info-panel-content">
            {@html ui.infoPanelContent}
        </div>
    </div>
{/if}

<style>
    .info-backdrop {
        position: fixed;
        inset: 0;
        background: rgba(0, 0, 0, 0.3);
        z-index: 149;
    }

    .info-panel {
        position: fixed;
        left: 0;
        top: 0;
        bottom: 0;
        width: 320px;
        background: var(--bg-secondary);
        border-right: 1px solid var(--border);
        box-shadow: 4px 0 24px rgba(0, 0, 0, 0.4);
        z-index: 150;
        display: flex;
        flex-direction: column;
        animation: slideInLeft 0.25s ease;
    }

    @keyframes slideInLeft {
        from { opacity: 0; transform: translateX(-20px); }
        to { opacity: 1; transform: translateX(0); }
    }

    .info-panel-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 1rem 1.25rem;
        border-bottom: 1px solid var(--border);
        flex-shrink: 0;
    }

    .info-panel-header h3 {
        font-size: 0.9375rem;
        font-weight: 600;
        color: var(--text-primary);
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }

    .info-panel-header h3::before {
        content: '';
        width: 8px;
        height: 8px;
        background: var(--accent);
        border-radius: 50%;
    }

    .info-panel-close {
        background: var(--bg-tertiary);
        border: 1px solid var(--border);
        color: var(--text-secondary);
        width: 32px;
        height: 32px;
        border-radius: 8px;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: all 0.2s;
        flex-shrink: 0;
        font-size: 1rem;
        line-height: 1;
        user-select: none;
    }

    .info-panel-close:hover {
        background: rgba(239, 68, 68, 0.15);
        border-color: var(--error);
        color: var(--error);
    }

    .info-panel-content {
        flex: 1;
        overflow-y: auto;
        padding: 1rem 1.25rem;
        font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
        font-size: 0.8125rem;
        line-height: 1.7;
        color: var(--text-secondary);
        white-space: pre-wrap;
        scrollbar-width: none;
        -ms-overflow-style: none;
    }

    .info-panel-content::-webkit-scrollbar { display: none; }

    .info-panel-content :global(b) {
        color: var(--accent-hover);
        font-weight: 600;
    }

    @media (max-width: 768px) {
        .info-panel {
            left: 0; right: 0; bottom: 0; top: auto;
            width: auto; max-height: 50vh;
            border-right: none; border-top: 1px solid var(--border);
            border-radius: 16px 16px 0 0;
            box-shadow: 0 -4px 24px rgba(0, 0, 0, 0.3);
        }
        @keyframes slideInLeft {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }
    }
</style>
