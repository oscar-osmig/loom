<script>
    import { ui, setVizOpen } from '../../stores/ui.svelte.js';
    import { GraphEngine } from './engine/graph-engine.js';
    import { render } from './engine/graph-renderer.js';
    import { attachInteractions } from './engine/graph-interaction.js';
    import { fetchGraph } from '../../lib/api.js';

    // Canvas & engine
    let canvas = $state(null);
    let engine = $state(null);
    let ctx = $state(null);

    // Dimensions
    let width = $state(window.innerWidth);
    let height = $state(window.innerHeight);

    // State
    let loading = $state(false);
    let graphData = $state(null);
    let neuronCount = $state(0);
    let synapseCount = $state(0);
    let discoveryCount = $state(0);
    let isDiscovering = $state(false);

    // Search
    let searchQuery = $state('');
    let searchResults = $state([]);
    let searchOpen = $state(false);
    let searchInput = $state(null);

    // Detail panel (selected neuron)
    let detailNode = $state(null);

    // Context menu
    let contextMenu = $state(null); // { node, x, y }

    // Zoom display
    let zoomPercent = $state(100);

    // Internal refs
    let animFrameId = null;
    let cleanupInteractions = null;
    let refreshInterval = null;

    // Relation colors
    const RELATION_COLORS = {
        is: '#6ecfff', has: '#a78bfa', can: '#f9a8d4',
        causes: '#fbbf24', leads_to: '#fbbf24', part_of: '#34d399',
        looks_like: '#fb923c', lives_in: '#38bdf8', eats: '#f87171', needs: '#c084fc',
    };

    function getRelationColor(rel) {
        return RELATION_COLORS[rel.toLowerCase().replace(/\s+/g, '_')] || '#8b9dc3';
    }

    // ------------------------------------------------------------------ open/close

    $effect(() => {
        if (ui.vizOpen) openVisualizer();
        else closeVisualizer();
    });

    $effect(() => {
        return () => {
            cancelAnimationFrame(animFrameId);
            if (cleanupInteractions) cleanupInteractions();
            if (refreshInterval) clearInterval(refreshInterval);
        };
    });

    async function openVisualizer() {
        loading = true;
        detailNode = null;
        searchQuery = '';
        searchResults = [];
        searchOpen = false;

        const data = await fetchGraph();

        if (data.error) { loading = false; return; }

        graphData = data;
        neuronCount = (data.neurons || data.nodes || []).length;
        synapseCount = (data.synapses || data.edges || []).length;
        discoveryCount = (data.potential_edges || []).length;
        isDiscovering = discoveryCount > 0;

        await waitFrame();

        if (!canvas) { loading = false; return; }

        ctx = canvas.getContext('2d');
        engine = new GraphEngine();
        engine.isDiscovering = isDiscovering;
        engine.initGraph(data);
        resizeCanvas();
        engine.centerAndZoomToFit(width, height);

        cleanupInteractions = attachInteractions(canvas, engine, {
            onNodeSelect: handleNodeSelect,
            onNodeHover: handleNodeHover,
            onContextMenu: handleContextMenu,
        });

        loading = false;
        startAnimationLoop();
        refreshInterval = setInterval(refreshGraphData, 30000);
    }

    function closeVisualizer() {
        if (engine) engine.saveCachedLayout();
        cancelAnimationFrame(animFrameId);
        animFrameId = null;
        if (cleanupInteractions) { cleanupInteractions(); cleanupInteractions = null; }
        if (refreshInterval) { clearInterval(refreshInterval); refreshInterval = null; }
        detailNode = null;
        searchOpen = false;
    }

    // ------------------------------------------------------------------ animation

    function startAnimationLoop() {
        function frame() {
            if (!engine || !ctx || !ui.vizOpen) return;
            engine.tick();
            render(ctx, engine, width, height);
            zoomPercent = Math.round(engine.zoom * 100);
            animFrameId = requestAnimationFrame(frame);
        }
        animFrameId = requestAnimationFrame(frame);
    }

    // ------------------------------------------------------------------ resize

    function resizeCanvas() {
        if (!canvas) return;
        width = window.innerWidth;
        height = window.innerHeight;
        // Use at least 2x resolution for crisp rendering at all zoom levels
        const dpr = Math.max(window.devicePixelRatio || 1, 2);
        canvas.width = width * dpr;
        canvas.height = height * dpr;
        canvas.style.width = width + 'px';
        canvas.style.height = height + 'px';
        ctx = canvas.getContext('2d');
        ctx.scale(dpr, dpr);
    }

    function handleResize() {
        resizeCanvas();
        if (engine) engine.centerAndZoomToFit(width, height);
    }

    // ------------------------------------------------------------------ refresh

    async function refreshGraphData() {
        if (!ui.vizOpen || !engine) return;
        const data = await fetchGraph();
        if (data.error) return;
        graphData = data;
        neuronCount = (data.neurons || data.nodes || []).length;
        synapseCount = (data.synapses || data.edges || []).length;
        discoveryCount = (data.potential_edges || []).length;
        isDiscovering = discoveryCount > 0;
        engine.isDiscovering = isDiscovering;
        engine.refreshGraph(data);
    }

    // ------------------------------------------------------------------ interactions

    function handleNodeSelect(node) {
        if (!node) { detailNode = null; return; }
        detailNode = node;
    }

    function handleNodeHover(_node) {}

    function handleContextMenu(node, pos) {
        contextMenu = { node, x: pos.x, y: pos.y };
    }

    function closeContextMenu() {
        contextMenu = null;
    }

    function getRelationsById(nodeId) {
        if (!graphData) return [];
        const relations = [];
        const synapses = graphData.synapses || graphData.edges || [];
        for (const syn of synapses) {
            const srcId = typeof syn.source === 'string' ? syn.source : syn.source?.id;
            const tgtId = typeof syn.target === 'string' ? syn.target : syn.target?.id;
            if (srcId === nodeId) {
                relations.push({ direction: 'out', relation: syn.relation || syn.label || 'related', target: tgtId, weight: syn.weight || 1 });
            } else if (tgtId === nodeId) {
                relations.push({ direction: 'in', relation: syn.relation || syn.label || 'related', target: srcId, weight: syn.weight || 1 });
            }
        }
        return relations;
    }

    function findNodeById(nodeId) {
        if (!engine) return null;
        return engine.nodes.find(n => n.id === nodeId) || null;
    }

    function buildNodeTree(nodeId, visited, indent, maxDepth) {
        if (visited.has(nodeId) || indent > maxDepth) return '';
        visited.add(nodeId);

        const node = findNodeById(nodeId);
        const prefix = '  '.repeat(indent);
        let text = '';

        // Node header
        if (indent === 0) {
            text += `${node?.label || nodeId}\n`;
            text += `${'='.repeat((node?.label || nodeId).length)}\n`;
            if (node?.isSystem) text += `Type: system\n`;
            if (node?.isLonely) text += `Type: isolated\n`;
            if (node?.creators?.length) text += `Created by: ${node.creators.join(', ')}\n`;
            if (node?.correctors?.length) text += `Corrected by: ${node.correctors.join(', ')}\n`;
            text += '\n';
        }

        const rels = getRelationsById(nodeId);
        const grouped = groupRelations(rels);

        for (const [relType, items] of Object.entries(grouped)) {
            for (const rel of items) {
                const other = rel.direction === 'out' ? rel.target : rel.target;
                const arrow = rel.direction === 'out'
                    ? `${prefix}—[${relType}]→ ${other}`
                    : `${prefix}${other} —[${relType}]→ this`;
                text += arrow;
                if (rel.weight > 1) text += ` (weight: ${rel.weight.toFixed(1)})`;
                text += '\n';

                // Recurse into connected node
                const childText = buildNodeTree(other, visited, indent + 1, maxDepth);
                if (childText) text += childText;
            }
        }

        return text;
    }

    function copyNeuronData() {
        if (!contextMenu) return;
        const node = contextMenu.node;
        const visited = new Set();
        const text = buildNodeTree(node.id, visited, 0, 3);
        navigator.clipboard.writeText(text.trim());
        contextMenu = null;
    }

    function closeDetail() {
        detailNode = null;
        if (engine) engine.selectedNode = null;
    }

    // ------------------------------------------------------------------ search

    function handleSearchInput(e) {
        searchQuery = e.target.value;
        if (!searchQuery.trim() || !engine) {
            searchResults = [];
            searchOpen = false;
            return;
        }
        const q = searchQuery.toLowerCase();
        searchResults = engine.nodes.filter(n => n.label.toLowerCase().includes(q)).slice(0, 8);
        searchOpen = searchResults.length > 0;
    }

    function selectSearchResult(node) {
        searchQuery = '';
        searchResults = [];
        searchOpen = false;
        if (!engine) return;
        const screen = engine.worldToScreen(node.x, node.y);
        engine.panX += width / 2 - screen.x;
        engine.panY += height / 2 - screen.y;
        engine.selectedNode = node;
        handleNodeSelect(node);
    }

    function handleSearchKeydown(e) {
        if (e.key === 'Escape') {
            searchQuery = '';
            searchResults = [];
            searchOpen = false;
            searchInput?.blur();
        }
    }

    function handleSearchBlur() {
        setTimeout(() => { searchOpen = false; }, 200);
    }

    // ------------------------------------------------------------------ keyboard

    function handleKeydown(e) {
        if (!ui.vizOpen) return;
        if (e.key === 'Escape') {
            if (contextMenu) closeContextMenu();
            else if (detailNode) closeDetail();
            else if (searchOpen) { searchQuery = ''; searchResults = []; searchOpen = false; }
            else setVizOpen(false);
        }
    }

    // ------------------------------------------------------------------ helpers

    function getNodeRelations(node) {
        if (!graphData || !node) return [];
        const relations = [];
        const synapses = graphData.synapses || graphData.edges || [];
        for (const syn of synapses) {
            const srcId = typeof syn.source === 'string' ? syn.source : syn.source?.id;
            const tgtId = typeof syn.target === 'string' ? syn.target : syn.target?.id;
            if (srcId === node.id) {
                relations.push({ direction: 'out', relation: syn.relation || syn.label || 'related', target: tgtId, weight: syn.weight || 1 });
            } else if (tgtId === node.id) {
                relations.push({ direction: 'in', relation: syn.relation || syn.label || 'related', target: srcId, weight: syn.weight || 1 });
            }
        }
        return relations;
    }

    function groupRelations(relations) {
        const groups = {};
        for (const rel of relations) {
            if (!groups[rel.relation]) groups[rel.relation] = [];
            groups[rel.relation].push(rel);
        }
        return groups;
    }

    function waitFrame() {
        return new Promise(resolve => requestAnimationFrame(resolve));
    }
