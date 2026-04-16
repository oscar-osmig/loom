<script>
    import { isAuthenticated } from '../stores/auth.svelte.js';

    const tips = [
        'Teach me facts like <b>"dogs are animals"</b>',
        'Ask questions like <b>"what are dogs?"</b>',
        'Paste a paragraph and I\'ll extract knowledge from it',
        'Type <b>/help</b> to see all available commands',
        'Try <b>/show</b> to see the knowledge summary',
        'Use <b>/neuron X</b> to inspect any concept',
        'Click the <b>?</b> in the header to learn more about Loom',
        'Type <b>"birds can fly"</b> to teach abilities',
        'Try <b>/analogies X</b> to find similar concepts',
        'Click <b>Visualize</b> to see the knowledge graph',
    ];

    let tipIndex = $state(0);
    let visible = $state(true);

    $effect(() => {
        if (!isAuthenticated()) return;
        const interval = setInterval(() => {
            visible = false;
            setTimeout(() => {
                tipIndex = (tipIndex + 1) % tips.length;
                visible = true;
            }, 400);
        }, 4000);
        return () => clearInterval(interval);
    });
</script>

{#if !isAuthenticated()}
    <div class="welcome">
        <h2>Welcome to Loom</h2>
        <p>Teach me facts, ask questions, or paste paragraphs. I'll weave them into a connected knowledge graph. Type <b>/help</b> for commands.</p>
        <div class="name-prompt">
            <p>What's your name?</p>
            <span>Type your name or nickname, or sign in with Google</span>
        </div>
    </div>
{:else}
    <div class="tips-container">
        <div class="tips-icon">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="10"/>
                <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/>
                <line x1="12" y1="17" x2="12.01" y2="17"/>
            </svg>
        </div>
        <p class="tip-text" class:fade-out={!visible}>{@html tips[tipIndex]}</p>
    </div>
{/if}

<style>
    .welcome {
        text-align: center;
        padding: 4rem 2rem;
        max-width: 500px;
        margin: auto;
    }

    .welcome h2 {
        font-size: 1.5rem;
        font-weight: 700;
        margin-bottom: 0.75rem;
    }

    .welcome p {
        color: var(--text-secondary);
        line-height: 1.6;
    }

    .welcome p :global(b) {
        color: var(--accent-hover);
    }

    .name-prompt {
        margin-top: 1.25rem;
        background: rgba(34, 197, 94, 0.08);
        border: 1px solid rgba(34, 197, 94, 0.3);
        border-radius: 12px;
        padding: 1rem 1.25rem;
        text-align: center;
    }

    .name-prompt p {
        color: var(--success);
        font-size: 0.9375rem;
        font-weight: 500;
        margin-bottom: 0.25rem;
    }

    .name-prompt span {
        color: var(--text-muted);
        font-size: 0.8125rem;
    }

    /* ── Tips (logged in, no messages) ─── */

    .tips-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 1.25rem;
        margin: auto;
        padding: 2rem;
        max-width: 420px;
        text-align: center;
    }

    .tips-icon {
        color: var(--text-muted);
        opacity: 0.5;
        animation: throb 3s ease-in-out infinite;
    }

    .tip-text {
        color: var(--text-muted);
        font-size: 0.9375rem;
        line-height: 1.6;
        transition: opacity 0.35s ease;
    }

    .tip-text :global(b) {
        color: var(--accent-hover);
        font-weight: 600;
    }

    .tip-text.fade-out {
        opacity: 0;
    }

    @keyframes throb {
        0%, 100% { transform: scale(1); opacity: 0.5; }
        50% { transform: scale(1.1); opacity: 0.8; }
    }
</style>
