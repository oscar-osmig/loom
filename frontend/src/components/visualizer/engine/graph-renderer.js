/**
 * graph-renderer.js
 * Canvas renderer for the Loom knowledge graph.
 * Draws neurons with dendrites, synaptic connections, labels, and clusters.
 */

import { getClusterColor, getNodeColor, hashString } from './graph-utils.js';

// LOD thresholds
const LOD_FAR = 0.25;
const LOD_MEDIUM = 0.6;

// Colors
const COLOR_SELECTED = 'hsl(140, 85%, 55%)';
const COLOR_NEW = 'hsl(140, 75%, 50%)';
const COLOR_SYSTEM = 'hsl(260, 70%, 60%)';
const COLOR_LONELY = 'hsl(30, 90%, 55%)';

// ============================================================ main render

export function render(ctx, engine, width, height) {
    const { zoom, panX, panY } = engine;
    const lod = zoom < LOD_FAR ? 'FAR' : zoom < LOD_MEDIUM ? 'MEDIUM' : 'CLOSE';

    const _nodeById = new Map();
    for (const node of engine.nodes) _nodeById.set(node.id, node);

    // 1. Background
    const bgGrad = ctx.createRadialGradient(
        width / 2, height / 2, 0,
        width / 2, height / 2, Math.max(width, height) * 0.8
    );
    bgGrad.addColorStop(0, '#0d1025');
    bgGrad.addColorStop(1, '#050510');
    ctx.fillStyle = bgGrad;
    ctx.fillRect(0, 0, width, height);

    // 2. Camera
    ctx.save();
    ctx.translate(panX, panY);
    ctx.scale(zoom, zoom);

    // Viewport culling
    const pad = 100 / zoom;
    const viewLeft = -panX / zoom - pad;
    const viewTop = -panY / zoom - pad;
    const viewRight = (width - panX) / zoom + pad;
    const viewBottom = (height - panY) / zoom + pad;

    function inView(x, y, margin) {
        margin = margin || 0;
        return x + margin >= viewLeft && x - margin <= viewRight &&
               y + margin >= viewTop && y - margin <= viewBottom;
    }

    function edgeInView(src, tgt) {
        const minX = Math.min(src.x, tgt.x);
        const maxX = Math.max(src.x, tgt.x);
        const minY = Math.min(src.y, tgt.y);
        const maxY = Math.max(src.y, tgt.y);
        return maxX >= viewLeft && minX <= viewRight &&
               maxY >= viewTop && minY <= viewBottom;
    }

    // 3. Cluster hulls
    if (lod !== 'FAR' && engine.clusters.length > 0) {
        _drawClusterHulls(ctx, engine, _nodeById, zoom);
    }

    // 4. Exploration pulse waves (expanding rings from exploring neurons)
    if (lod !== 'FAR') {
        for (const w of engine.pulseWaves) {
            if (!inView(w.x, w.y, w.radius)) continue;
            const alpha = w.life * 0.25;
            ctx.strokeStyle = `rgba(80, 220, 160, ${alpha})`;
            ctx.lineWidth = Math.max(1, 2 / zoom);
            ctx.beginPath();
            ctx.arc(w.x, w.y, w.radius, 0, Math.PI * 2);
            ctx.stroke();

            // Inner softer ring
            if (w.life > 0.5) {
                ctx.strokeStyle = `rgba(80, 220, 160, ${alpha * 0.4})`;
                ctx.beginPath();
                ctx.arc(w.x, w.y, w.radius * 0.6, 0, Math.PI * 2);
                ctx.stroke();
            }
        }
    }

    // 5. Transitive gap lines
    if (lod !== 'FAR') {
        ctx.save();
        ctx.setLineDash([8, 6]);
        ctx.strokeStyle = 'rgba(255, 200, 50, 0.2)';
        ctx.lineWidth = 1.5 / zoom;
        for (const gap of engine.transitiveGaps) {
            if (!edgeInView(gap.source, gap.target)) continue;
            ctx.beginPath();
            ctx.moveTo(gap.source.x, gap.source.y);
            ctx.lineTo(gap.target.x, gap.target.y);
            ctx.stroke();
        }
        ctx.setLineDash([]);
        ctx.restore();
    }

    // 6. Potential edges as organic tendrils
    if (lod !== 'FAR') {
        const time = Date.now() / 1000;
        for (const pe of engine.potentialEdges) {
            if (pe.appearProgress <= 0) continue;
            if (!edgeInView(pe.source, pe.target)) continue;

            const src = pe.source;
            const tgt = pe.target;
            const dx = tgt.x - src.x;
            const dy = tgt.y - src.y;
            const dist = Math.sqrt(dx * dx + dy * dy) || 1;

            // Animated growth: tendril extends from source toward target
            const growT = pe.appearProgress;

            // Curved control point (perpendicular offset + subtle wave)
            const wave = Math.sin(time * 1.5 + src.x * 0.01) * 20;
            const perpX = -dy / dist;
            const perpY = dx / dist;
            const cpX = (src.x + tgt.x) / 2 + perpX * wave;
            const cpY = (src.y + tgt.y) / 2 + perpY * wave;

            // Draw tendril with gradient opacity
            const alpha = 0.35 * growT;
            ctx.save();
            ctx.strokeStyle = `rgba(80, 220, 130, ${alpha})`;
            ctx.lineWidth = Math.max(1, 1.8 / zoom);
            ctx.lineCap = 'round';

            // Animated dash
            ctx.setLineDash([4 / zoom, 6 / zoom]);
            ctx.lineDashOffset = -time * 30;

            ctx.beginPath();
            ctx.moveTo(src.x, src.y);
            ctx.quadraticCurveTo(cpX, cpY, tgt.x, tgt.y);
            ctx.stroke();
            ctx.setLineDash([]);

            // Tendril glow along the curve
            if (lod === 'CLOSE') {
                ctx.strokeStyle = `rgba(80, 255, 140, ${alpha * 0.3})`;
                ctx.lineWidth = Math.max(3, 6 / zoom);
                ctx.beginPath();
                ctx.moveTo(src.x, src.y);
                ctx.quadraticCurveTo(cpX, cpY, tgt.x, tgt.y);
                ctx.stroke();
            }

            ctx.restore();
        }
    }

    // 7. Probe particles with trails (exploring potential connections)
    if (lod !== 'FAR') {
        for (const p of engine.probeParticles) {
            const src = p.edge.source;
            const tgt = p.edge.target;

            const dx = tgt.x - src.x;
            const dy = tgt.y - src.y;
            const dist = Math.sqrt(dx * dx + dy * dy) || 1;
            const wave = Math.sin(Date.now() / 1000 * 1.5 + src.x * 0.01) * 20;
            const perpX = -dy / dist;
            const perpY = dx / dist;
            const cpX = (src.x + tgt.x) / 2 + perpX * wave;
            const cpY = (src.y + tgt.y) / 2 + perpY * wave;

            // Position along quadratic bezier
            const t = p.t;
            const mt = 1 - t;
            const px = mt * mt * src.x + 2 * mt * t * cpX + t * t * tgt.x;
            const py = mt * mt * src.y + 2 * mt * t * cpY + t * t * tgt.y;
            if (!inView(px, py, 15)) continue;

            // Trail (line from slightly behind to current position)
            const trailT = Math.max(0, t - 0.08);
            const tmt = 1 - trailT;
            const trailX = tmt * tmt * src.x + 2 * tmt * trailT * cpX + trailT * trailT * tgt.x;
            const trailY = tmt * tmt * src.y + 2 * tmt * trailT * cpY + trailT * trailT * tgt.y;

            const trailGrad = ctx.createLinearGradient(trailX, trailY, px, py);
            trailGrad.addColorStop(0, 'rgba(80, 255, 160, 0)');
            trailGrad.addColorStop(1, 'rgba(80, 255, 160, 0.6)');
            ctx.strokeStyle = trailGrad;
            ctx.lineWidth = Math.max(1.5, 2.5 / zoom) * p.size;
            ctx.lineCap = 'round';
            ctx.beginPath();
            ctx.moveTo(trailX, trailY);
            ctx.lineTo(px, py);
            ctx.stroke();

            // Particle glow
            const glowR = (4 / zoom) * p.size;
            const glow = ctx.createRadialGradient(px, py, 0, px, py, glowR * 3);
            glow.addColorStop(0, 'rgba(100, 255, 170, 0.9)');
            glow.addColorStop(0.4, 'rgba(80, 220, 140, 0.4)');
            glow.addColorStop(1, 'rgba(80, 220, 140, 0)');
            ctx.fillStyle = glow;
            ctx.beginPath();
            ctx.arc(px, py, glowR * 3, 0, Math.PI * 2);
            ctx.fill();

            // Core dot
            ctx.fillStyle = '#a0ffc0';
            ctx.beginPath();
            ctx.arc(px, py, glowR * 0.6, 0, Math.PI * 2);
            ctx.fill();
        }
    }

    // 8. Signal particles flowing along existing edges (network activity)
    if (lod !== 'FAR') {
        for (const p of engine.signalParticles) {
            const src = p.edge.source;
            const tgt = p.edge.target;
            const px = src.x + (tgt.x - src.x) * p.t;
            const py = src.y + (tgt.y - src.y) * p.t;
            if (!inView(px, py, 8)) continue;

            // Fade in/out at edges of travel
            const fade = p.t < 0.1 ? p.t / 0.1 : p.t > 0.9 ? (1 - p.t) / 0.1 : 1;
            const alpha = p.alpha * fade;

            const r = Math.max(1, 2 / zoom);
            const glow = ctx.createRadialGradient(px, py, 0, px, py, r * 2.5);
            glow.addColorStop(0, `rgba(140, 180, 255, ${alpha})`);
            glow.addColorStop(1, `rgba(140, 180, 255, 0)`);
            ctx.fillStyle = glow;
            ctx.beginPath();
            ctx.arc(px, py, r * 2.5, 0, Math.PI * 2);
            ctx.fill();

            ctx.fillStyle = `rgba(180, 210, 255, ${alpha})`;
            ctx.beginPath();
            ctx.arc(px, py, r * 0.7, 0, Math.PI * 2);
            ctx.fill();
        }
    }

    // 9. Spark effects at potential connection points
    if (lod !== 'FAR') {
        for (const s of engine.sparkEffects) {
            if (!inView(s.x, s.y, 30)) continue;

            const r = (12 / zoom) * s.life;
            const alpha = s.life * 0.7;

            // Outer flash
            const flash = ctx.createRadialGradient(s.x, s.y, 0, s.x, s.y, r);
            flash.addColorStop(0, `rgba(160, 255, 200, ${alpha})`);
            flash.addColorStop(0.3, `rgba(80, 220, 140, ${alpha * 0.5})`);
            flash.addColorStop(1, 'rgba(80, 220, 140, 0)');
            ctx.fillStyle = flash;
            ctx.beginPath();
            ctx.arc(s.x, s.y, r, 0, Math.PI * 2);
            ctx.fill();

            // Spark rays
            if (s.life > 0.5) {
                const rayCount = 4;
                const rayLen = r * 1.5;
                ctx.strokeStyle = `rgba(180, 255, 220, ${(s.life - 0.5) * 0.8})`;
                ctx.lineWidth = Math.max(0.5, 1 / zoom);
                ctx.lineCap = 'round';
                for (let i = 0; i < rayCount; i++) {
                    const angle = (i / rayCount) * Math.PI * 2 + s.life * 3;
                    ctx.beginPath();
                    ctx.moveTo(s.x, s.y);
                    ctx.lineTo(s.x + Math.cos(angle) * rayLen, s.y + Math.sin(angle) * rayLen);
                    ctx.stroke();
                }
            }
        }
    }

    // 10. Synaptic connections (edges)
    _drawEdges(ctx, engine, lod, zoom, edgeInView);

    // 11. Edge labels
    if (lod === 'CLOSE') {
        _drawEdgeLabels(ctx, engine, zoom, edgeInView);
    }

    // 12. Dendrites (behind nodes, only at CLOSE/MEDIUM)
    if (lod !== 'FAR') {
        _drawDendrites(ctx, engine, lod, zoom, inView);
    }

    // 13. Neuron cell bodies
    _drawNeurons(ctx, engine, lod, zoom, inView);

    // 14. Node labels
    if (lod !== 'FAR') {
        _drawNodeLabels(ctx, engine, lod, zoom, inView);
    }

    ctx.restore();
}

