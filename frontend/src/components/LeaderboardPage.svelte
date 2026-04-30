<script>
    import { setLeaderboardOpen } from '../stores/ui.svelte.js';
    import { auth } from '../stores/auth.svelte.js';
    import { fetchCollaborators } from '../lib/api.js';

    let data = $state(null);
    let loading = $state(true);
    let activeTab = $state('neurons');

    function close() { setLeaderboardOpen(false); }

    $effect(() => {
        loading = true;
        fetchCollaborators(auth.user, auth.email).then(d => { data = d; loading = false; });
    });

    const tabs = [
        { id: 'neurons', label: 'Builders', icon: 'M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5' },
        { id: 'corrections', label: 'Correctors', icon: 'M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z' },
        { id: 'messages', label: 'Most Active', icon: 'M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z' },
    ];

    const activeList = $derived(() => {
        if (!data) return [];
        if (activeTab === 'neurons') return data.by_neurons || [];
        if (activeTab === 'corrections') return data.by_corrections || [];
        return data.by_messages || [];
    });

    const activeKey = $derived(() => {
        if (activeTab === 'neurons') return 'neurons';
        if (activeTab === 'corrections') return 'corrections';
        return 'messages';
    });

    function maxVal(list, key) {
        if (!list || list.length === 0) return 1;
        return Math.max(1, ...list.map(u => u[key] || 0));
    }

    function medal(i) {
        if (i === 0) return '🥇';
        if (i === 1) return '🥈';
        if (i === 2) return '🥉';
        return `${i + 1}`;
    }
</script>

