/**
 * graph-engine.js
 * Force-directed graph simulation engine for the Loom knowledge graph.
 * Handles layout, physics, camera state, and hit-testing.
 */

const CACHE_KEY = 'loom_graph_layout';

export class GraphEngine {
    constructor() {
        /** @type {Array<Object>} */
        this.nodes = [];
        /** @type {Array<Object>} */
        this.edges = [];
        /** @type {Array<Object>} */
        this.potentialEdges = [];
        /** @type {Array<Object>} */
        this.clusters = [];
        /** @type {Array<Object>} */
        this.transitiveGaps = [];
        /** @type {Set<string>} */
        this.lonelyNeurons = new Set();
        /** @type {Array<Object>} */
        this.probeParticles = [];
        /** @type {Array<Object>} Signal particles flowing along edges */
        this.signalParticles = [];
        /** @type {Array<Object>} Expanding pulse waves from exploring neurons */
        this.pulseWaves = [];
        /** @type {Array<Object>} Brief spark flashes at potential connections */
        this.sparkEffects = [];
        /** @type {Array<Object>} Tendrils extending from neurons seeking connections */
        this.seekingTendrils = [];

        // Camera
        this.zoom = 1;
        this.panX = 0;
        this.panY = 0;

        // Interaction state
        this.hoveredNode = null;
        this.selectedNode = null;
        this.draggedNode = null;

        // Discovery animation flag
        this.isDiscovering = false;

        // Internal
        this._nodeMap = new Map();
    }

    // ------------------------------------------------------------------ init

    /**
     * Build the graph from an API response.
     * Expected shape: { neurons: [...], synapses: [...],
     *   potential_edges?, clusters?, transitive_gaps?, lonely_neurons? }
     * @param {Object} data
     */
    initGraph(data) {
        this._nodeMap.clear();
        this.nodes = [];
        this.edges = [];
        this.potentialEdges = [];
        this.clusters = data.clusters || [];
        this.transitiveGaps = [];
        this.lonelyNeurons = new Set(data.lonely_neurons || []);
        this.probeParticles = [];
        this.seekingTendrils = [];

        const neurons = data.neurons || data.nodes || [];
        const synapses = data.synapses || data.edges || [];
        const n = neurons.length;

        // Try to restore cached positions
        const cached = this.loadCachedLayout();
        const cachedPositions = cached ? cached.positions : null;

        // Fibonacci spiral layout -------------------------------------------
        const centerX = 0;
        const centerY = 0;
        const spreadFactor = Math.max(600, Math.sqrt(n) * 120);

        for (let i = 0; i < n; i++) {
            const neuron = neurons[i];
            const id = neuron.id || neuron.name || neuron.label;

            let x, y;
            if (cachedPositions && cachedPositions[id]) {
                x = cachedPositions[id].x;
                y = cachedPositions[id].y;
            } else {
                const angle = i * 2.4; // golden angle in radians
                const r = spreadFactor * Math.sqrt(i / Math.max(n, 1));
                x = centerX + Math.cos(angle) * r;
                y = centerY + Math.sin(angle) * r;
            }

            const connections = neuron.connections || 0;
            const isSystem = !!(neuron.isSystem || neuron.is_system);
            const radius = isSystem
                ? 24
                : Math.max(4, Math.min(4 + connections * 1.5, 20));

            const node = {
                id,
                label: neuron.label || neuron.name || id,
                connections,
                creators: neuron.creators || [],
                isLonely: this.lonelyNeurons.has(id),
                isSystem,
                x,
                y,
                vx: 0,
                vy: 0,
                radius,
                pulsePhase: Math.random() * Math.PI * 2,
                appearProgress: cachedPositions ? 1 : 0,
            };

            this.nodes.push(node);
            this._nodeMap.set(id, node);
        }

        // Build edges -------------------------------------------------------
        this._buildEdges(synapses);

        // Build potential edges ---------------------------------------------
        if (data.potential_edges) {
            for (const pe of data.potential_edges) {
                const src = this._nodeMap.get(pe.source);
                const tgt = this._nodeMap.get(pe.target);
                if (src && tgt) {
                    this.potentialEdges.push({
                        source: src,
                        target: tgt,
                        relation: pe.relation || '',
                        appearProgress: 0,
                    });
                }
            }
        }

        // Build transitive gaps ---------------------------------------------
        if (data.transitive_gaps) {
            for (const tg of data.transitive_gaps) {
                const src = this._nodeMap.get(tg.source);
                const tgt = this._nodeMap.get(tg.target);
                if (src && tgt) {
                    this.transitiveGaps.push({ source: src, target: tgt });
                }
            }
        }

        // Pre-settle physics briefly then let animation finish settling visually
        if (!cachedPositions) {
            for (let i = 0; i < 40; i++) {
                this.tick();
            }
            // Make nodes visible immediately; let remaining settling animate
            for (const node of this.nodes) {
                node.appearProgress = 1;
            }
            for (const edge of this.edges) {
                edge.appearProgress = 1;
            }
        }
    }

