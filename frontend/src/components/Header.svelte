<script>
    import { auth } from '../stores/auth.svelte.js';
    import { addMessage, conversationId } from '../stores/chat.svelte.js';
    import { ui, showInfoPanel, setVizOpen, setTrainInfoOpen, setAboutOpen, setLeaderboardOpen } from '../stores/ui.svelte.js';
    import { showSpinner, hideSpinner } from '../stores/training.svelte.js';
    import { showToast } from '../stores/toast.svelte.js';
    import { addFile } from '../stores/files.svelte.js';
    import { sendChat, uploadTrainingBatch } from '../lib/api.js';
    import AccountDropdown from './AccountDropdown.svelte';

    let fileInput = $state(null);

    async function handleStats() {
        if (ui.headerLocked) return;
        try {
            const data = await sendChat('/stats', auth.user, auth.email, conversationId);
            if (data.error) {
                addMessage(data.error, 'error');
            } else {
                showInfoPanel('Stats', data.response);
            }
        } catch {
            addMessage('Failed to fetch stats.', 'error');
        }
    }

    function handleTrain() {
        if (ui.headerLocked) return;
        fileInput?.click();
    }

    async function handleFileSelect(e) {
        const files = e.target.files;
        if (!files || files.length === 0) return;

        if (files.length > 50) {
            showToast('warning', 'Too many files', 'Maximum 50 files per upload.');
            fileInput.value = '';
            return;
        }

        showSpinner('Uploading training files...', `${files.length} file${files.length > 1 ? 's' : ''}`);

        // Save file contents to browser storage
        for (const file of files) {
            try {
                const text = await file.text();
                addFile(file.name, text);
            } catch {}
        }

        try {
            const data = await uploadTrainingBatch(files, auth.user);
            hideSpinner();

            if (data.error) {
                showToast('error', 'Upload failed', data.error);
            } else {
                const msg = `Loaded ${data.total_loaded || 0} facts from ${data.files_processed || 0} file(s).`;
                showToast('success', 'Training complete', msg);
                addMessage(msg, 'info');
            }
        } catch {
            hideSpinner();
            showToast('error', 'Upload failed', 'Connection error during upload.');
        }

        fileInput.value = '';
    }

    function handleVisualize() {
        if (ui.headerLocked) return;
        setVizOpen(true);
    }

    function handleTrainInfo(e) {
        e.stopPropagation();
        setTrainInfoOpen(true);
    }

    function handleAbout() {
        setAboutOpen(!ui.aboutOpen);
    }
</script>

<header class="header">
    <div class="header-left">
        <button class="logo" onclick={handleAbout} title="About Loom">
            <div class="logo-icon">
                <img src="/loom.png" alt="Loom" width="40" height="40" />
            </div>
            <div class="logo-text">
                <h1>Loom</h1>
                <p>Knowledge Weaver</p>
            </div>
        </button>
    </div>

    <div class="header-actions" class:locked={ui.headerLocked}>
        <!-- Stats -->
        <button class="header-btn" onclick={handleStats} title="Stats" disabled={ui.headerLocked}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <line x1="18" y1="20" x2="18" y2="10"/>
                <line x1="12" y1="20" x2="12" y2="4"/>
                <line x1="6" y1="20" x2="6" y2="14"/>
            </svg>
            Stats
        </button>

        <!-- Train -->
        <div class="train-btn-wrapper">
            <button class="header-btn" onclick={handleTrain} title="Upload training files" disabled={ui.headerLocked}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                    <polyline points="17 8 12 3 7 8"/>
                    <line x1="12" y1="3" x2="12" y2="15"/>
                </svg>
                Train
            </button>
            <button class="train-info-btn" onclick={handleTrainInfo} title="Training formats" aria-label="Training info">
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                    <circle cx="12" cy="12" r="10"/>
                    <line x1="12" y1="16" x2="12" y2="12"/>
                    <line x1="12" y1="8" x2="12.01" y2="8"/>
                </svg>
            </button>
        </div>

        <!-- Visualize -->
        <button class="header-btn" onclick={handleVisualize} title="Knowledge graph" disabled={ui.headerLocked}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="6" cy="6" r="3"/>
                <circle cx="18" cy="18" r="3"/>
                <circle cx="18" cy="6" r="3"/>
                <line x1="8.5" y1="7.5" x2="15.5" y2="16.5"/>
                <line x1="15.5" y1="7.5" x2="8.5" y2="16.5"/>
            </svg>
            Visualize
        </button>

        <!-- Collaborators (always accessible) -->
        <div class="always-active">
            <button class="header-btn" class:active={ui.leaderboardOpen} onclick={() => setLeaderboardOpen(!ui.leaderboardOpen)} title="Collaborators">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
                    <circle cx="9" cy="7" r="4"/>
                    <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
                    <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
                </svg>
            </button>
        </div>

        <!-- About (always accessible) -->
        <div class="always-active">
            <button class="header-btn about-btn" class:active={ui.aboutOpen} onclick={handleAbout} title="About Loom">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <circle cx="12" cy="12" r="10"/>
                    <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/>
                    <line x1="12" y1="17" x2="12.01" y2="17"/>
                </svg>
            </button>
        </div>

        <!-- Account dropdown stays active even when locked -->
        <div class="account-wrapper-outer">
            <AccountDropdown />
        </div>
    </div>

    <!-- Hidden file input for training uploads -->
    <input
        type="file"
        accept=".json,.txt"
        multiple
        bind:this={fileInput}
        onchange={handleFileSelect}
        style="display: none;"
    />
