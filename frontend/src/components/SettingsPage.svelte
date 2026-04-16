<script>
    import { auth, isGoogleUser, setUser } from '../stores/auth.svelte.js';
    import { setSettingsOpen } from '../stores/ui.svelte.js';
    import { showToast } from '../stores/toast.svelte.js';
    import { checkNickname } from '../lib/api.js';

    let nickname = $state(auth.user || '');
    let error = $state('');
    let saving = $state(false);

    function close() {
        setSettingsOpen(false);
    }

    async function handleSave() {
        const name = nickname.trim();
        if (!name || name.length > 30) {
            error = 'Nickname must be 1-30 characters.';
            return;
        }
        if (name === auth.user) {
            close();
            return;
        }

        saving = true;
        error = '';
        try {
            const result = await checkNickname(name);
            if (!result.available) {
                error = 'That nickname is already taken. Try another.';
                saving = false;
                return;
            }
            setUser(name);
            showToast('success', 'Nickname updated', `You're now known as ${name}.`);
            close();
        } catch {
            error = 'Could not verify nickname. Try again.';
        }
        saving = false;
    }

    function handleKeydown(e) {
        if (e.key === 'Enter') handleSave();
    }
</script>

<div class="settings">
    <button class="close-btn" onclick={close} aria-label="Close settings">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
        </svg>
    </button>

    <div class="settings-header">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="3"/>
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
        </svg>
        <h2>Settings</h2>
    </div>

    <div class="settings-body">
        <section>
            <h3>Nickname</h3>
            <p class="hint">This is how you appear to Loom and other users.</p>
            <div class="field">
                <input
                    type="text"
                    bind:value={nickname}
                    onkeydown={handleKeydown}
                    placeholder="Your nickname"
                    maxlength="30"
                />
                <button class="save-btn" onclick={handleSave} disabled={saving}>
                    {saving ? 'Checking...' : 'Save'}
                </button>
            </div>
            {#if error}
                <p class="error">{error}</p>
            {/if}
        </section>

        <section>
            <h3>Account</h3>
            <div class="account-info">
                {#if auth.email}
                    <div class="info-row">
                        <span class="info-label">Email</span>
                        <span class="info-value">{auth.email}</span>
                    </div>
                {/if}
                <div class="info-row">
                    <span class="info-label">Type</span>
                    <span class="info-value">{isGoogleUser() ? 'Google account' : 'Guest'}</span>
                </div>
            </div>
        </section>
    </div>
</div>

<style>
    .settings {
        flex: 1;
        overflow-y: auto;
        padding: 2rem 1.5rem;
        position: relative;
        animation: fadeIn 0.3s ease;
    }

    .close-btn {
        position: absolute; top: 1rem; right: 0.5rem;
        background: var(--bg-secondary); border: 1px solid var(--border);
        color: var(--text-muted); cursor: pointer; padding: 0.4rem;
        border-radius: 8px; transition: all 0.2s;
        display: flex; align-items: center; z-index: 1;
    }
    .close-btn:hover { color: var(--text-primary); border-color: var(--accent); }

    .settings-header {
        text-align: center; margin-bottom: 2rem;
        display: flex; flex-direction: column; align-items: center; gap: 0.5rem;
        color: var(--text-muted);
    }
    .settings-header h2 { font-size: 1.25rem; font-weight: 700; color: var(--text-primary); }

    .settings-body {
        max-width: 440px; margin: 0 auto;
        display: flex; flex-direction: column; gap: 1.75rem;
    }

    section h3 {
        font-size: 0.875rem; font-weight: 600;
        color: var(--accent-hover); margin-bottom: 0.375rem;
        text-transform: uppercase; letter-spacing: 0.5px;
    }

    .hint {
        font-size: 0.8125rem; color: var(--text-muted);
        margin-bottom: 0.75rem; line-height: 1.5;
    }

    .field {
        display: flex; gap: 0.5rem;
    }

    .field input {
        flex: 1; padding: 0.625rem 0.875rem;
        background: var(--bg-secondary); border: 1px solid var(--border);
        border-radius: 10px; color: var(--text-primary);
        font-size: 0.875rem; font-family: inherit; outline: none;
        transition: border-color 0.2s;
    }
    .field input:focus { border-color: var(--accent); }

    .save-btn {
        padding: 0.625rem 1.25rem; border-radius: 10px; border: none;
        background: var(--accent); color: white;
        font-size: 0.875rem; font-weight: 500; font-family: inherit;
        cursor: pointer; transition: all 0.2s; white-space: nowrap;
    }
    .save-btn:hover { background: var(--accent-hover); }
    .save-btn:disabled { opacity: 0.5; cursor: not-allowed; }

    .error { font-size: 0.8125rem; color: var(--error); margin-top: 0.375rem; }

    .account-info {
        display: flex; flex-direction: column; gap: 0.5rem;
    }

    .info-row {
        display: flex; justify-content: space-between; align-items: center;
        padding: 0.5rem 0.75rem; background: var(--bg-secondary);
        border-radius: 8px;
    }
    .info-label { font-size: 0.8125rem; color: var(--text-muted); }
    .info-value { font-size: 0.8125rem; color: var(--text-secondary); }

    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(8px); }
        to { opacity: 1; transform: translateY(0); }
    }
</style>