    // -------------------------------------------------------------- refresh

    /**
     * Update graph with new data, preserving existing node positions.
     * @param {Object} data
     */
    refreshGraph(data) {
        const neurons = data.neurons || data.nodes || [];
        const synapses = data.synapses || data.edges || [];
        const existingIds = new Set(this.nodes.map((n) => n.id));
        this.lonelyNeurons = new Set(data.lonely_neurons || []);
        this.clusters = data.clusters || [];

        // Update existing nodes, add new ones
        for (const neuron of neurons) {
            const id = neuron.id || neuron.name || neuron.label;
            const existing = this._nodeMap.get(id);

            if (existing) {
                // Update metadata, keep position
                existing.connections = neuron.connections || 0;
                existing.creators = neuron.creators || [];
                existing.isLonely = this.lonelyNeurons.has(id);
                existing.isSystem = !!(neuron.isSystem || neuron.is_system);
                existing.radius = existing.isSystem
                    ? 24
                    : Math.max(4, Math.min(4 + existing.connections * 1.5, 20));
            } else {
                // New node: place near center with jitter
                const jitter = 100;
                const connections = neuron.connections || 0;
                const isSystem = !!(neuron.isSystem || neuron.is_system);
                const node = {
                    id,
                    label: neuron.label || neuron.name || id,
                    connections,
                    creators: neuron.creators || [],
                    isLonely: this.lonelyNeurons.has(id),
                    isSystem,
                    x: (Math.random() - 0.5) * jitter,
                    y: (Math.random() - 0.5) * jitter,
                    vx: 0,
                    vy: 0,
                    radius: isSystem
                        ? 24
                        : Math.max(4, Math.min(4 + connections * 1.5, 20)),
                    pulsePhase: Math.random() * Math.PI * 2,
                    appearProgress: 0,
                };
                this.nodes.push(node);
                this._nodeMap.set(id, node);
            }
        }

        // Remove nodes no longer in the data
        const newIds = new Set(
            neurons.map((n) => n.id || n.name || n.label)
        );
        this.nodes = this.nodes.filter((n) => {
            if (!newIds.has(n.id)) {
                this._nodeMap.delete(n.id);
                return false;
            }
            return true;
        });

        // Rebuild edges
        this._buildEdges(synapses);

        // Rebuild potential edges
        this.potentialEdges = [];
        if (data.potential_edges) {
            for (const pe of data.potential_edges) {
                const src = this._nodeMap.get(pe.source);
                const tgt = this._nodeMap.get(pe.target);
                if (src && tgt) {
                    this.potentialEdges.push({
                        source: src,
                        target: tgt,
                        relation: pe.relation || '',
                        appearProgress: 0,
                    });
                }
            }
        }

        // Rebuild transitive gaps
        this.transitiveGaps = [];
        if (data.transitive_gaps) {
            for (const tg of data.transitive_gaps) {
                const src = this._nodeMap.get(tg.source);
                const tgt = this._nodeMap.get(tg.target);
                if (src && tgt) {
                    this.transitiveGaps.push({ source: src, target: tgt });
                }
            }
        }
    }

    // ----------------------------------------------------------------- tick