// ============================================================ dendrites

function _drawDendrites(ctx, engine, lod, zoom, inView) {
    const showBranches = lod === 'CLOSE';

    for (const node of engine.nodes) {
        if (!inView(node.x, node.y, node.radius * 4)) continue;

        const r = node.radius * node.appearProgress;
        if (r < 2) continue;

        const baseColor = _getBaseColor(node, engine);
        const alpha = showBranches ? 0.3 : 0.15;

        ctx.strokeStyle = _withAlpha(baseColor, alpha);
        ctx.lineWidth = Math.max(0.5, 1 / zoom);
        ctx.lineCap = 'round';

        const hash = hashString(node.id);
        const numDendrites = 3 + (hash % 4); // 3-6

        ctx.beginPath();

        for (let i = 0; i < numDendrites; i++) {
            const seed = (hash * 7 + i * 2654435761) >>> 0;
            const angle = (seed % 6283) / 1000;
            const lenFactor = 1.5 + (seed % 150) / 100;
            const len = r * lenFactor;

            const sx = node.x + Math.cos(angle) * r * 0.85;
            const sy = node.y + Math.sin(angle) * r * 0.85;
            const ex = node.x + Math.cos(angle) * (r + len);
            const ey = node.y + Math.sin(angle) * (r + len);

            ctx.moveTo(sx, sy);
            ctx.lineTo(ex, ey);

            if (showBranches) {
                const bLen = len * 0.4;
                const bA1 = angle + 0.4 + (seed % 40) / 100;
                const bA2 = angle - 0.4 - (seed % 40) / 100;

                ctx.moveTo(ex, ey);
                ctx.lineTo(ex + Math.cos(bA1) * bLen, ey + Math.sin(bA1) * bLen);

                ctx.moveTo(ex, ey);
                ctx.lineTo(ex + Math.cos(bA2) * bLen, ey + Math.sin(bA2) * bLen);
            }
        }

        ctx.stroke();

        // Synaptic boutons at dendrite tips
        if (showBranches) {
            ctx.fillStyle = _withAlpha(baseColor, alpha * 0.7);
            for (let i = 0; i < numDendrites; i++) {
                const seed = (hash * 7 + i * 2654435761) >>> 0;
                const angle = (seed % 6283) / 1000;
                const lenFactor = 1.5 + (seed % 150) / 100;
                const len = r * lenFactor;

                const ex = node.x + Math.cos(angle) * (r + len);
                const ey = node.y + Math.sin(angle) * (r + len);
                const dotR = Math.max(1, 1.5 / zoom);

                ctx.beginPath();
                ctx.arc(ex, ey, dotR, 0, Math.PI * 2);
                ctx.fill();
            }
        }
    }
}