</script>

<svelte:window onkeydown={handleKeydown} onresize={handleResize} />

{#if ui.vizOpen}
    <div class="viz-overlay" role="dialog" aria-label="Neural graph visualizer">
        <canvas class="viz-canvas" bind:this={canvas}></canvas>

        <!-- Header -->
        <div class="viz-header">
            <div class="viz-title">
                <span class="viz-title-dot"></span>
                Neural Map
            </div>
            <div class="viz-search-wrapper">
                <div class="viz-search-icon">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
                    </svg>
                </div>
                <input class="viz-search" type="text" placeholder="Search neurons..." value={searchQuery}
                    oninput={handleSearchInput} onkeydown={handleSearchKeydown}
                    onblur={handleSearchBlur} bind:this={searchInput} />
                {#if searchOpen && searchResults.length > 0}
                    <div class="viz-search-results">
                        {#each searchResults as result}
                            <button class="viz-search-result" onmousedown={() => selectSearchResult(result)}>
                                <span class="result-dot"></span>
                                {result.label}
                                {#if result.connections > 0}
                                    <span class="result-count">{result.connections}</span>
                                {/if}
                            </button>
                        {/each}
                    </div>
                {/if}
            </div>
            <button class="viz-close" onclick={() => setVizOpen(false)} aria-label="Close">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M18 6L6 18M6 6l12 12"/>
                </svg>
            </button>
        </div>

        <!-- Top-right: Stats panel -->
        <div class="viz-panel panel-top-right">
            <div class="panel-row">
                <span class="panel-value">{neuronCount}</span>
                <span class="panel-label">neurons</span>
            </div>
            <div class="panel-divider"></div>
            <div class="panel-row">
                <span class="panel-value">{synapseCount}</span>
                <span class="panel-label">synapses</span>
            </div>
            {#if isDiscovering}
                <div class="panel-divider"></div>
                <div class="panel-row discovery">
                    <span class="discovery-dot"></span>
                    <span class="panel-label">{discoveryCount} exploring</span>
                </div>
            {/if}
        </div>

        <!-- Bottom-left: Legend panel -->
        <div class="viz-panel panel-bottom-left">
            <div class="legend-item">
                <span class="legend-neuron"></span> Neuron
            </div>
            <div class="legend-item">
                <span class="legend-synapse"></span> Synapse
            </div>
            <div class="legend-item">
                <span class="legend-dendrite"></span> Dendrite
            </div>
            <div class="legend-item">
                <span class="legend-exploring"></span> Exploring
            </div>
        </div>

        <!-- Right: Neuron detail panel -->
        {#if detailNode}
            <div class="viz-panel panel-detail">
                <div class="detail-header">
                    <h3>{detailNode.label}</h3>
                    <button class="detail-close" onclick={closeDetail} aria-label="Close detail">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                            <path d="M18 6L6 18M6 6l12 12"/>
                        </svg>
                    </button>
                </div>

                <div class="detail-meta">
                    <span>{detailNode.connections} connection{detailNode.connections !== 1 ? 's' : ''}</span>
                    {#if detailNode.isSystem}
                        <span class="badge system">system</span>
                    {/if}
                    {#if detailNode.isLonely}
                        <span class="badge lonely">isolated</span>
                    {/if}
                </div>

                {#if detailNode.creators && detailNode.creators.length > 0}
                    <div class="detail-creators">
                        <span class="creators-label">Generated by</span>
                        {#each detailNode.creators as creator}
                            <span class="creator-tag">{creator}</span>
                        {/each}
                    </div>
                {/if}

                {#if detailNode.correctors && detailNode.correctors.length > 0}
                    <div class="detail-creators correctors">
                        <span class="creators-label">Corrected by</span>
                        {#each detailNode.correctors as corrector}
                            <span class="corrector-tag">{corrector}</span>
                        {/each}
                    </div>
                {/if}

                <div class="detail-body">
                    {#if getNodeRelations(detailNode).length > 0}
                        {@const relations = getNodeRelations(detailNode)}
                        {@const grouped = groupRelations(relations)}
                        {#each Object.entries(grouped) as [relType, rels]}
                            <div class="relation-group">
                                <div class="relation-type" style="color: {getRelationColor(relType)}">{relType}</div>
                                {#each rels as rel}
                                    <div class="relation-row">
                                        {#if rel.direction === 'out'}
                                            <span class="arrow">&#8594;</span>
                                            <span class="rel-target">{rel.target}</span>
                                        {:else}
                                            <span class="rel-target">{rel.target}</span>
                                            <span class="arrow">&#8594;</span>
                                            <span class="rel-self">{detailNode.label}</span>
                                        {/if}
                                    </div>
                                {/each}
                            </div>
                        {/each}
                    {:else}
                        <div class="detail-empty">No connections found.</div>
                    {/if}
                </div>
            </div>
        {/if}

        <!-- Context menu -->
        {#if contextMenu}
            <!-- svelte-ignore a11y_no_static_element_interactions -->
            <div class="ctx-backdrop" onclick={closeContextMenu}></div>
            <div class="ctx-menu" style="left: {contextMenu.x}px; top: {contextMenu.y}px;">
                <div class="ctx-header">{contextMenu.node.label}</div>
                <button class="ctx-item" onclick={copyNeuronData}>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
                    </svg>
                    Copy neuron data
                </button>
            </div>
        {/if}

        <!-- Bottom-right: Zoom indicator -->
        <div class="viz-panel panel-bottom-right">
            <span class="zoom-value">{zoomPercent}%</span>
        </div>

        <!-- Empty state -->
        {#if !loading && neuronCount === 0}
            <div class="viz-empty">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" opacity="0.4">
                    <circle cx="12" cy="12" r="10"/>
                    <line x1="12" y1="8" x2="12" y2="12"/>
                    <line x1="12" y1="16" x2="12.01" y2="16"/>
                </svg>
                <p>No neurons yet.</p>
                <p class="hint">Teach Loom some facts to see your knowledge graph.</p>
            </div>
        {/if}

        <!-- Loader -->
        {#if loading}
            <div class="viz-loader">
                <svg class="loader-ring" width="56" height="56" viewBox="0 0 56 56">
                    <circle cx="28" cy="28" r="22" fill="none" stroke="rgba(100,200,255,0.15)" stroke-width="3"/>
                    <circle class="loader-arc" cx="28" cy="28" r="22" fill="none" stroke="rgba(100,200,255,0.8)" stroke-width="3" stroke-linecap="round" stroke-dasharray="40 100"/>
                </svg>
            </div>
        {/if}
    </div>
{/if}

<style>
    /* ============ Overlay & Canvas */
    .viz-overlay { position: fixed; inset: 0; background: #050510; z-index: 200; overflow: hidden; }
    .viz-canvas { width: 100%; height: 100%; display: block; }

    /* ============ Header */
    .viz-header {
        position: absolute; top: 0; left: 0; right: 0; height: 56px;
        background: linear-gradient(to bottom, rgba(5,5,16,0.9) 0%, rgba(5,5,16,0.6) 60%, transparent 100%);
        display: flex; align-items: center; justify-content: space-between;
        padding: 0 1.25rem; pointer-events: none; z-index: 210;
    }
    .viz-header > * { pointer-events: auto; }

    .viz-title {
        font-size: 1rem; font-weight: 600; color: rgba(220,230,245,0.9);
        letter-spacing: 0.3px; display: flex; align-items: center; gap: 0.5rem; user-select: none;
    }
    .viz-title-dot {
        width: 8px; height: 8px; background: #64c8ff; border-radius: 50%;
        box-shadow: 0 0 8px rgba(100,200,255,0.6);
    }

    .viz-close {
        width: 40px; height: 40px; border-radius: 12px;
        background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.1);
        color: rgba(220,230,245,0.7); cursor: pointer;
        display: flex; align-items: center; justify-content: center; transition: all 0.2s;
    }
    .viz-close:hover { background: rgba(255,80,80,0.15); border-color: rgba(255,80,80,0.4); color: #ff6b6b; }

    /* ============ Search */
    .viz-search-wrapper { position: relative; display: flex; align-items: center; }
    .viz-search-icon {
        position: absolute; left: 10px; color: rgba(200,210,230,0.4);
        display: flex; align-items: center; pointer-events: none; z-index: 1;
    }
    .viz-search {
        width: 220px; padding: 0.5rem 0.75rem 0.5rem 2rem;
        background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.1);
        border-radius: 10px; color: rgba(220,230,245,0.9); font-size: 0.8125rem;
        font-family: inherit; outline: none; transition: all 0.2s;
    }
    .viz-search::placeholder { color: rgba(200,210,230,0.35); }
    .viz-search:focus { background: rgba(255,255,255,0.1); border-color: rgba(100,200,255,0.4); box-shadow: 0 0 12px rgba(100,200,255,0.1); }

    .viz-search-results {
        position: absolute; top: 100%; left: 0; right: 0; margin-top: 4px;
        background: rgba(15,15,30,0.95); border: 1px solid rgba(255,255,255,0.1);
        border-radius: 10px; overflow: hidden; box-shadow: 0 8px 32px rgba(0,0,0,0.5); z-index: 220;
    }
    .viz-search-result {
        display: flex; align-items: center; gap: 0.5rem; width: 100%;
        padding: 0.5rem 0.75rem; background: none; border: none;
        color: rgba(200,210,230,0.8); font-size: 0.8125rem; font-family: inherit;
        cursor: pointer; text-align: left; transition: background 0.15s;
    }
    .viz-search-result:hover { background: rgba(100,200,255,0.1); color: rgba(220,230,245,1); }
    .result-dot { width: 6px; height: 6px; background: #64c8ff; border-radius: 50%; flex-shrink: 0; }
    .result-count {
        margin-left: auto; font-size: 0.6875rem; color: rgba(200,210,230,0.4);
        background: rgba(255,255,255,0.06); padding: 1px 6px; border-radius: 8px;
    }

    /* ============ Shared panel style */
    .viz-panel {
        position: absolute; z-index: 210;
        background: rgba(10, 10, 25, 0.85);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
    }

    /* ============ Top-right stats */
    .panel-top-right {
        top: 4.5rem; right: 1.25rem;
        padding: 0.75rem 1rem;
        display: flex; flex-direction: column; gap: 0.5rem;
        min-width: 120px;
    }
    .panel-row {
        display: flex; align-items: baseline; gap: 0.5rem;
    }
    .panel-value {
        font-size: 1.25rem; font-weight: 700; color: rgba(220,230,245,0.9);
        font-variant-numeric: tabular-nums;
    }
    .panel-label { font-size: 0.6875rem; color: rgba(200,210,230,0.45); text-transform: uppercase; letter-spacing: 0.5px; }
    .panel-divider { height: 1px; background: rgba(255,255,255,0.06); }
    .panel-row.discovery { gap: 0.375rem; align-items: center; }
    .discovery-dot {
        width: 6px; height: 6px; background: #34d399; border-radius: 50%;
        animation: disc-pulse 2s ease-in-out infinite;
    }
    @keyframes disc-pulse {
        0%, 100% { box-shadow: 0 0 4px rgba(52,211,153,0.4); opacity: 1; }
        50% { box-shadow: 0 0 10px rgba(52,211,153,0.8); opacity: 0.7; }
    }

    /* ============ Bottom-left legend */
    .panel-bottom-left {
        bottom: 1.25rem; left: 1.25rem;
        padding: 0.625rem 0.875rem;
        display: flex; flex-direction: column; gap: 0.375rem;
    }
    .legend-item {
        display: flex; align-items: center; gap: 0.5rem;
        font-size: 0.75rem; color: rgba(200,210,230,0.6); user-select: none;
    }
    .legend-neuron {
        width: 10px; height: 10px; border-radius: 50%;
        background: radial-gradient(circle, rgba(255,255,255,0.8) 20%, #6ecfff 60%, transparent 100%);
        box-shadow: 0 0 6px rgba(110,207,255,0.5);
    }
    .legend-synapse { width: 18px; height: 2px; background: rgba(100,140,200,0.6); border-radius: 1px; }
    .legend-dendrite {
        width: 18px; height: 2px; position: relative;
        background: rgba(110,207,255,0.3); border-radius: 1px;
    }
    .legend-dendrite::after {
        content: ''; position: absolute; right: 0; top: -3px;
        width: 8px; height: 8px; border-right: 1.5px solid rgba(110,207,255,0.3);
        border-top: 1.5px solid rgba(110,207,255,0.3); transform: rotate(30deg);
    }
    .legend-exploring {
        width: 18px; height: 2px; position: relative;
        background: repeating-linear-gradient(90deg, rgba(80,220,130,0.6) 0px, rgba(80,220,130,0.6) 4px, transparent 4px, transparent 8px);
        border-radius: 1px;
    }

    /* ============ Bottom-right zoom */
    .panel-bottom-right {
        bottom: 1.25rem; right: 1.25rem;
        padding: 0.4rem 0.75rem;
    }
    .zoom-value {
        font-size: 0.8125rem; font-weight: 600; color: rgba(200,210,230,0.6);
        font-variant-numeric: tabular-nums; user-select: none;
    }

    /* ============ Neuron detail panel (right side, fixed) */
    .panel-detail {
        top: 4.5rem; right: 1.25rem; bottom: 1.25rem;
        width: 320px;
        display: flex; flex-direction: column;
        animation: slide-in 0.25s ease-out;
    }

    @keyframes slide-in {
        from { opacity: 0; transform: translateX(20px); }
        to { opacity: 1; transform: translateX(0); }
    }

    .detail-header {
        display: flex; align-items: center; justify-content: space-between;
        padding: 0.875rem 1rem; border-bottom: 1px solid rgba(255,255,255,0.06);
        flex-shrink: 0;
    }
    .detail-header h3 {
        font-size: 1rem; font-weight: 600; color: rgba(220,230,245,0.95);
        margin: 0; text-transform: capitalize;
    }
    .detail-close {
        width: 28px; height: 28px; border-radius: 8px;
        background: rgba(255,255,255,0.06); border: none;
        color: rgba(200,210,230,0.5); cursor: pointer;
        display: flex; align-items: center; justify-content: center; transition: all 0.15s;
    }
    .detail-close:hover { background: rgba(255,80,80,0.15); color: #ff6b6b; }

    .detail-meta {
        display: flex; align-items: center; gap: 0.5rem;
        padding: 0.5rem 1rem; font-size: 0.75rem; color: rgba(200,210,230,0.5);
        flex-shrink: 0;
    }

    .badge {
        padding: 1px 6px; border-radius: 6px; font-size: 0.625rem;
        font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;
    }
    .badge.system { background: rgba(167,139,250,0.15); color: #a78bfa; }
    .badge.lonely { background: rgba(251,146,60,0.15); color: #fb923c; }

    .detail-creators {
        display: flex; flex-wrap: wrap; align-items: center; gap: 0.375rem;
        padding: 0.375rem 1rem 0.5rem; flex-shrink: 0;
        border-bottom: 1px solid rgba(255,255,255,0.06);
    }
    .creators-label {
        font-size: 0.6875rem; color: rgba(200,210,230,0.4);
        text-transform: uppercase; letter-spacing: 0.3px; margin-right: 0.125rem;
    }
    .creator-tag {
        font-size: 0.6875rem; color: rgba(100,200,255,0.8);
        background: rgba(100,200,255,0.1); padding: 1px 8px;
        border-radius: 6px;
    }
    .detail-creators.correctors { border-bottom-color: rgba(251,146,60,0.15); }
    .detail-creators.correctors .creators-label { color: rgba(251,146,60,0.6); }
    .corrector-tag {
        font-size: 0.6875rem; color: rgba(251,146,60,0.8);
        background: rgba(251,146,60,0.1); padding: 1px 8px;
        border-radius: 6px;
    }

    .detail-body {
        flex: 1; overflow-y: auto; padding: 0.5rem 1rem 0.75rem;
        /* Invisible scrollbar */
        scrollbar-width: none; -ms-overflow-style: none;
    }
    .detail-body::-webkit-scrollbar { display: none; }

    .relation-group { margin-bottom: 0.625rem; }
    .relation-group:last-child { margin-bottom: 0; }

    .relation-type {
        font-size: 0.6875rem; font-weight: 600; text-transform: uppercase;
        letter-spacing: 0.5px; margin-bottom: 0.25rem; opacity: 0.8;
    }

    .relation-row {
        display: flex; align-items: center; gap: 0.375rem;
        font-size: 0.8125rem; color: rgba(200,210,230,0.7);
        padding: 0.2rem 0; line-height: 1.4;
    }
    .arrow { color: rgba(200,210,230,0.3); font-size: 0.75rem; }
    .rel-target { color: rgba(220,230,245,0.85); }
    .rel-self { color: rgba(220,230,245,0.6); font-size: 0.75rem; }

    .detail-empty {
        padding: 0.75rem 0; font-size: 0.8125rem;
        color: rgba(200,210,230,0.35); font-style: italic;
    }

    /* ============ Context menu */
    .ctx-backdrop {
        position: fixed; inset: 0; z-index: 230;
    }
    .ctx-menu {
        position: fixed; z-index: 231;
        background: rgba(15, 15, 30, 0.95);
        border: 1px solid rgba(255,255,255,0.12);
        border-radius: 10px; overflow: hidden;
        box-shadow: 0 8px 32px rgba(0,0,0,0.6);
        min-width: 180px;
        animation: ctx-in 0.12s ease-out;
    }
    @keyframes ctx-in {
        from { opacity: 0; transform: scale(0.95); }
        to { opacity: 1; transform: scale(1); }
    }
    .ctx-header {
        padding: 0.5rem 0.75rem; font-size: 0.75rem; font-weight: 600;
        color: rgba(200,210,230,0.5); text-transform: capitalize;
        border-bottom: 1px solid rgba(255,255,255,0.06);
    }
    .ctx-item {
        display: flex; align-items: center; gap: 0.5rem; width: 100%;
        padding: 0.5rem 0.75rem; background: none; border: none;
        color: rgba(220,230,245,0.85); font-size: 0.8125rem; font-family: inherit;
        cursor: pointer; text-align: left; transition: background 0.12s;
    }
    .ctx-item:hover { background: rgba(100,200,255,0.12); }
    .ctx-item svg { color: rgba(200,210,230,0.5); flex-shrink: 0; }

    /* ============ Empty state */
    .viz-empty {
        position: absolute; inset: 0;
        display: flex; flex-direction: column; align-items: center; justify-content: center;
        gap: 0.75rem; z-index: 205; pointer-events: none;
    }
    .viz-empty p { font-size: 1rem; color: rgba(200,210,230,0.5); margin: 0; }
    .viz-empty .hint { font-size: 0.8125rem; color: rgba(200,210,230,0.3); }

    /* ============ Loader */
    .viz-loader {
        position: absolute; inset: 0;
        display: flex; align-items: center; justify-content: center;
        z-index: 215; pointer-events: none;
    }
    .loader-ring { animation: loader-spin 2s linear infinite; }
    .loader-arc { animation: loader-dash 1.5s ease-in-out infinite; transform-origin: center; }
    @keyframes loader-spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
    @keyframes loader-dash { 0% { stroke-dasharray: 10 128; } 50% { stroke-dasharray: 80 58; } 100% { stroke-dasharray: 10 128; } }

    /* ============ Mobile */
    @media (max-width: 640px) {
        .viz-search { width: 140px; }
        .panel-detail {
            top: auto; bottom: 0; left: 0; right: 0;
            width: 100%; max-height: 50vh; border-radius: 16px 16px 0 0;
        }
        .panel-top-right { top: 4rem; right: 0.75rem; }
        .panel-bottom-left { bottom: 0.75rem; left: 0.75rem; }
    }
</style>