<div class="lb-page">
    <button class="close-btn" onclick={close} aria-label="Close">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
        </svg>
    </button>

    <div class="lb-header">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/>
            <circle cx="9" cy="7" r="4"/>
            <path d="M23 21v-2a4 4 0 00-3-3.87"/>
            <path d="M16 3.13a4 4 0 010 7.75"/>
        </svg>
        <h2>Collaborators</h2>
        <p class="subtitle">{data?.total_collaborators || 0} contributors building Loom's knowledge</p>
    </div>

    {#if loading}
        <div class="loading">Loading...</div>
    {:else if data}
        <div class="lb-body">
            <!-- Tabs -->
            <div class="tab-row">
                {#each tabs as tab}
                    <button
                        class="tab-btn"
                        class:active={activeTab === tab.id}
                        onclick={() => { activeTab = tab.id; }}
                    >
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <path d={tab.icon}/>
                        </svg>
                        {tab.label}
                    </button>
                {/each}
            </div>

            <!-- Ranked list -->
            {#if activeList().length === 0}
                <div class="empty">No data yet. Start teaching Loom!</div>
            {:else}
                {@const list = activeList()}
                {@const key = activeKey()}
                {@const mx = maxVal(list, key)}
                <div class="rank-list">
                    {#each list as user, i}
                        <div class="rank-row" class:admin-row={user.is_admin}>
                            <span class="rank-pos">{medal(i)}</span>
                            <div class="rank-avatar" class:admin-avatar={user.is_admin}>
                                {user.user.charAt(0).toUpperCase()}
                            </div>
                            <div class="rank-info">
                                <span class="rank-name">
                                    {user.user}
                                    {#if user.is_admin}
                                        <span class="admin-badge">admin</span>
                                    {/if}
                                </span>
                                <div class="rank-bar-track">
                                    <div
                                        class="rank-bar-fill"
                                        style="width: {Math.max(4, (user[key] / mx) * 100)}%"
                                    ></div>
                                </div>
                            </div>
                            <span class="rank-count">
                                {user[key].toLocaleString()}
                                <span class="rank-unit">{key === 'neurons' ? 'facts' : key === 'corrections' ? 'fixes' : 'msgs'}</span>
                            </span>
                        </div>
                    {/each}
                </div>
            {/if}
        </div>
    {/if}
</div>

<style>
    .lb-page {
        flex: 1; overflow-y: auto; padding: 2rem 1.5rem;
        position: relative; animation: fadeIn 0.3s ease;
    }

    .close-btn {
        position: absolute; top: 1rem; right: 0.5rem;
        background: var(--bg-secondary); border: 1px solid var(--border);
        color: var(--text-muted); cursor: pointer; padding: 0.4rem;
        border-radius: 8px; transition: all 0.2s;
        display: flex; align-items: center; z-index: 1;
    }
    .close-btn:hover { color: var(--text-primary); border-color: var(--accent); }

    .lb-header {
        text-align: center; margin-bottom: 1.5rem;
        display: flex; flex-direction: column; align-items: center; gap: 0.25rem;
        color: var(--text-muted);
    }
    .lb-header h2 { font-size: 1.25rem; font-weight: 700; color: var(--text-primary); }
    .subtitle { font-size: 0.8125rem; color: var(--text-muted); }

    .lb-body { max-width: 480px; margin: 0 auto; }
    .loading, .empty { text-align: center; color: var(--text-muted); padding: 2rem; }

    /* Tabs */
    .tab-row {
        display: flex; gap: 0.375rem; margin-bottom: 1.25rem;
        background: var(--bg-secondary); border-radius: 10px; padding: 0.25rem;
    }
    .tab-btn {
        flex: 1; display: flex; align-items: center; justify-content: center; gap: 0.375rem;
        padding: 0.5rem; border-radius: 8px; border: none;
        background: transparent; color: var(--text-muted); font-size: 0.75rem;
        font-weight: 500; font-family: inherit; cursor: pointer; transition: all 0.2s;
    }
    .tab-btn:hover { color: var(--text-secondary); }
    .tab-btn.active {
        background: var(--bg-tertiary); color: var(--accent-hover);
        box-shadow: 0 1px 4px rgba(0,0,0,0.15);
    }
    .tab-btn svg { flex-shrink: 0; }

    /* Rank list */
    .rank-list { display: flex; flex-direction: column; gap: 0.5rem; }

    .rank-row {
        display: flex; align-items: center; gap: 0.75rem;
        padding: 0.625rem 0.75rem; background: var(--bg-secondary);
        border: 1px solid var(--border); border-radius: 10px;
        transition: border-color 0.2s;
    }
    .rank-row:first-child { border-color: rgba(255, 215, 0, 0.3); }
    .rank-row:nth-child(2) { border-color: rgba(192, 192, 192, 0.3); }
    .rank-row:nth-child(3) { border-color: rgba(205, 127, 50, 0.3); }

    .rank-pos {
        width: 28px; text-align: center; font-size: 0.875rem;
        font-weight: 600; color: var(--text-muted); flex-shrink: 0;
    }

    .rank-avatar {
        width: 32px; height: 32px; border-radius: 50%;
        background: var(--bg-tertiary); border: 1px solid var(--border);
        display: flex; align-items: center; justify-content: center;
        font-size: 0.8125rem; font-weight: 600; color: var(--text-primary);
        flex-shrink: 0;
    }

    .rank-info { flex: 1; min-width: 0; }
    .rank-name {
        font-size: 0.8125rem; font-weight: 600; color: var(--text-primary);
        display: block; margin-bottom: 0.25rem;
    }
    .rank-bar-track { height: 6px; background: var(--bg-tertiary); border-radius: 3px; overflow: hidden; }
    .rank-bar-fill {
        height: 100%; border-radius: 3px;
        background: linear-gradient(90deg, var(--accent), var(--accent-hover));
        transition: width 0.5s ease;
    }

    .rank-count {
        font-size: 0.875rem; font-weight: 700; color: var(--accent-hover);
        font-variant-numeric: tabular-nums; flex-shrink: 0; min-width: 50px; text-align: right;
        display: flex; flex-direction: column; align-items: flex-end; gap: 0;
    }
    .rank-unit {
        font-size: 0.5625rem; font-weight: 500; color: var(--text-muted);
        text-transform: uppercase; letter-spacing: 0.3px;
    }

    .admin-row { border-color: rgba(99, 102, 241, 0.25); }
    .admin-avatar { border-color: var(--accent); background: rgba(99, 102, 241, 0.15); }
    .admin-badge {
        font-size: 0.5625rem; font-weight: 600; text-transform: uppercase;
        letter-spacing: 0.5px; padding: 1px 6px; border-radius: 4px;
        background: rgba(99, 102, 241, 0.15); color: var(--accent-hover);
        margin-left: 0.375rem; vertical-align: middle;
    }

    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(8px); }
        to { opacity: 1; transform: translateY(0); }
    }
</style>