    /**
     * Run one physics simulation step.
     */
    tick() {
        const n = this.nodes.length;
        if (n === 0) return;

        // ---- Repulsion ----------------------------------------------------
        if (n > 200) {
            this._gridRepulsion();
        } else {
            this._pairwiseRepulsion(n);
        }

        // ---- Edge spring attraction ---------------------------------------
        for (const edge of this.edges) {
            const src = edge.source;
            const tgt = edge.target;
            const dx = tgt.x - src.x;
            const dy = tgt.y - src.y;
            const dist = Math.sqrt(dx * dx + dy * dy) || 1;

            const idealLength = 180;
            const springStrength = 0.025 * (edge.weight || 1);
            const displacement = dist - idealLength;
            const force = springStrength * displacement / dist;

            const fx = dx * force;
            const fy = dy * force;

            src.vx += fx;
            src.vy += fy;
            tgt.vx -= fx;
            tgt.vy -= fy;
        }

        // ---- Center gravity -----------------------------------------------
        const gravity = n > 200 ? 0.0002 : 0.0001;
        for (const node of this.nodes) {
            node.vx -= node.x * gravity;
            node.vy -= node.y * gravity;
        }

        // ---- Integration --------------------------------------------------
        const damping = 0.96;
        const maxVelocity = 3;

        for (const node of this.nodes) {
            // Skip pinned / dragged node
            if (node === this.draggedNode) {
                node.vx = 0;
                node.vy = 0;
                continue;
            }

            node.vx *= damping;
            node.vy *= damping;

            // Freeze nearly-still nodes to prevent jitter
            const speed = Math.sqrt(node.vx * node.vx + node.vy * node.vy);
            if (speed < 0.01) {
                node.vx = 0;
                node.vy = 0;
            } else if (speed > maxVelocity) {
                const scale = maxVelocity / speed;
                node.vx *= scale;
                node.vy *= scale;
            }

            node.x += node.vx;
            node.y += node.vy;

            // Pulse animation (slow, subtle)
            node.pulsePhase += 0.012;

            // Appear animation for new nodes
            if (node.appearProgress < 1) {
                node.appearProgress = Math.min(1, node.appearProgress + 0.02);
            }
        }

        // Appear animation for edges
        for (const edge of this.edges) {
            if (edge.appearProgress < 1) {
                edge.appearProgress = Math.min(1, edge.appearProgress + 0.03);
            }
        }

        // Appear animation for potential edges
        for (const pe of this.potentialEdges) {
            if (pe.appearProgress < 1) {
                pe.appearProgress = Math.min(1, pe.appearProgress + 0.015);
            }
        }

        // Update probe particles
        this._updateProbeParticles();
    }

    // --------------------------------------------------------- camera utils

    /**
     * Set zoom and pan to fit all nodes within the given viewport.
     * @param {number} width  Canvas width in CSS pixels
     * @param {number} height Canvas height in CSS pixels
     */
    centerAndZoomToFit(width, height) {
        if (this.nodes.length === 0) {
            this.zoom = 1;
            this.panX = 0;
            this.panY = 0;
            return;
        }

        let minX = Infinity, minY = Infinity;
        let maxX = -Infinity, maxY = -Infinity;

        for (const node of this.nodes) {
            const r = node.radius;
            if (node.x - r < minX) minX = node.x - r;
            if (node.y - r < minY) minY = node.y - r;
            if (node.x + r > maxX) maxX = node.x + r;
            if (node.y + r > maxY) maxY = node.y + r;
        }

        const graphWidth = maxX - minX;
        const graphHeight = maxY - minY;
        const padding = 80;

        const scaleX = (width - padding * 2) / (graphWidth || 1);
        const scaleY = (height - padding * 2) / (graphHeight || 1);
        this.zoom = Math.min(scaleX, scaleY, 2); // cap at 2x
        this.zoom = Math.max(this.zoom, 0.05); // floor

        const cx = (minX + maxX) / 2;
        const cy = (minY + maxY) / 2;
        this.panX = width / 2 - cx * this.zoom;
        this.panY = height / 2 - cy * this.zoom;
    }

    /**
     * Convert screen coordinates to world coordinates.
     * @param {number} sx Screen X
     * @param {number} sy Screen Y
     * @returns {{ x: number, y: number }}
     */
    screenToWorld(sx, sy) {
        return {
            x: (sx - this.panX) / this.zoom,
            y: (sy - this.panY) / this.zoom,
        };
    }

    /**
     * Convert world coordinates to screen coordinates.
     * @param {number} wx World X
     * @param {number} wy World Y
     * @returns {{ x: number, y: number }}
     */
    worldToScreen(wx, wy) {
        return {
            x: wx * this.zoom + this.panX,
            y: wy * this.zoom + this.panY,
        };
    }

    // ----------------------------------------------------------- hit test

    /**
     * Find the topmost node at the given world coordinates.
     * @param {number} worldX
     * @param {number} worldY
     * @returns {Object|null}
     */
    getNodeAt(worldX, worldY) {
        // Iterate in reverse so topmost (last drawn) nodes are checked first
        for (let i = this.nodes.length - 1; i >= 0; i--) {
            const node = this.nodes[i];
            const dx = worldX - node.x;
            const dy = worldY - node.y;
            const hitRadius = Math.max(node.radius, 10); // minimum hit area
            if (dx * dx + dy * dy <= hitRadius * hitRadius) {
                return node;
            }
        }
        return null;
    }