// ============================================================ neurons (nodes)

function _drawNeurons(ctx, engine, lod, zoom, inView) {
    const { hoveredNode, selectedNode } = engine;

    for (const node of engine.nodes) {
        if (!inView(node.x, node.y, node.radius + 20)) continue;

        const progress = node.appearProgress;
        if (progress <= 0) continue;

        const r = node.radius * progress;
        const isHovered = node === hoveredNode;
        const isSelected = node === selectedNode;
        const baseColor = _getBaseColor(node, engine);

        // FAR LOD: dots only
        if (lod === 'FAR') {
            ctx.fillStyle = baseColor;
            ctx.globalAlpha = node.isSystem ? 1 : 0.7;
            ctx.beginPath();
            ctx.arc(node.x, node.y, Math.max(r, 2), 0, Math.PI * 2);
            ctx.fill();
            ctx.globalAlpha = 1;
            continue;
        }

        const pulse = 1 + Math.sin(node.pulsePhase) * 0.04;
        const drawR = r * pulse;
        const baseAlpha = node.isSystem ? 1 : 0.75 + progress * 0.25;
        const hoverBoost = isHovered ? 0.2 : 0;

        // Layer 1: Outer glow (aura)
        if (lod === 'CLOSE' || isHovered || isSelected) {
            const outerR = drawR * 2.5;
            const outerGlow = ctx.createRadialGradient(
                node.x, node.y, drawR * 0.5,
                node.x, node.y, outerR
            );
            outerGlow.addColorStop(0, _withAlpha(baseColor, (0.15 + hoverBoost) * progress));
            outerGlow.addColorStop(1, _withAlpha(baseColor, 0));
            ctx.fillStyle = outerGlow;
            ctx.beginPath();
            ctx.arc(node.x, node.y, outerR, 0, Math.PI * 2);
            ctx.fill();
        }

        // Layer 2: Soma glow
        const innerGlow = ctx.createRadialGradient(
            node.x, node.y, 0,
            node.x, node.y, drawR * 1.5
        );
        innerGlow.addColorStop(0, _withAlpha(baseColor, (0.4 + hoverBoost) * baseAlpha));
        innerGlow.addColorStop(1, _withAlpha(baseColor, 0));
        ctx.fillStyle = innerGlow;
        ctx.beginPath();
        ctx.arc(node.x, node.y, drawR * 1.5, 0, Math.PI * 2);
        ctx.fill();

        // Layer 3: Cell membrane (ring)
        ctx.strokeStyle = _withAlpha(baseColor, (0.35 + hoverBoost) * baseAlpha);
        ctx.lineWidth = Math.max(1, 1.5 / zoom);
        ctx.beginPath();
        ctx.arc(node.x, node.y, drawR, 0, Math.PI * 2);
        ctx.stroke();

        // Layer 4: Soma fill (semi-transparent body)
        ctx.fillStyle = _withAlpha(baseColor, (0.15 + hoverBoost * 0.3) * baseAlpha);
        ctx.beginPath();
        ctx.arc(node.x, node.y, drawR, 0, Math.PI * 2);
        ctx.fill();

        // Layer 5: Nucleus (bright center)
        const nucleusR = drawR * 0.35;
        const nucleusGlow = ctx.createRadialGradient(
            node.x, node.y, 0,
            node.x, node.y, nucleusR * 1.5
        );
        nucleusGlow.addColorStop(0, `rgba(255, 255, 255, ${(0.85 + hoverBoost) * baseAlpha})`);
        nucleusGlow.addColorStop(0.4, _withAlpha(baseColor, (0.7 + hoverBoost) * baseAlpha));
        nucleusGlow.addColorStop(1, _withAlpha(baseColor, 0));
        ctx.fillStyle = nucleusGlow;
        ctx.beginPath();
        ctx.arc(node.x, node.y, nucleusR * 1.5, 0, Math.PI * 2);
        ctx.fill();

        // Selection ring
        if (isSelected) {
            ctx.strokeStyle = _withAlpha(COLOR_SELECTED, 0.7);
            ctx.lineWidth = 2.5 / zoom;
            ctx.beginPath();
            ctx.arc(node.x, node.y, drawR + 5 / zoom, 0, Math.PI * 2);
            ctx.stroke();

            // Outer selection pulse
            const selPulse = 1 + Math.sin(Date.now() / 400) * 0.15;
            ctx.strokeStyle = _withAlpha(COLOR_SELECTED, 0.2);
            ctx.lineWidth = 1.5 / zoom;
            ctx.beginPath();
            ctx.arc(node.x, node.y, (drawR + 10 / zoom) * selPulse, 0, Math.PI * 2);
            ctx.stroke();
        }
    }
}

