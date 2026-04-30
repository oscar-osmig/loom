<script>
    import { fileStore, selectFile, closeFileList } from '../stores/files.svelte.js';

    function handleClick(name) {
        selectFile(name);
    }
</script>

{#if fileStore.items.length > 0}
    <div class="file-sidebar">
        <div class="sidebar-header">
            <div class="sidebar-title">Files</div>
            <button class="close-btn" onclick={closeFileList} title="Close file list">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                    <line x1="18" y1="6" x2="6" y2="18"/>
                    <line x1="6" y1="6" x2="18" y2="18"/>
                </svg>
            </button>
        </div>
        <div class="file-list">
            {#each fileStore.items as file (file.name)}
                <button
                    class="file-item"
                    class:active={fileStore.activeFile === file.name}
                    onclick={() => handleClick(file.name)}
                    title={file.name}
                >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                        <polyline points="14 2 14 8 20 8"/>
                    </svg>
                    <span class="file-name">{file.name}</span>
                </button>
            {/each}
        </div>
    </div>
{/if}

<style>
    .file-sidebar {
        position: absolute;
        top: 0;
        right: 0;
        width: 160px;
        max-height: 100%;
        z-index: 6;
        display: flex;
        flex-direction: column;
        overflow: hidden;
        background: var(--bg-secondary);
        border-left: 1px solid var(--border);
        border-bottom: 1px solid var(--border);
        border-bottom-left-radius: 10px;
    }

    .sidebar-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0.75rem 0.75rem 0.5rem;
    }

    .sidebar-title {
        font-size: 0.6875rem;
        font-weight: 600;
        color: var(--text-muted);
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    .close-btn {
        background: none;
        border: none;
        color: var(--text-muted);
        cursor: pointer;
        padding: 0.2rem;
        border-radius: 4px;
        display: flex;
        align-items: center;
        transition: all 0.15s;
    }

    .close-btn:hover {
        color: var(--text-primary);
        background: var(--bg-tertiary);
    }

    .file-list {
        flex: 1;
        overflow-y: auto;
        padding: 0 0.375rem 0.5rem;
        scrollbar-width: none;
        -ms-overflow-style: none;
    }
    .file-list::-webkit-scrollbar { display: none; }

    .file-item {
        display: flex;
        align-items: center;
        gap: 0.375rem;
        width: 100%;
        padding: 0.375rem 0.5rem;
        background: none;
        border: none;
        border-radius: 6px;
        color: var(--text-secondary);
        font-size: 0.75rem;
        font-family: inherit;
        cursor: pointer;
        transition: all 0.15s;
        text-align: left;
    }

    .file-item:hover {
        background: var(--bg-tertiary);
        color: var(--text-primary);
    }

    .file-item.active {
        background: rgba(99, 102, 241, 0.12);
        color: var(--accent-hover);
    }

    .file-item svg { flex-shrink: 0; opacity: 0.5; }

    .file-name {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        text-decoration: underline;
        text-decoration-color: var(--border);
        text-underline-offset: 2px;
    }

    .file-item:hover .file-name,
    .file-item.active .file-name {
        text-decoration-color: currentColor;
    }

    @media (max-width: 640px) {
        .file-sidebar { display: none; }
    }
</style>
