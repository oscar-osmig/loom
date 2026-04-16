<script>
    import { training } from '../stores/training.svelte.js';

    let elapsed = $state(0);
    let intervalId = $state(null);

    $effect(() => {
        if (training.active) {
            elapsed = 0;
            intervalId = setInterval(() => {
                elapsed = ((Date.now() - training.startTime) / 1000).toFixed(1);
            }, 100);
        } else {
            if (intervalId) {
                clearInterval(intervalId);
                intervalId = null;
            }
            elapsed = 0;
        }

        return () => {
            if (intervalId) {
                clearInterval(intervalId);
                intervalId = null;
            }
        };
    });
</script>

{#if training.active}
    <div class="backdrop">
        <div class="spinner-container">
            <div class="ring"></div>

            {#if training.text}
                <p class="text">{training.text}</p>
            {/if}

            {#if training.sub}
                <p class="sub">{training.sub}</p>
            {/if}

            <p class="elapsed">{elapsed}s</p>
        </div>
    </div>
{/if}

<style>
    .backdrop {
        position: fixed;
        inset: 0;
        z-index: 9000;
        display: flex;
        align-items: center;
        justify-content: center;
        background: rgba(0, 0, 0, 0.6);
        backdrop-filter: blur(6px);
        -webkit-backdrop-filter: blur(6px);
        animation: fadeIn 0.2s ease forwards;
    }

    .spinner-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 1rem;
        animation: scaleIn 0.25s cubic-bezier(0.16, 1, 0.3, 1) forwards;
    }

    .ring {
        width: 56px;
        height: 56px;
        border: 3px solid var(--bg-tertiary, #252525);
        border-top-color: var(--success, #22c55e);
        border-radius: 50%;
        animation: trainSpin 0.8s linear infinite;
    }

    .text {
        font-size: 1rem;
        font-weight: 600;
        color: var(--text-primary, #ffffff);
        text-align: center;
    }

    .sub {
        font-size: 0.8125rem;
        color: var(--text-secondary, #a1a1aa);
        text-align: center;
        margin-top: -0.5rem;
    }

    .elapsed {
        font-size: 0.75rem;
        font-family: 'SF Mono', 'Fira Code', monospace;
        color: var(--text-muted, #71717a);
        text-align: center;
    }

    @keyframes fadeIn {
        from { opacity: 0; }
        to { opacity: 1; }
    }

    @keyframes scaleIn {
        from {
            transform: scale(0.9);
            opacity: 0;
        }
        to {
            transform: scale(1);
            opacity: 1;
        }
    }

    @keyframes trainSpin {
        to { transform: rotate(360deg); }
    }
</style>
