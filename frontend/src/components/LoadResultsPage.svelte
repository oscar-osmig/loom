<script>
    import { ui, closeLoadResults } from '../stores/ui.svelte.js';

    const data = $derived(ui.loadResultsData);
    const files = $derived(data?.files || []);
    const totalLoaded = $derived(data?.total_loaded || 0);
    const totalFiles = $derived(data?.total_files || 0);
    const maxCount = $derived(Math.max(1, ...files.map(f => f.count)));
</script>

<div class="load-page">
    <button class="close-btn" onclick={closeLoadResults} aria-label="Close">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
        </svg>
    </button>

    <div class="load-header">
        <div class="check-icon">
            <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
                <polyline points="22 4 12 14.01 9 11.01"/>
            </svg>
        </div>
        <h2>Training Complete</h2>
        <p class="subtitle">{totalFiles} files processed</p>
    </div>

    <div class="load-body">
        <!-- Summary stats -->
        <div class="summary-row">
            <div class="summary-card big">
                <span class="summary-num">{totalLoaded.toLocaleString()}</span>
                <span class="summary-label">total facts loaded</span>
            </div>
            <div class="summary-card">
                <span class="summary-num">{totalFiles}</span>
                <span class="summary-label">files</span>
            </div>
            <div class="summary-card">
                <span class="summary-num">{files.filter(f => f.ok).length}</span>
                <span class="summary-label">succeeded</span>
            </div>
            {#if files.some(f => !f.ok)}
                <div class="summary-card error">
                    <span class="summary-num">{files.filter(f => !f.ok).length}</span>
                    <span class="summary-label">failed</span>
                </div>
            {/if}
        </div>

        <!-- File breakdown chart -->
        <div class="chart-section">
            <h3>Per-file breakdown</h3>
            <div class="file-chart">
                {#each files as file}
                    <div class="chart-row" class:failed={!file.ok}>
                        <span class="chart-name" title={file.name}>
                            {file.name.replace('.json', '').replace('.txt', '').replace(/_/g, ' ')}
                        </span>
                        <div class="chart-bar-track">
                            <div
                                class="chart-bar-fill"
                                class:zero={file.count === 0}
                                style="width: {file.count > 0 ? Math.max(3, (file.count / maxCount) * 100) : 0}%"
                            ></div>
                        </div>
                        <span class="chart-count">
                            {#if file.ok}
                                {file.count}
                            {:else}
                                <span class="error-badge">error</span>
                            {/if}
                        </span>
                    </div>
                {/each}
            </div>
        </div>
    </div>
</div>

<style>
    .load-page {
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

    .load-header {
        text-align: center; margin-bottom: 2rem;
        display: flex; flex-direction: column; align-items: center; gap: 0.375rem;
    }
    .check-icon { color: var(--success); margin-bottom: 0.25rem; }
    .load-header h2 { font-size: 1.25rem; font-weight: 700; color: var(--text-primary); }
    .subtitle { font-size: 0.8125rem; color: var(--text-muted); }

    .load-body { max-width: 560px; margin: 0 auto; display: flex; flex-direction: column; gap: 1.75rem; }

    /* Summary cards */
    .summary-row { display: flex; gap: 0.625rem; }
    .summary-card {
        flex: 1; display: flex; flex-direction: column; align-items: center; gap: 0.125rem;
        padding: 0.875rem 0.5rem; background: var(--bg-secondary);
        border: 1px solid var(--border); border-radius: 10px; text-align: center;
    }
    .summary-card.big { flex: 1.5; border-color: rgba(34, 197, 94, 0.3); }
    .summary-card.error { border-color: rgba(239, 68, 68, 0.3); }
    .summary-num { font-size: 1.5rem; font-weight: 700; color: var(--accent-hover); font-variant-numeric: tabular-nums; }
    .summary-card.big .summary-num { color: var(--success); font-size: 1.75rem; }
    .summary-card.error .summary-num { color: var(--error); }
    .summary-label { font-size: 0.625rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; }

    /* Chart */
    .chart-section h3 { font-size: 0.875rem; font-weight: 600; color: var(--text-primary); margin-bottom: 0.75rem; }

    .file-chart { display: flex; flex-direction: column; gap: 0.375rem; }

    .chart-row {
        display: grid; grid-template-columns: 140px 1fr 40px;
        align-items: center; gap: 0.625rem;
        padding: 0.25rem 0;
    }
    .chart-row.failed { opacity: 0.5; }

    .chart-name {
        font-size: 0.75rem; color: var(--text-secondary);
        text-transform: capitalize; overflow: hidden;
        text-overflow: ellipsis; white-space: nowrap;
    }

    .chart-bar-track {
        height: 8px; background: var(--bg-tertiary);
        border-radius: 4px; overflow: hidden;
    }
    .chart-bar-fill {
        height: 100%; border-radius: 4px;
        background: linear-gradient(90deg, var(--accent), var(--success));
        transition: width 0.5s ease;
    }
    .chart-bar-fill.zero { background: var(--text-muted); opacity: 0.2; width: 100% !important; }

    .chart-count {
        font-size: 0.75rem; font-weight: 600; color: var(--text-muted);
        text-align: right; font-variant-numeric: tabular-nums;
    }

    .error-badge {
        font-size: 0.625rem; color: var(--error);
        background: rgba(239, 68, 68, 0.1); padding: 1px 6px;
        border-radius: 4px;
    }

    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(8px); }
        to { opacity: 1; transform: translateY(0); }
    }
</style>
