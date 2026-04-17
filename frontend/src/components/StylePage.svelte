<script>
    import { setStylePageOpen } from '../stores/ui.svelte.js';
    import { auth } from '../stores/auth.svelte.js';
    import { fetchStyle } from '../lib/api.js';

    let data = $state(null);
    let loading = $state(true);

    function close() {
        setStylePageOpen(false);
    }

    $effect(() => {
        loading = true;
        fetchStyle(auth.email).then(d => {
            data = d;
            loading = false;
        });
    });

    function feedbackBar(likes, dislikes) {
        const total = likes + dislikes;
        if (total === 0) return 0;
        return Math.round((likes / total) * 100);
    }
</script>

<div class="style-page">
    <button class="close-btn" onclick={close} aria-label="Close">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
        </svg>
    </button>

    <div class="style-header">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4 12.5-12.5z"/>
        </svg>
        <h2>Writing Style</h2>
        <p class="subtitle">How Loom has learned to write from your feedback</p>
    </div>

    {#if loading}
        <div class="loading">Loading style data...</div>
    {:else if data && data.error}
        <div class="error-msg">{data.error}</div>
    {:else if data}
        <div class="style-body">
            <!-- Stats grid -->
            <div class="stats-grid">
                <div class="stat-card">
                    <span class="stat-num">{data.stats?.templates_learned || 0}</span>
                    <span class="stat-lbl">Templates Learned</span>
                </div>
                <div class="stat-card accent">
                    <span class="stat-num">{data.stats?.openers_learned || 0}</span>
                    <span class="stat-lbl">Opener Patterns</span>
                </div>
                <div class="stat-card">
                    <span class="stat-num">{data.stats?.feedback_received || 0}</span>
                    <span class="stat-lbl">Responses Rated</span>
                </div>
            </div>

            <!-- Composer templates with feedback bars -->
            {#if data.patterns?.composer_templates?.length > 0}
                <section>
                    <h3>Response Templates</h3>
                    <p class="desc">Which phrasings users like and dislike</p>
                    <div class="template-list">
                        {#each data.patterns.composer_templates as p}
                            <div class="template-row">
                                <div class="template-info">
                                    <span class="template-name">{p.value.replace(/_/g, ' ')}</span>
                                    <span class="template-counts">
                                        <span class="like">+{p.likes}</span>
                                        <span class="dislike">-{p.dislikes}</span>
                                    </span>
                                </div>
                                <div class="bar-track">
                                    <div
                                        class="bar-fill"
                                        class:positive={feedbackBar(p.likes, p.dislikes) >= 50}
                                        class:negative={feedbackBar(p.likes, p.dislikes) < 50 && (p.likes + p.dislikes) > 0}
                                        class:neutral={p.likes + p.dislikes === 0}
                                        style="width: {p.likes + p.dislikes === 0 ? 50 : feedbackBar(p.likes, p.dislikes)}%"
                                    ></div>
                                </div>
                            </div>
                        {/each}
                    </div>
                </section>
            {/if}

            <!-- Learned openers -->
            {#if data.patterns?.openers?.length > 0}
                <section>
                    <h3>Opener Patterns</h3>
                    <p class="desc">How users start their sentences when teaching Loom</p>
                    <div class="opener-list">
                        {#each data.patterns.openers as p}
                            <div class="opener-chip">
                                <code>{p.value.replace(/_/g, ' ')}</code>
                                <span class="chip-count">{p.count}x</span>
                            </div>
                        {/each}
                    </div>
                </section>
            {/if}

            <!-- Learned sentence templates -->
            {#if data.patterns?.templates?.length > 0}
                <section>
                    <h3>Sentence Templates</h3>
                    <p class="desc">Structural patterns extracted from user input</p>
                    <div class="sentence-templates">
                        {#each data.patterns.templates as p}
                            <div class="sent-tmpl">
                                <code>{p.value}</code>
                                <span class="tmpl-count">seen {p.count}x</span>
                            </div>
                        {/each}
                    </div>
                </section>
            {/if}

            <!-- Connectives -->
            {#if data.patterns?.connectives?.length > 0}
                <section>
                    <h3>Connective Patterns</h3>
                    <p class="desc">How users join ideas together</p>
                    <div class="opener-list">
                        {#each data.patterns.connectives as p}
                            <div class="opener-chip">
                                <code>{p.value.replace(/_/g, ' ')}</code>
                                <span class="chip-count">{p.count}x</span>
                            </div>
                        {/each}
                    </div>
                </section>
            {/if}

            {#if !data.patterns?.composer_templates?.length && !data.patterns?.openers?.length && !data.patterns?.templates?.length}
                <div class="empty-state">
                    <p>No style patterns learned yet.</p>
                    <p class="hint">Teach Loom facts and rate responses to help it develop a writing style.</p>
                </div>
            {/if}
        </div>
    {/if}
</div>

<style>
    .style-page {
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

    .style-header {
        text-align: center; margin-bottom: 2rem;
        display: flex; flex-direction: column; align-items: center; gap: 0.375rem;
        color: var(--text-muted);
    }
    .style-header h2 { font-size: 1.25rem; font-weight: 700; color: var(--text-primary); }
    .subtitle { font-size: 0.8125rem; color: var(--text-muted); }

    .style-body { max-width: 520px; margin: 0 auto; display: flex; flex-direction: column; gap: 2rem; }

    .loading, .error-msg { text-align: center; color: var(--text-muted); padding: 3rem; }
    .error-msg { color: var(--error); }

    /* Stats grid */
    .stats-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.75rem; }
    .stat-card {
        display: flex; flex-direction: column; align-items: center; gap: 0.25rem;
        padding: 1rem; background: var(--bg-secondary); border: 1px solid var(--border);
        border-radius: 12px; transition: border-color 0.2s;
    }
    .stat-card:hover { border-color: var(--accent); }
    .stat-card.accent { border-color: rgba(99, 102, 241, 0.3); }
    .stat-num { font-size: 1.75rem; font-weight: 700; color: var(--accent-hover); font-variant-numeric: tabular-nums; }
    .stat-lbl { font-size: 0.6875rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; text-align: center; }

    /* Sections */
    section h3 { font-size: 0.875rem; font-weight: 600; color: var(--text-primary); margin-bottom: 0.25rem; }
    .desc { font-size: 0.8125rem; color: var(--text-muted); margin-bottom: 0.875rem; }

    /* Template feedback bars */
    .template-list { display: flex; flex-direction: column; gap: 0.625rem; }
    .template-row { display: flex; flex-direction: column; gap: 0.375rem; }
    .template-info { display: flex; justify-content: space-between; align-items: center; }
    .template-name { font-size: 0.8125rem; color: var(--text-secondary); }
    .template-counts { display: flex; gap: 0.625rem; font-size: 0.75rem; }
    .like { color: var(--success); }
    .dislike { color: var(--error); }

    .bar-track { height: 6px; background: var(--bg-tertiary); border-radius: 3px; overflow: hidden; }
    .bar-fill { height: 100%; border-radius: 3px; transition: width 0.4s ease; min-width: 4px; }
    .bar-fill.positive { background: var(--success); }
    .bar-fill.negative { background: var(--error); }
    .bar-fill.neutral { background: var(--text-muted); opacity: 0.3; }

    /* Opener chips */
    .opener-list { display: flex; flex-wrap: wrap; gap: 0.5rem; }
    .opener-chip {
        display: inline-flex; align-items: center; gap: 0.375rem;
        padding: 0.375rem 0.75rem; background: var(--bg-secondary);
        border: 1px solid var(--border); border-radius: 20px;
        font-size: 0.8125rem;
    }
    .opener-chip code { color: var(--accent-hover); background: none; padding: 0; font-size: 0.8125rem; }
    .chip-count { font-size: 0.6875rem; color: var(--text-muted); }

    /* Sentence templates */
    .sentence-templates { display: flex; flex-direction: column; gap: 0.375rem; }
    .sent-tmpl {
        display: flex; justify-content: space-between; align-items: center;
        padding: 0.5rem 0.75rem; background: var(--bg-secondary);
        border-radius: 8px; font-size: 0.8125rem;
    }
    .sent-tmpl code { color: var(--text-secondary); background: none; padding: 0; font-size: 0.75rem; font-family: 'JetBrains Mono', monospace; }
    .tmpl-count { font-size: 0.6875rem; color: var(--text-muted); white-space: nowrap; }

    .empty-state { text-align: center; padding: 2rem; }
    .empty-state p { color: var(--text-muted); }
    .hint { font-size: 0.8125rem; margin-top: 0.5rem; }

    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(8px); }
        to { opacity: 1; transform: translateY(0); }
    }
</style>
