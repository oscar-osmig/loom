<script>
    import { chat } from '../stores/chat.svelte.js';
</script>

{#if chat.isTyping}
    <div class="typing-indicator">
        <span></span>
        <span></span>
        <span></span>
    </div>
{/if}

<style>
    .typing-indicator {
        display: flex;
        gap: 4px;
        padding: 1rem 1.25rem;
        background: var(--assistant-msg);
        border: 1px solid var(--border);
        border-radius: 16px;
        border-bottom-left-radius: 4px;
        align-self: flex-start;
    }

    .typing-indicator span {
        width: 8px;
        height: 8px;
        background: var(--accent);
        border-radius: 50%;
        animation: pulse 1.4s infinite ease-in-out;
    }

    .typing-indicator span:nth-child(1) { animation-delay: 0s; }
    .typing-indicator span:nth-child(2) { animation-delay: 0.2s; }
    .typing-indicator span:nth-child(3) { animation-delay: 0.4s; }

    @keyframes pulse {
        0%, 80%, 100% { opacity: 0.4; transform: scale(1); }
        40% { opacity: 1; transform: scale(1.1); }
    }
</style>
