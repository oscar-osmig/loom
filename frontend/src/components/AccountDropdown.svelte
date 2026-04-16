<script>
    import {
        auth, isAuthenticated, isGuest, isGoogleUser, setUser, signOut, initGoogle
    } from '../stores/auth.svelte.js';
    import { setHeaderLocked, setSettingsOpen } from '../stores/ui.svelte.js';

    let dropdownOpen = $state(false);
    let wrapperEl = $state(null);
    let signInButtonEl = $state(null);
    let googleRendered = $state(false);

    function toggleDropdown() {
        dropdownOpen = !dropdownOpen;
    }

    function handleClickOutside(e) {
        if (wrapperEl && !wrapperEl.contains(e.target)) {
            dropdownOpen = false;
        }
    }

    function handleGoogleCredential(response) {
        try {
            const payload = JSON.parse(atob(response.credential.split('.')[1]));
            const name = payload.name || payload.given_name || 'User';
            const userEmail = payload.email || '';
            const userPicture = payload.picture || '';
            setUser(name, { email: userEmail, picture: userPicture, authMethod: 'google' });
            setHeaderLocked(false);
            dropdownOpen = false;
        } catch (err) {
            console.error('Failed to decode Google credential:', err);
        }
    }

    function handleSignOut() {
        signOut();
        setHeaderLocked(true);
        dropdownOpen = false;
        googleRendered = false;
    }

    function handleSettings() {
        dropdownOpen = false;
        setSettingsOpen(true);
    }

    function renderGoogleButton() {
        if (!signInButtonEl || !auth.googleClientId || googleRendered) return;
        if (typeof google === 'undefined' || !google.accounts) return;

        try {
            google.accounts.id.initialize({
                client_id: auth.googleClientId,
                callback: handleGoogleCredential
            });
            google.accounts.id.renderButton(signInButtonEl, {
                theme: 'filled_black',
                size: 'medium',
                shape: 'rectangular',
                text: 'signin_with',
                width: 220
            });
            googleRendered = true;
        } catch (err) {
            console.error('Failed to render Google sign-in button:', err);
        }
    }

    $effect(() => { initGoogle(); });

    $effect(() => {
        if (dropdownOpen && !isAuthenticated() && auth.googleClientId && signInButtonEl) {
            setTimeout(renderGoogleButton, 50);
        }
    });

    const initial = $derived(auth.user ? auth.user.charAt(0).toUpperCase() : '');
</script>

<svelte:window onclick={handleClickOutside} />

<div class="account-wrapper" bind:this={wrapperEl}>
    <button class="account-icon" onclick={toggleDropdown} title="Account" aria-label="Account menu">
        {#if auth.picture}
            <img src={auth.picture} alt={auth.user} referrerpolicy="no-referrer" />
        {:else if auth.user}
            <span class="account-initial">{initial}</span>
        {:else}
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
                <circle cx="12" cy="7" r="4"/>
            </svg>
        {/if}
    </button>

    {#if dropdownOpen}
        <div class="account-dropdown">
            {#if isAuthenticated()}
                <div class="account-dropdown-header">
                    <div class="name">{auth.user}</div>
                    {#if auth.email}
                        <div class="email">{auth.email}</div>
                    {/if}
                    {#if isGuest()}
                        <div class="auth-badge guest">guest</div>
                    {/if}
                </div>

                <!-- Settings (Google users only) -->
                {#if isGoogleUser()}
                    <button class="account-dropdown-item" onclick={handleSettings}>
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <circle cx="12" cy="12" r="3"/>
                            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
                        </svg>
                        Settings
                    </button>
                {/if}

                <button class="account-dropdown-item danger" onclick={handleSignOut}>
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
                        <polyline points="16 17 21 12 16 7"/>
                        <line x1="21" y1="12" x2="9" y2="12"/>
                    </svg>
                    Sign out
                </button>
            {:else}
                <div class="google-signin-container">
                    <div id="googleSignInButton" bind:this={signInButtonEl}></div>
                </div>
            {/if}
        </div>
    {/if}
</div>

<style>
    .account-wrapper { position: relative; }
    .account-icon {
        width: 36px; height: 36px; border-radius: 50%;
        background: var(--bg-tertiary); border: 1px solid var(--border);
        color: var(--text-secondary); cursor: pointer;
        display: flex; align-items: center; justify-content: center;
        overflow: hidden; transition: all 0.2s; padding: 0;
    }
    .account-icon:hover { border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-glow); }
    .account-icon img { width: 100%; height: 100%; object-fit: cover; }
    .account-initial { font-size: 0.875rem; font-weight: 600; color: var(--text-primary); text-transform: uppercase; }

    .account-dropdown {
        position: absolute; top: calc(100% + 8px); right: 0;
        background: var(--bg-secondary); border: 1px solid var(--border);
        border-radius: 12px; box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
        z-index: 100; min-width: 240px; overflow: hidden;
        animation: dropdownIn 0.15s ease;
    }
    @keyframes dropdownIn { from { opacity: 0; transform: translateY(-4px); } to { opacity: 1; transform: translateY(0); } }

    .account-dropdown-header { padding: 0.75rem 1rem; border-bottom: 1px solid var(--border); }
    .account-dropdown-header .name { font-size: 0.9375rem; font-weight: 600; color: var(--text-primary); }
    .account-dropdown-header .email { font-size: 0.8125rem; color: var(--text-muted); margin-top: 0.125rem; }

    .auth-badge {
        display: inline-block; margin-top: 0.375rem;
        font-size: 0.625rem; font-weight: 600; text-transform: uppercase;
        letter-spacing: 0.5px; padding: 2px 8px; border-radius: 6px;
    }
    .auth-badge.guest { background: rgba(251, 191, 36, 0.12); color: #fbbf24; }

    .account-dropdown-item {
        display: flex; align-items: center; gap: 0.5rem; width: 100%;
        padding: 0.625rem 1rem; background: none; border: none;
        color: var(--text-secondary); font-size: 0.875rem; font-family: inherit;
        cursor: pointer; transition: all 0.15s;
    }
    .account-dropdown-item:hover { background: var(--bg-tertiary); color: var(--text-primary); }
    .account-dropdown-item.danger:hover { color: var(--error); background: rgba(239, 68, 68, 0.1); }
    .account-dropdown-item svg { flex-shrink: 0; }

    .google-signin-container { padding: 0.75rem 1rem; display: flex; justify-content: center; }
</style>
