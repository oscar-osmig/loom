<script>
    import { chat, clearMessages, formatConversation } from '../stores/chat.svelte.js';
    import { isAuthenticated } from '../stores/auth.svelte.js';
    import { ui } from '../stores/ui.svelte.js';
    import { fileStore } from '../stores/files.svelte.js';
    import MessageBubble from './MessageBubble.svelte';
    import WelcomeBox from './WelcomeBox.svelte';
    import AboutPage from './AboutPage.svelte';
    import SettingsPage from './SettingsPage.svelte';
    import FileViewer from './FileViewer.svelte';
    import FileSidebar from './FileSidebar.svelte';
    import TypingIndicator from './TypingIndicator.svelte';

    let messagesContainer = $state(null);

    function scrollToBottom() {
        if (messagesContainer) {
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }
    }

    $effect(() => {
        chat.messages.length;
        chat.isTyping;
        setTimeout(scrollToBottom, 0);
    });

    function handleClear() {
        clearMessages();
    }

    let copyToast = $state(false);

    async function handleContextMenu(e) {
        // Only intercept right-click on the messages area (not on about/settings/file pages)
        if (!messagesContainer || !messagesContainer.contains(e.target)) return;
        if (chat.messages.length === 0) return;

        // If user has selected text, let native copy work
        const selection = window.getSelection();
        if (selection && selection.toString().trim().length > 0) return;

        e.preventDefault();
        const text = formatConversation();
        try {
            await navigator.clipboard.writeText(text);
            copyToast = true;
            setTimeout(() => { copyToast = false; }, 2000);
        } catch {}
    }
</script>

<div class="chat-area">
    <div class="chat-main">
        {#if ui.aboutOpen}
            <AboutPage />
        {:else if ui.settingsOpen}
            <SettingsPage />
        {:else if fileStore.activeFile}
            <FileViewer />
        {:else}
            <button class="clear-chat-btn" onclick={handleClear} title="Clear chat">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <polyline points="3 6 5 6 21 6"/>
                    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                </svg>
            </button>

            <!-- svelte-ignore a11y_no_static_element_interactions -->
            <div class="messages" bind:this={messagesContainer} oncontextmenu={handleContextMenu}>
                {#if chat.messages.length === 0}
                    <WelcomeBox />
                {/if}

                {#each chat.messages as msg (msg.id)}
                    <MessageBubble content={msg.content} type={msg.type} meta={msg.meta} />
                {/each}

                <TypingIndicator />
            </div>

            {#if copyToast}
                <div class="copy-toast">Conversation copied!</div>
            {/if}
        {/if}
    </div>

    {#if isAuthenticated() && fileStore.items.length > 0 && !ui.aboutOpen && !ui.settingsOpen}
        <FileSidebar />
    {/if}
</div>

<style>
    .chat-area {
        flex: 1;
        display: flex;
        flex-direction: row;
        overflow: hidden;
        position: relative;
    }

    .chat-main {
        flex: 1;
        display: flex;
        flex-direction: column;
        overflow: hidden;
        position: relative;
        min-width: 0;
    }

    .clear-chat-btn {
        position: absolute;
        top: 0.5rem;
        right: 0.25rem;
        z-index: 5;
        background: var(--bg-secondary);
        border: 1px solid var(--border);
        color: var(--text-muted);
        cursor: pointer;
        padding: 0.4rem;
        border-radius: 8px;
        transition: all 0.2s;
        display: flex;
        align-items: center;
    }

    .clear-chat-btn:hover {
        color: var(--error);
        border-color: var(--error);
        background: rgba(239, 68, 68, 0.1);
    }

    .messages {
        flex: 1;
        overflow-y: auto;
        padding: 1.5rem 0;
        display: flex;
        flex-direction: column;
        gap: 1rem;
        position: relative;
    }

    .messages::-webkit-scrollbar { width: 6px; }
    .messages::-webkit-scrollbar-track { background: transparent; }
    .messages::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
    .messages::-webkit-scrollbar-thumb:hover { background: var(--text-muted); }

    .copy-toast {
        position: absolute;
        bottom: 1rem;
        left: 50%;
        transform: translateX(-50%);
        background: var(--accent);
        color: white;
        padding: 0.5rem 1.25rem;
        border-radius: 10px;
        font-size: 0.8125rem;
        font-weight: 500;
        z-index: 10;
        pointer-events: none;
        animation: toastIn 0.2s ease, toastOut 0.3s ease 1.7s forwards;
    }

    @keyframes toastIn {
        from { opacity: 0; transform: translateX(-50%) translateY(8px); }
        to { opacity: 1; transform: translateX(-50%) translateY(0); }
    }
    @keyframes toastOut {
        from { opacity: 1; }
        to { opacity: 0; }
    }
</style>
