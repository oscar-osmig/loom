<script>
    import { fileStore, getFile, updateFileContent, removeFile, deselectFile, setEditing } from '../stores/files.svelte.js';
    import { auth } from '../stores/auth.svelte.js';
    import { showToast } from '../stores/toast.svelte.js';
    import { showSpinner, hideSpinner } from '../stores/training.svelte.js';
    import { uploadTrainingBatch } from '../lib/api.js';

    let editContent = $state('');
    let retrainTimer = null;

    const file = $derived(getFile(fileStore.activeFile));

    function handleEdit() {
        if (!file) return;
        editContent = file.content;
        setEditing(true);
    }

    function handleExit() {
        if (fileStore.editing) {
            finishEditing();
        }
        deselectFile();
    }

    function handleDelete() {
        if (!file) return;
        const name = file.name;
        removeFile(name);
        showToast('success', 'File deleted', `${name} removed.`);
    }

    function handleInput(e) {
        editContent = e.target.value;
        // Debounce: retrain after 2s of no typing
        if (retrainTimer) clearTimeout(retrainTimer);
        retrainTimer = setTimeout(() => {
            saveAndRetrain();
        }, 2000);
    }

    function finishEditing() {
        if (retrainTimer) {
            clearTimeout(retrainTimer);
            retrainTimer = null;
        }
        if (file && editContent !== file.content) {
            saveAndRetrain();
        }
        setEditing(false);
    }

    async function saveAndRetrain() {
        if (!file) return;
        const name = fileStore.activeFile;
        updateFileContent(name, editContent);

        showSpinner('Retraining...', name);
        try {
            const blob = new Blob([editContent], { type: name.endsWith('.json') ? 'application/json' : 'text/plain' });
            const reFile = new File([blob], name);
            const result = await uploadTrainingBatch([reFile], auth.user);
            hideSpinner();

            if (result.error) {
                showToast('error', 'Retrain failed', result.error);
            } else {
                showToast('success', 'Retrained', `${result.total_loaded || 0} facts from ${name}.`);
            }
        } catch {
            hideSpinner();
            showToast('error', 'Retrain failed', 'Connection error.');
        }
    }

    function handleKeydown(e) {
        if (e.key === 'Escape') handleExit();
    }
</script>

<svelte:window onkeydown={handleKeydown} />

{#if file}
    <div class="file-viewer">
        <div class="viewer-toolbar">
            <div class="toolbar-left">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                    <polyline points="14 2 14 8 20 8"/>
                </svg>
                <span class="toolbar-filename">{file.name}</span>
            </div>
            <div class="toolbar-actions">
                {#if fileStore.editing}
                    <button class="toolbar-btn done" onclick={finishEditing}>
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                            <polyline points="20 6 9 17 4 12"/>
                        </svg>
                        Done
                    </button>
                {:else}
                    <button class="toolbar-btn" onclick={handleEdit}>
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                            <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                        </svg>
                        Edit
                    </button>
                {/if}
                <button class="toolbar-btn danger" onclick={handleDelete}>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <polyline points="3 6 5 6 21 6"/>
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                    </svg>
                    Delete
                </button>
                <button class="toolbar-btn" onclick={handleExit}>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                    </svg>
                    Exit
                </button>
            </div>
        </div>

        <div class="viewer-content">
            {#if fileStore.editing}
                <textarea
                    class="file-editor"
                    value={editContent}
                    oninput={handleInput}
                    spellcheck="false"
                ></textarea>
            {:else}
                <pre class="file-preview">{file.content}</pre>
            {/if}
        </div>
    </div>
{/if}

<style>
    .file-viewer {
        flex: 1;
        display: flex;
        flex-direction: column;
        overflow: hidden;
        animation: fadeIn 0.2s ease;
    }

    .viewer-toolbar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0.625rem 1rem;
        border-bottom: 1px solid var(--border);
        background: var(--bg-secondary);
        flex-shrink: 0;
        gap: 0.5rem;
    }

    .toolbar-left {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        color: var(--text-muted);
        min-width: 0;
    }
    .toolbar-left svg { flex-shrink: 0; }

    .toolbar-filename {
        font-size: 0.875rem;
        font-weight: 600;
        color: var(--text-primary);
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }

    .toolbar-actions {
        display: flex;
        gap: 0.375rem;
        flex-shrink: 0;
    }

    .toolbar-btn {
        display: flex;
        align-items: center;
        gap: 0.375rem;
        padding: 0.35rem 0.75rem;
        background: var(--bg-tertiary);
        border: 1px solid var(--border);
        border-radius: 8px;
        color: var(--text-secondary);
        font-size: 0.75rem;
        font-weight: 500;
        font-family: inherit;
        cursor: pointer;
        transition: all 0.15s;
    }
    .toolbar-btn:hover { background: var(--bg-primary); color: var(--text-primary); border-color: var(--accent); }
    .toolbar-btn.danger:hover { color: var(--error); border-color: var(--error); background: rgba(239, 68, 68, 0.08); }
    .toolbar-btn.done { background: var(--accent); color: white; border-color: var(--accent); }
    .toolbar-btn.done:hover { background: var(--accent-hover); }
    .toolbar-btn svg { flex-shrink: 0; }

    .viewer-content {
        flex: 1;
        overflow: hidden;
        display: flex;
    }

    .file-preview {
        flex: 1;
        overflow-y: auto;
        padding: 1rem;
        font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
        font-size: 0.8125rem;
        line-height: 1.7;
        color: var(--text-secondary);
        white-space: pre-wrap;
        word-break: break-word;
        margin: 0;
        scrollbar-width: none;
        -ms-overflow-style: none;
    }
    .file-preview::-webkit-scrollbar { display: none; }

    .file-editor {
        flex: 1;
        padding: 1rem;
        background: var(--bg-primary);
        border: none;
        color: var(--text-primary);
        font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
        font-size: 0.8125rem;
        line-height: 1.7;
        resize: none;
        outline: none;
        scrollbar-width: none;
        -ms-overflow-style: none;
    }
    .file-editor::-webkit-scrollbar { display: none; }

    @keyframes fadeIn {
        from { opacity: 0; }
        to { opacity: 1; }
    }
</style>