    // --------------------------------------------------- layout persistence

    /**
     * Save current node positions to sessionStorage.
     */
    saveCachedLayout() {
        try {
            const positions = {};
            for (const node of this.nodes) {
                positions[node.id] = { x: node.x, y: node.y };
            }
            sessionStorage.setItem(
                CACHE_KEY,
                JSON.stringify({
                    positions,
                    zoom: this.zoom,
                    panX: this.panX,
                    panY: this.panY,
                })
            );
        } catch (_) {
            // sessionStorage might be unavailable or full
        }
    }

    /**
     * Load cached layout from sessionStorage.
     * @returns {Object|null}
     */
    loadCachedLayout() {
        try {
            const raw = sessionStorage.getItem(CACHE_KEY);
            if (!raw) return null;
            const data = JSON.parse(raw);
            if (data.zoom != null) {
                this.zoom = data.zoom;
                this.panX = data.panX || 0;
                this.panY = data.panY || 0;
            }
            return data;
        } catch (_) {
            return null;
        }
    }

    // ================================================ PRIVATE HELPERS ====

    /**
     * Build the edges array from synapse data.
     * @param {Array} synapses
     * @private
     */
    _buildEdges(synapses) {
        this.edges = [];
        for (const syn of synapses) {
            const srcId =
                typeof syn.source === 'string' ? syn.source : syn.source?.id;
            const tgtId =
                typeof syn.target === 'string' ? syn.target : syn.target?.id;
            const src = this._nodeMap.get(srcId);
            const tgt = this._nodeMap.get(tgtId);
            if (src && tgt) {
                this.edges.push({
                    source: src,
                    target: tgt,
                    relation: syn.relation || syn.label || '',
                    weight: syn.weight != null ? syn.weight : 1,
                    appearProgress: 1,
                });
            }
        }
    }

    /**
     * O(n^2) pairwise repulsion with skip optimisation for n > 80.
     * @param {number} n
     * @private
     */
    _pairwiseRepulsion(n) {
        const repulsionStrength = 800;
        const skipThreshold = 80;

        for (let i = 0; i < n; i++) {
            const a = this.nodes[i];
            for (let j = i + 1; j < n; j++) {
                // Skip distant pairs probabilistically for large-ish graphs
                if (n > skipThreshold && (i + j) % 3 === 0) continue;

                const b = this.nodes[j];
                let dx = b.x - a.x;
                let dy = b.y - a.y;
                let distSq = dx * dx + dy * dy;

                if (distSq < 1) {
                    // Jitter to prevent overlap
                    dx = (Math.random() - 0.5) * 2;
                    dy = (Math.random() - 0.5) * 2;
                    distSq = dx * dx + dy * dy;
                }

                // Cut off at large distance to save cycles
                if (distSq > 250000) continue; // ~500px

                const force = repulsionStrength / distSq;
                const fx = dx * force;
                const fy = dy * force;

                a.vx -= fx;
                a.vy -= fy;
                b.vx += fx;
                b.vy += fy;
            }
        }
    }

    /**
     * Grid-based repulsion for large node counts (n > 200).
     * @private
     */
    _gridRepulsion() {
        const cellSize = 300;
        const repulsionStrength = 800;
        const grid = new Map();

        // Assign nodes to grid cells
        for (const node of this.nodes) {
            const cx = Math.floor(node.x / cellSize);
            const cy = Math.floor(node.y / cellSize);
            const key = `${cx},${cy}`;
            if (!grid.has(key)) grid.set(key, []);
            grid.get(key).push(node);
            node._gcx = cx;
            node._gcy = cy;
        }

        // Check only neighbor cells (3x3 neighborhood)
        for (const node of this.nodes) {
            const cx = node._gcx;
            const cy = node._gcy;

            for (let dx = -1; dx <= 1; dx++) {
                for (let dy = -1; dy <= 1; dy++) {
                    const key = `${cx + dx},${cy + dy}`;
                    const cell = grid.get(key);
                    if (!cell) continue;

                    for (const other of cell) {
                        if (other === node || other.id <= node.id) continue;

                        let ddx = other.x - node.x;
                        let ddy = other.y - node.y;
                        let distSq = ddx * ddx + ddy * ddy;

                        if (distSq < 1) {
                            ddx = (Math.random() - 0.5) * 2;
                            ddy = (Math.random() - 0.5) * 2;
                            distSq = ddx * ddx + ddy * ddy;
                        }

                        if (distSq > 250000) continue;

                        const force = repulsionStrength / distSq;
                        const fx = ddx * force;
                        const fy = ddy * force;

                        node.vx -= fx;
                        node.vy -= fy;
                        other.vx += fx;
                        other.vy += fy;
                    }
                }
            }
        }
    }