// ============================================================ edges

function _drawEdges(ctx, engine, lod, zoom, edgeInView) {
    for (const edge of engine.edges) {
        if (!edgeInView(edge.source, edge.target)) continue;

        const alpha = lod === 'FAR'
            ? (edge.weight >= 2 ? 0.5 : 0)
            : Math.min(0.2 + edge.weight * 0.15, 0.8) * edge.appearProgress;

        if (alpha <= 0) continue;

        const src = edge.source;
        const tgt = edge.target;
        const lineW = Math.max(0.5, Math.min(edge.weight * 0.8, 3)) / zoom;

        ctx.strokeStyle = `rgba(100, 140, 200, ${alpha})`;
        ctx.lineWidth = lineW;
        ctx.beginPath();
        ctx.moveTo(src.x, src.y);
        ctx.lineTo(tgt.x, tgt.y);
        ctx.stroke();

        // Synaptic terminal dot at target end (CLOSE only)
        if (lod === 'CLOSE' && alpha > 0.3) {
            const dx = tgt.x - src.x;
            const dy = tgt.y - src.y;
            const dist = Math.sqrt(dx * dx + dy * dy) || 1;
            const termX = tgt.x - (dx / dist) * tgt.radius;
            const termY = tgt.y - (dy / dist) * tgt.radius;
            const termR = Math.max(1.5, 2.5 / zoom);

            ctx.fillStyle = `rgba(100, 140, 200, ${alpha * 0.7})`;
            ctx.beginPath();
            ctx.arc(termX, termY, termR, 0, Math.PI * 2);
            ctx.fill();
        }
    }
}

