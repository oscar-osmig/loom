<script>
    import { ui, setTrainInfoOpen } from '../stores/ui.svelte.js';

    function close() {
        setTrainInfoOpen(false);
    }

    function onKeydown(e) {
        if (e.key === 'Escape') {
            close();
        }
    }
</script>

<svelte:window onkeydown={onKeydown} />

{#if ui.trainInfoOpen}
    <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
    <div class="overlay" onclick={close}>
        <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
        <div class="dialog" onclick={(e) => e.stopPropagation()}>
            <header class="dialog-header">
                <h2>Training File Formats</h2>
                <button class="close-btn" onclick={close} aria-label="Close dialog">
                    <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                        <path d="M13.5 4.5L4.5 13.5M4.5 4.5l9 9" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                </button>
            </header>

            <div class="dialog-body">
                <section>
                    <h3>JSON Format</h3>
                    <p>An array of objects with <code>subject</code>, <code>relation</code>, and <code>object</code> fields:</p>
                    <pre><code>{`[
  { "subject": "dogs", "relation": "is", "object": "animals" },
  { "subject": "dogs", "relation": "has", "object": "four legs" },
  { "subject": "cats", "relation": "can", "object": "climb trees" }
]`}</code></pre>
                </section>

                <section>
                    <h3>TXT Format</h3>
                    <p>Plain text with one natural language statement per line:</p>
                    <pre><code>{`dogs are animals
dogs have four legs
cats can climb trees
the sun is a star
water is made from hydrogen and oxygen`}</code></pre>
                </section>

                <section>
                    <h3>Supported Relations</h3>
                    <p>Loom recognizes the following relation types:</p>
                    <div class="tags">
                        {#each ['is', 'has', 'can', 'causes', 'part_of', 'lives_in', 'eats', 'made_from', 'used_for', 'needs', 'produces', 'contains', 'enables', 'prevents', 'leads_to', 'looks_like', 'becomes', 'opposite_of'] as rel}
                            <span class="tag">{rel}</span>
                        {/each}
                    </div>
                </section>
            </div>
        </div>
    </div>
{/if}

<style>
    .overlay {
        position: fixed;
        inset: 0;
        z-index: 8500;
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
        max-width: 560px;
        max-height: 80vh;
        display: flex;
        flex-direction: column;
        background: var(--bg-secondary, #1a1a1a);
        border: 1px solid var(--border, #2e2e2e);
        border-radius: 12px;
        box-shadow: 0 16px 48px rgba(0, 0, 0, 0.5);
        animation: scaleIn 0.25s cubic-bezier(0.16, 1, 0.3, 1) forwards;
    }

    .dialog-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 1.125rem 1.25rem;
        border-bottom: 1px solid var(--border, #2e2e2e);
    }

    .dialog-header h2 {
        font-size: 1rem;
        font-weight: 600;
        color: var(--text-primary, #ffffff);
    }

    .close-btn {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 30px;
        height: 30px;
        border: none;
        border-radius: 6px;
        background: transparent;
        color: var(--text-muted, #71717a);
        cursor: pointer;
        transition: color 0.15s, background 0.15s;
    }

    .close-btn:hover {
        color: var(--text-primary, #ffffff);
        background: var(--bg-tertiary, #252525);
    }

    .dialog-body {
        padding: 1.25rem;
        overflow-y: auto;
        display: flex;
        flex-direction: column;
        gap: 1.5rem;
    }

    section h3 {
        font-size: 0.875rem;
        font-weight: 600;
        color: var(--accent, #6366f1);
        margin-bottom: 0.5rem;
    }

    section p {
        font-size: 0.8125rem;
        color: var(--text-secondary, #a1a1aa);
        line-height: 1.5;
        margin-bottom: 0.625rem;
    }

    section p code {
        font-family: 'SF Mono', 'Fira Code', monospace;
        font-size: 0.75rem;
        background: var(--bg-tertiary, #252525);
        padding: 0.125rem 0.375rem;
        border-radius: 4px;
        color: var(--accent-hover, #818cf8);
    }

    pre {
        background: var(--bg-primary, #0f0f0f);
        border: 1px solid var(--border, #2e2e2e);
        border-radius: 8px;
        padding: 0.875rem 1rem;
        overflow-x: auto;
    }

    pre code {
        font-family: 'SF Mono', 'Fira Code', monospace;
        font-size: 0.75rem;
        line-height: 1.6;
        color: var(--text-secondary, #a1a1aa);
    }

    .tags {
        display: flex;
        flex-wrap: wrap;
        gap: 0.375rem;
    }

    .tag {
        display: inline-block;
        font-family: 'SF Mono', 'Fira Code', monospace;
        font-size: 0.6875rem;
        font-weight: 500;
        padding: 0.25rem 0.5rem;
        background: var(--bg-tertiary, #252525);
        border: 1px solid var(--border, #2e2e2e);
        border-radius: 4px;
        color: var(--accent-hover, #818cf8);
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
