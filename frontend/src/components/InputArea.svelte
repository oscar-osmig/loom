<script>
    import { auth, isAuthenticated, setUser } from '../stores/auth.svelte.js';
    import { addMessage, setTyping, clearMessages, conversationId } from '../stores/chat.svelte.js';
    import { showInfoPanel, setHeaderLocked, setStylePageOpen, setVizOpen, setAboutOpen, showLoadResults, triggerGraphReset } from '../stores/ui.svelte.js';
    import { showSpinner, hideSpinner } from '../stores/training.svelte.js';
    import { showToast } from '../stores/toast.svelte.js';
    import { sendChat, uploadTrainingBatch } from '../lib/api.js';
    import { isValidName, escapeHtml } from '../lib/utils.js';

    let textarea = $state(null);
    let sending = $state(false);

    // Autocomplete state
    const COMMANDS = [
        'help', 'show', 'stats', 'about', 'style', 'clear',
        'visualize', 'viz', 'graph', 'activation', 'weights',
        'clusters', 'procedures',
        'train', 'load', 'load-all',
        'forget', 'forget-all',
    ];
    let suggestions = $state([]);
    let selectedIndex = $state(0);

    const placeholder = $derived(
        isAuthenticated() ? 'Type a message or /help for commands...' : 'Enter your name...'
    );

    function autoResize() {
        if (!textarea) return;
        textarea.style.height = 'auto';
        textarea.style.height = Math.min(textarea.scrollHeight, 200) + 'px';
    }

    function updateSuggestions() {
        if (!textarea) { suggestions = []; return; }
        const val = textarea.value;
        if (val.startsWith('/') && !val.includes(' ')) {
            const partial = val.slice(1).toLowerCase();
            suggestions = COMMANDS.filter(c => c.startsWith(partial) && c !== partial);
            selectedIndex = 0;
        } else {
            suggestions = [];
        }
    }

    function acceptSuggestion(cmd) {
        if (!textarea) return;
        textarea.value = '/' + cmd;
        suggestions = [];
        textarea.focus();
    }

    function handleKeydown(e) {
        if (suggestions.length > 0) {
            if (e.key === 'Tab') {
                e.preventDefault();
                acceptSuggestion(suggestions[selectedIndex]);
                return;
            }
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                selectedIndex = (selectedIndex + 1) % suggestions.length;
                return;
            }
            if (e.key === 'ArrowUp') {
                e.preventDefault();
                selectedIndex = (selectedIndex - 1 + suggestions.length) % suggestions.length;
                return;
            }
            if (e.key === 'Escape') {
                suggestions = [];
                return;
            }
        }
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    }

    function handleInput() {
        autoResize();
        updateSuggestions();
    }

    async function handleSend() {
        if (!textarea || sending) return;
        const text = textarea.value.trim();
        if (!text) return;

        // Name input flow
        if (!isAuthenticated()) {
            textarea.value = '';
            autoResize();

            if (isValidName(text)) {
                setUser(text, { authMethod: 'guest' });
                setHeaderLocked(false);
                addMessage(escapeHtml(text), 'user');
                addMessage(`Hello, <b>${escapeHtml(text)}</b>! I'm Loom. Teach me facts, ask questions, or type <b>/help</b>.`, 'assistant');
            } else {
                addMessage(escapeHtml(text), 'user');
                addMessage('Please enter a valid name (1-3 words, letters and numbers only).', 'error');
            }
            return;
        }

        const message = text;
        textarea.value = '';
        suggestions = [];
        autoResize();

        const msgLower = message.toLowerCase();
        const cmdMessage = msgLower.startsWith('/') ? msgLower.slice(1) : msgLower;

        // Handle /clear locally
        if (msgLower.startsWith('/') && cmdMessage === 'clear') {
            const { clearMessages } = await import('../stores/chat.svelte.js');
            clearMessages();
            return;
        }

        // Detect training operations (pasted JSON arrays)
        let isTraining = false;
        try {
            if (message.trim().startsWith('[')) {
                const parsed = JSON.parse(message.trim());
                if (Array.isArray(parsed)) {
                    isTraining = true;
                }
            }
        } catch {
            // not JSON, that's fine
        }

        if (!isTraining) {
            isTraining = (msgLower.startsWith('/') && cmdMessage.startsWith('load ')) ||
                         (msgLower.startsWith('/') && cmdMessage.startsWith('train '));
        }

        // Detect forget commands
        const isForget = msgLower.startsWith('/') &&
            (cmdMessage === 'forget-all' || cmdMessage === 'forget');

        // Add user message to chat
        addMessage(escapeHtml(message), 'user');

        if (isTraining) {
            showSpinner('Training Loom...');
        }

        // Show typing
        setTyping(true);
        sending = true;

        try {
            const data = await sendChat(message, auth.user, auth.email, conversationId);

            setTyping(false);
            sending = false;

            if (isTraining) {
                hideSpinner();
            }

            if (data.error) {
                addMessage(data.error, 'error');
                return;
            }

            const responseType = data.type || 'response';

            // Forget commands: clear chat, reset graph, show confirmation
            if (isForget && responseType === 'info') {
                clearMessages();
                addMessage(data.response, 'info');
                if (data.action === 'graph_reset') {
                    triggerGraphReset();
                }
                return;
            }

            // Route help and info to the info panel, style to style page
            if (responseType === 'help' || responseType === 'info') {
                const title = responseType === 'help' ? 'Help' : 'Info';
                showInfoPanel(title, data.response);
            } else if (responseType === 'style') {
                setStylePageOpen(true);
            } else if (responseType === 'visualize') {
                setVizOpen(true);
            } else if (responseType === 'about') {
                setAboutOpen(true);
            } else if (responseType === 'load_results') {
                showLoadResults(data.meta);
            } else {
                addMessage(data.response, responseType, data.meta);
            }
        } catch (err) {
            setTyping(false);
            sending = false;
            if (isTraining) hideSpinner();
            addMessage('Connection error. Please try again.', 'error');
        }
    }