// ============================================================ edge labels

function _drawEdgeLabels(ctx, engine, zoom, edgeInView) {
    const fontSize = Math.max(9, 11 / zoom);
    ctx.font = `${fontSize}px sans-serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillStyle = 'rgba(160, 180, 220, 0.5)';

    for (const edge of engine.edges) {
        if (!edge.relation) continue;
        if (!edgeInView(edge.source, edge.target)) continue;

        const mx = (edge.source.x + edge.target.x) / 2;
        const my = (edge.source.y + edge.target.y) / 2;
        ctx.fillText(edge.relation, mx, my);
    }
}

// ============================================================ node labels

function _drawNodeLabels(ctx, engine, lod, zoom, inView) {
    const fontSize = lod === 'CLOSE'
        ? Math.max(10, 13 / zoom)
        : Math.max(9, 11 / zoom);

    ctx.font = `500 ${fontSize}px 'Inter', sans-serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';

    for (const node of engine.nodes) {
        if (!inView(node.x, node.y, node.radius + 40)) continue;
        if (node.appearProgress <= 0) continue;

        // At MEDIUM, only hide very small unimportant nodes
        if (lod === 'MEDIUM' && !node.isSystem && node.radius < 5 &&
            node !== engine.hoveredNode && node !== engine.selectedNode) {
            continue;
        }

        const alpha = node.isSystem ? 0.95 : 0.65 + node.appearProgress * 0.3;
        const isHighlight = node === engine.hoveredNode || node === engine.selectedNode;

        // Text shadow for readability
        const labelY = node.y + node.radius * node.appearProgress + 5;

        // Draw shadow/outline for contrast
        ctx.fillStyle = `rgba(5, 5, 16, ${alpha * 0.7})`;
        for (const [ox, oy] of [[-1,0],[1,0],[0,-1],[0,1]]) {
            ctx.fillText(node.label, node.x + ox / zoom, labelY + oy / zoom);
        }

        // Draw label
        ctx.fillStyle = isHighlight
            ? `rgba(255, 255, 255, ${Math.min(alpha + 0.3, 1)})`
            : `rgba(210, 220, 240, ${alpha})`;
        ctx.fillText(node.label, node.x, labelY);
    }
}

