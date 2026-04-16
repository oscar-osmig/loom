<script>
    import { uploadTrainingBatch } from '../lib/api.js';
    import { showSpinner, hideSpinner } from '../stores/training.svelte.js';
    import { showToast } from '../stores/toast.svelte.js';
    import { auth, isAuthenticated } from '../stores/auth.svelte.js';
    import { addFile } from '../stores/files.svelte.js';

    let dragging = $state(false);
    let dragCounter = $state(0);

    function hasFiles(e) {
        return e.dataTransfer && e.dataTransfer.types && e.dataTransfer.types.includes('Files');
    }

    function handleDragEnter(e) {
        e.preventDefault();
        if (!isAuthenticated()) return;
        if (!hasFiles(e)) return;
        dragCounter++;
        if (dragCounter === 1) {
            dragging = true;
        }
    }

    function handleDragLeave(e) {
        e.preventDefault();
        if (!dragging) return;
        dragCounter--;
        if (dragCounter <= 0) {
            dragCounter = 0;
            dragging = false;
        }
    }

    function handleDragOver(e) {
        if (!hasFiles(e)) return;
        e.preventDefault();
        e.dataTransfer.dropEffect = 'copy';
    }

    async function handleDrop(e) {
        e.preventDefault();
        dragCounter = 0;
        dragging = false;

        if (!isAuthenticated()) return;

        const allFiles = Array.from(e.dataTransfer.files);
        const validFiles = allFiles.filter(f => {
            const name = f.name.toLowerCase();
            return name.endsWith('.json') || name.endsWith('.txt');
        });

        if (validFiles.length === 0) {
            showToast('error', 'Invalid files', 'Only .json and .txt files are supported.');
            return;
        }

        // Save to browser storage
        for (const file of validFiles) {
            try {
                const text = await file.text();
                addFile(file.name, text);
            } catch {}
        }

        const names = validFiles.map(f => f.name).join(', ');
        showSpinner('Training Loom...', `Processing ${validFiles.length} file${validFiles.length > 1 ? 's' : ''}: ${names}`);

        const result = await uploadTrainingBatch(validFiles, auth.user);

        hideSpinner();

        if (result.error) {
            showToast('error', 'Training failed', result.error);
        } else {
            const loaded = result.total_loaded ?? 0;
            const processed = result.files_processed ?? validFiles.length;
            showToast('success', 'Training complete', `${loaded} facts loaded from ${processed} file${processed > 1 ? 's' : ''}.`);
        }
    }

    $effect(() => {
        document.addEventListener('dragenter', handleDragEnter);
        document.addEventListener('dragleave', handleDragLeave);
        document.addEventListener('dragover', handleDragOver);
        document.addEventListener('drop', handleDrop);

        return () => {
            document.removeEventListener('dragenter', handleDragEnter);
            document.removeEventListener('dragleave', handleDragLeave);
            document.removeEventListener('dragover', handleDragOver);
            document.removeEventListener('drop', handleDrop);
        };
    });
</script>

{#if dragging}
    <div class="drop-overlay">
        <div class="drop-content">
            <div class="drop-icon">
                <svg width="64" height="64" viewBox="0 0 64 64" fill="none">
                    <path d="M32 8v36m0 0l-12-12m12 12l12-12" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
                    <path d="M8 44v8a4 4 0 004 4h40a4 4 0 004-4v-8" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
            </div>
            <p class="drop-title">Drop to train Loom</p>
            <p class="drop-hint">.json and .txt files</p>
        </div>
    </div>
{/if}

<style>
    .drop-overlay {
        position: fixed;
        inset: 0;
        z-index: 9500;
        display: flex;
        align-items: center;
        justify-content: center;
        background: rgba(0, 0, 0, 0.75);
        backdrop-filter: blur(8px);
        -webkit-backdrop-filter: blur(8px);
        animation: fadeIn 0.2s ease forwards;
    }

    .drop-content {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 1rem;
        padding: 3rem 4rem;
        border: 2px dashed var(--accent, #6366f1);
        border-radius: 16px;
        animation: borderPulse 1.5s ease-in-out infinite;
    }

    .drop-icon {
        color: var(--accent, #6366f1);
        animation: bobUp 1.2s ease-in-out infinite;
    }

    .drop-title {
        font-size: 1.5rem;
        font-weight: 700;
        color: var(--text-primary, #ffffff);
    }

    .drop-hint {
        font-size: 0.875rem;
        color: var(--text-muted, #71717a);
    }

    @keyframes fadeIn {
        from { opacity: 0; }
        to { opacity: 1; }
    }

    @keyframes borderPulse {
        0%, 100% {
            border-color: var(--accent, #6366f1);
            box-shadow: 0 0 0 0 rgba(99, 102, 241, 0);
        }
        50% {
            border-color: var(--accent-hover, #818cf8);
            box-shadow: 0 0 24px 4px rgba(99, 102, 241, 0.2);
        }
    }

    @keyframes bobUp {
        0%, 100% {
            transform: translateY(0);
        }
        50% {
            transform: translateY(-6px);
        }
    }
</style>