</script>

<div class="input-area">
    <div class="input-wrapper">
        {#if suggestions.length > 0}
            <div class="autocomplete">
                {#each suggestions as cmd, i (cmd)}
                    <button
                        class="autocomplete-item"
                        class:selected={i === selectedIndex}
                        onmousedown={(e) => { e.preventDefault(); acceptSuggestion(cmd); }}
                        onmouseenter={() => selectedIndex = i}
                    >/{cmd}</button>
                {/each}
            </div>
        {/if}
        <textarea
            bind:this={textarea}
            {placeholder}
            oninput={handleInput}
            onkeydown={handleKeydown}
            rows="1"
            disabled={sending}
        ></textarea>
        <button class="send-btn" onclick={handleSend} disabled={sending} aria-label="Send message">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <line x1="22" y1="2" x2="11" y2="13"/>
                <polygon points="22 2 15 22 11 13 2 9 22 2"/>
            </svg>
        </button>
    </div>
</div>

<style>
    .input-area {
        padding: 1rem 0 1.5rem;
        flex-shrink: 0;
    }

    .input-wrapper {
        position: relative;
        background: var(--bg-secondary);
        border: 1px solid var(--border);
        border-radius: 16px;
        transition: border-color 0.2s, box-shadow 0.2s;
    }

    .input-wrapper:focus-within {
        border-color: var(--accent);
        box-shadow: 0 0 0 3px var(--accent-glow);
    }

    .input-wrapper textarea {
        width: 100%;
        background: transparent;
        border: none;
        color: var(--text-primary);
        font-size: 0.9375rem;
        font-family: inherit;
        resize: none;
        outline: none;
        min-height: 24px;
        max-height: 200px;
        line-height: 1.6;
        padding: 0.875rem 1rem;
        padding-right: 4rem;
        box-sizing: border-box;
        word-break: break-word;
        overflow-wrap: anywhere;
        overflow-y: auto;
        scrollbar-width: thin;
        scrollbar-color: rgba(255, 255, 255, 0.1) transparent;
    }

    .input-wrapper textarea::placeholder {
        color: var(--text-muted);
    }

    .input-wrapper textarea::-webkit-scrollbar {
        width: 6px;
    }

    .input-wrapper textarea::-webkit-scrollbar-track {
        background: transparent;
        margin: 8px 0;
    }

    .input-wrapper textarea::-webkit-scrollbar-thumb {
        background: rgba(255, 255, 255, 0.15);
        border-radius: 3px;
    }

    .input-wrapper textarea::-webkit-scrollbar-thumb:hover {
        background: rgba(255, 255, 255, 0.25);
    }

    .send-btn {
        position: absolute;
        right: 0.5rem;
        bottom: 0.5rem;
        background: var(--accent);
        color: white;
        border: none;
        border-radius: 10px;
        padding: 0.5rem 1rem;
        font-size: 0.875rem;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.2s;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }

    .send-btn:hover {
        background: var(--accent-hover);
    }

    .send-btn:active {
        transform: scale(0.98);
    }

    .send-btn:disabled {
        background: var(--bg-tertiary);
        color: var(--text-muted);
        cursor: not-allowed;
        transform: none;
    }

    .autocomplete {
        position: absolute;
        bottom: calc(100% + 0.375rem);
        left: 0;
        right: 0;
        background: var(--bg-secondary);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 0.375rem;
        display: flex;
        flex-wrap: wrap;
        gap: 0.25rem;
        z-index: 10;
    }

    .autocomplete-item {
        background: var(--bg-tertiary);
        border: none;
        color: var(--text-secondary);
        font-size: 0.8125rem;
        font-family: inherit;
        padding: 0.3rem 0.625rem;
        border-radius: 8px;
        cursor: pointer;
        transition: all 0.1s;
    }

    .autocomplete-item:hover,
    .autocomplete-item.selected {
        background: var(--accent);
        color: white;
    }
</style>