// ============================================================ cluster hulls

function _drawClusterHulls(ctx, engine, _nodeById, zoom) {
    for (const cluster of engine.clusters) {
        const members = (cluster.members || [])
            .map((id) => _nodeById.get(id))
            .filter(Boolean);
        if (members.length < 3) continue;

        const points = members.map((n) => [n.x, n.y]);
        const hull = convexHull(points);
        if (hull.length < 3) continue;

        const color = getClusterColor(cluster.category || cluster.name || 'default');
        ctx.save();
        ctx.globalAlpha = 0.06;
        ctx.fillStyle = color;
        ctx.beginPath();

        const cx = hull.reduce((s, p) => s + p[0], 0) / hull.length;
        const cy = hull.reduce((s, p) => s + p[1], 0) / hull.length;
        const expand = 30;

        for (let i = 0; i < hull.length; i++) {
            const dx = hull[i][0] - cx;
            const dy = hull[i][1] - cy;
            const d = Math.sqrt(dx * dx + dy * dy) || 1;
            const px = hull[i][0] + (dx / d) * expand;
            const py = hull[i][1] + (dy / d) * expand;
            if (i === 0) ctx.moveTo(px, py);
            else ctx.lineTo(px, py);
        }
        ctx.closePath();
        ctx.fill();

        ctx.globalAlpha = 0.15;
        ctx.strokeStyle = color;
        ctx.lineWidth = 1.5 / zoom;
        ctx.stroke();
        ctx.restore();
    }
}

