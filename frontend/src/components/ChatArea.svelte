<script>
    import { chat, clearMessages } from '../stores/chat.svelte.js';
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

            <div class="messages" bind:this={messagesContainer}>
                {#if chat.messages.length === 0}
                    <WelcomeBox />
                {/if}

                {#each chat.messages as msg (msg.id)}
                    <MessageBubble content={msg.content} type={msg.type} meta={msg.meta} />
                {/each}

                <TypingIndicator />
            </div>
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
</style>