</header>

<style>
    .header {
        background: var(--bg-secondary);
        border-bottom: 1px solid var(--border);
        padding: 1rem 1.5rem;
        display: flex;
        align-items: center;
        justify-content: space-between;
        flex-shrink: 0;
    }

    .header-left {
        display: flex;
        align-items: center;
        gap: 1rem;
    }

    .logo {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        background: none;
        border: none;
        color: inherit;
        cursor: pointer;
        padding: 0;
        text-align: left;
    }

    .logo:hover .logo-icon {
        opacity: 0.8;
    }

    .logo-icon {
        width: 40px;
        height: 40px;
        border-radius: 12px;
        overflow: hidden;
        display: flex;
        align-items: center;
        justify-content: center;
    }

    .logo-icon img {
        width: 100%;
        height: 100%;
        object-fit: cover;
    }

    .logo-text h1 {
        font-size: 1.25rem;
        font-weight: 700;
        letter-spacing: 0.5px;
    }

    .logo-text p {
        font-size: 0.75rem;
        color: var(--text-muted);
        margin-top: 2px;
    }

    .header-actions {
        display: flex;
        gap: 0.5rem;
        align-items: center;
    }

    .header-actions.locked :global(.header-btn) {
        opacity: 0.3;
        pointer-events: none;
    }

    .header-actions.locked :global(.train-info-btn) {
        opacity: 0.3;
        pointer-events: none;
    }

    .header-actions.locked .account-wrapper-outer,
    .header-actions.locked .always-active {
        opacity: 1;
        pointer-events: auto;
    }

    .header-btn {
        background: var(--bg-tertiary);
        border: 1px solid var(--border);
        color: var(--text-secondary);
        padding: 0.5rem 1rem;
        border-radius: 8px;
        font-size: 0.875rem;
        font-weight: 500;
        cursor: pointer;
        transition: all 0.2s;
        display: flex;
        align-items: center;
        gap: 0.5rem;
        font-family: inherit;
    }

    .header-btn:hover:not(:disabled) {
        background: var(--bg-primary);
        border-color: var(--accent);
        color: var(--text-primary);
        box-shadow: 0 0 12px var(--accent-glow);
    }

    .header-btn:disabled {
        cursor: not-allowed;
    }

    .train-btn-wrapper {
        position: relative;
    }

    .train-info-btn {
        position: absolute;
        top: -6px;
        right: -6px;
        background: var(--bg-tertiary);
        border: 1px solid var(--border);
        color: var(--text-muted);
        cursor: pointer;
        width: 18px;
        height: 18px;
        padding: 0;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: all 0.2s;
        z-index: 1;
    }

    .train-info-btn:hover {
        color: var(--accent);
        border-color: var(--accent);
        background: var(--bg-secondary);
    }

    .about-btn.active {
        background: var(--accent);
        color: white;
        border-color: var(--accent);
    }

    .account-wrapper-outer {
        margin-left: 0.25rem;
    }
</style>