// ============================================================ helpers

function _getBaseColor(node, engine) {
    if (node === engine.selectedNode) return COLOR_SELECTED;
    if (node.appearProgress < 1) return COLOR_NEW;
    if (node.isSystem) return COLOR_SYSTEM;
    if (node.isLonely) return COLOR_LONELY;
    return getNodeColor(node.id);
}

function _withAlpha(hslColor, alpha) {
    const match = hslColor.match(/hsl\((\d+),\s*(\d+)%,\s*(\d+)%\)/);
    if (match) {
        return `hsla(${match[1]}, ${match[2]}%, ${match[3]}%, ${Math.max(0, Math.min(1, alpha))})`;
    }
    return hslColor;
}

// ============================================================ convex hull (Graham scan)

export function convexHull(points) {
    if (points.length < 3) return points.slice();

    let lowest = 0;
    for (let i = 1; i < points.length; i++) {
        if (points[i][1] < points[lowest][1] ||
            (points[i][1] === points[lowest][1] && points[i][0] < points[lowest][0])) {
            lowest = i;
        }
    }

    const pivot = points[lowest];
    const sorted = points
        .filter((_, i) => i !== lowest)
        .map((p) => ({
            p,
            angle: Math.atan2(p[1] - pivot[1], p[0] - pivot[0]),
            dist: (p[0] - pivot[0]) ** 2 + (p[1] - pivot[1]) ** 2,
        }))
        .sort((a, b) => a.angle - b.angle || a.dist - b.dist)
        .map((o) => o.p);

    const hull = [pivot];
    for (const p of sorted) {
        while (hull.length >= 2) {
            const a = hull[hull.length - 2];
            const b = hull[hull.length - 1];
            const cross = (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]);
            if (cross <= 0) hull.pop();
            else break;
        }
        hull.push(p);
    }
    return hull;
}