    /**
     * Update all particle systems: probes, signals, pulses, sparks.
     * @private
     */
    _updateProbeParticles() {
        // ---- Probe particles on potential edges ----
        if (this.isDiscovering && this.potentialEdges.length > 0) {
            if (Math.random() < 0.12) {
                const edge = this.potentialEdges[Math.floor(Math.random() * this.potentialEdges.length)];
                this.probeParticles.push({
                    edge,
                    t: 0,
                    speed: 0.005 + Math.random() * 0.008,
                    size: 0.6 + Math.random() * 0.6,
                });
            }
        }
        for (let i = this.probeParticles.length - 1; i >= 0; i--) {
            const p = this.probeParticles[i];
            p.t += p.speed;
            if (p.t >= 1) {
                // Spawn a spark when probe arrives
                if (this.sparkEffects.length < 8) {
                    const tgt = p.edge.target;
                    this.sparkEffects.push({ x: tgt.x, y: tgt.y, life: 1.0, decay: 0.03 + Math.random() * 0.02 });
                }
                this.probeParticles.splice(i, 1);
            }
        }

        // ---- Signal particles flowing along existing edges ----
        if (this.edges.length > 0 && this.signalParticles.length < 60) {
            if (Math.random() < 0.06) {
                const edge = this.edges[Math.floor(Math.random() * this.edges.length)];
                this.signalParticles.push({
                    edge,
                    t: 0,
                    speed: 0.003 + Math.random() * 0.006,
                    alpha: 0.3 + Math.random() * 0.4,
                });
            }
        }
        for (let i = this.signalParticles.length - 1; i >= 0; i--) {
            const p = this.signalParticles[i];
            p.t += p.speed;
            if (p.t >= 1) {
                this.signalParticles.splice(i, 1);
            }
        }

        // ---- Pulse waves from nodes with potential connections ----
        if (this.isDiscovering && this.potentialEdges.length > 0 && this.pulseWaves.length < 6) {
            if (Math.random() < 0.03) {
                const pe = this.potentialEdges[Math.floor(Math.random() * this.potentialEdges.length)];
                const node = Math.random() < 0.5 ? pe.source : pe.target;
                this.pulseWaves.push({
                    x: node.x, y: node.y,
                    radius: node.radius,
                    maxRadius: node.radius * 8,
                    life: 1.0,
                    decay: 0.008 + Math.random() * 0.005,
                });
            }
        }
        for (let i = this.pulseWaves.length - 1; i >= 0; i--) {
            const w = this.pulseWaves[i];
            w.life -= w.decay;
            w.radius += (w.maxRadius - w.radius) * 0.04;
            if (w.life <= 0) this.pulseWaves.splice(i, 1);
        }

        // ---- Spark effects ----
        for (let i = this.sparkEffects.length - 1; i >= 0; i--) {
            const s = this.sparkEffects[i];
            s.life -= s.decay;
            if (s.life <= 0) this.sparkEffects.splice(i, 1);
        }

        // ---- Seeking tendrils from neurons trying to connect ----
        const hasSeekingNodes = this.potentialEdges.length > 0 || this.lonelyNeurons.size > 0;
        if (hasSeekingNodes && this.seekingTendrils.length < 25) {
            if (Math.random() < 0.04) {
                const candidates = [];
                for (const pe of this.potentialEdges) {
                    candidates.push(pe.source, pe.target);
                }
                for (const node of this.nodes) {
                    if (node.isLonely) candidates.push(node);
                }
                if (candidates.length > 0) {
                    const node = candidates[Math.floor(Math.random() * candidates.length)];
                    this.seekingTendrils.push({
                        node,
                        angle: Math.random() * Math.PI * 2,
                        length: 0,
                        maxLength: 25 + Math.random() * 50,
                        life: 1.0,
                        growSpeed: 0.6 + Math.random() * 1.0,
                        fadeSpeed: 0.012 + Math.random() * 0.008,
                        wave: Math.random() * Math.PI * 2,
                    });
                }
            }
        }
        for (let i = this.seekingTendrils.length - 1; i >= 0; i--) {
            const t = this.seekingTendrils[i];
            if (t.length < t.maxLength) {
                t.length += t.growSpeed;
            } else {
                t.life -= t.fadeSpeed;
            }
            t.wave += 0.03;
            if (t.life <= 0) this.seekingTendrils.splice(i, 1);
        }
    }
}
