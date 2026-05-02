/**
 * graph-interaction.js
 * Attaches mouse and touch event handlers to the graph canvas.
 * Returns a cleanup function that removes all listeners.
 */

/**
 * Attach interaction handlers to the canvas.
 *
 * @param {HTMLCanvasElement} canvas
 * @param {import('./graph-engine.js').GraphEngine} engine
 * @param {{ onNodeSelect?: (node: Object|null) => void, onNodeHover?: (node: Object|null) => void }} callbacks
 * @returns {() => void} Cleanup function that removes all listeners.
 */
export function attachInteractions(canvas, engine, callbacks = {}) {
    const { onNodeSelect, onNodeHover, onContextMenu } = callbacks;

    // --- state ---
    let isPanning = false;
    let panStartX = 0;
    let panStartY = 0;
    let panStartPanX = 0;
    let panStartPanY = 0;
    let dragStartX = 0;
    let dragStartY = 0;
    let didDrag = false;

    // --- touch state ---
    let lastTouches = null;
    let lastPinchDist = 0;

    // ============================================================ mouse

    function onMouseDown(e) {
        const rect = canvas.getBoundingClientRect();
        const sx = e.clientX - rect.left;
        const sy = e.clientY - rect.top;
        const world = engine.screenToWorld(sx, sy);
        const node = engine.getNodeAt(world.x, world.y);

        dragStartX = sx;
        dragStartY = sy;
        didDrag = false;

        if (node) {
            engine.draggedNode = node;
        } else {
            isPanning = true;
            panStartX = sx;
            panStartY = sy;
            panStartPanX = engine.panX;
            panStartPanY = engine.panY;
        }
    }

    function onMouseMove(e) {
        const rect = canvas.getBoundingClientRect();
        const sx = e.clientX - rect.left;
        const sy = e.clientY - rect.top;

        if (engine.draggedNode) {
            const world = engine.screenToWorld(sx, sy);
            engine.draggedNode.x = world.x;
            engine.draggedNode.y = world.y;
            engine.draggedNode.vx = 0;
            engine.draggedNode.vy = 0;
            didDrag = true;
            return;
        }

        if (isPanning) {
            const dx = sx - panStartX;
            const dy = sy - panStartY;
            engine.panX = panStartPanX + dx;
            engine.panY = panStartPanY + dy;
            if (Math.abs(dx) > 3 || Math.abs(dy) > 3) didDrag = true;
            return;
        }

        // Hover detection
        const world = engine.screenToWorld(sx, sy);
        const hovered = engine.getNodeAt(world.x, world.y);
        if (hovered !== engine.hoveredNode) {
            engine.hoveredNode = hovered;
            canvas.style.cursor = hovered ? 'pointer' : 'default';
            if (onNodeHover) onNodeHover(hovered);
        }
    }

    function onMouseUp(e) {
        if (!didDrag) {
            const rect = canvas.getBoundingClientRect();
            const sx = e.clientX - rect.left;
            const sy = e.clientY - rect.top;
            const world = engine.screenToWorld(sx, sy);
            const node = engine.getNodeAt(world.x, world.y);
            engine.selectedNode = node;
            if (onNodeSelect) onNodeSelect(node);
        }
        engine.draggedNode = null;
        isPanning = false;
    }

    function onWheel(e) {
        e.preventDefault();

        const rect = canvas.getBoundingClientRect();
        const sx = e.clientX - rect.left;
        const sy = e.clientY - rect.top;

        const zoomFactor = e.deltaY < 0 ? 1.1 : 1 / 1.1;
        const newZoom = Math.max(0.02, Math.min(10, engine.zoom * zoomFactor));

        // Zoom toward cursor position
        const worldBefore = engine.screenToWorld(sx, sy);
        engine.zoom = newZoom;
        const worldAfter = engine.screenToWorld(sx, sy);

        engine.panX += (worldAfter.x - worldBefore.x) * engine.zoom;
        engine.panY += (worldAfter.y - worldBefore.y) * engine.zoom;
    }

    function onDblClick(e) {
        const rect = canvas.getBoundingClientRect();
        const sx = e.clientX - rect.left;
        const sy = e.clientY - rect.top;
        const world = engine.screenToWorld(sx, sy);
        const node = engine.getNodeAt(world.x, world.y);

        engine.selectedNode = node;
        if (onNodeSelect) onNodeSelect(node);
    }

    function onMouseLeave() {
        if (engine.hoveredNode) {
            engine.hoveredNode = null;
            canvas.style.cursor = 'default';
            if (onNodeHover) onNodeHover(null);
        }
        // Do not cancel drag/pan here so that returning to canvas resumes
    }

    // ============================================================ touch

    function getTouchDistance(t1, t2) {
        const dx = t1.clientX - t2.clientX;
        const dy = t1.clientY - t2.clientY;
        return Math.sqrt(dx * dx + dy * dy);
    }

    function getTouchCenter(t1, t2) {
        return {
            x: (t1.clientX + t2.clientX) / 2,
            y: (t1.clientY + t2.clientY) / 2,
        };
    }

    function onTouchStart(e) {
        e.preventDefault();

        if (e.touches.length === 1) {
            // Single finger: treat like mousedown
            const touch = e.touches[0];
            const rect = canvas.getBoundingClientRect();
            const sx = touch.clientX - rect.left;
            const sy = touch.clientY - rect.top;
            const world = engine.screenToWorld(sx, sy);
            const node = engine.getNodeAt(world.x, world.y);

            dragStartX = sx;
            dragStartY = sy;
            didDrag = false;

            if (node) {
                engine.draggedNode = node;
            } else {
                isPanning = true;
                panStartX = sx;
                panStartY = sy;
                panStartPanX = engine.panX;
                panStartPanY = engine.panY;
            }
        } else if (e.touches.length === 2) {
            // Pinch start
            engine.draggedNode = null;
            isPanning = false;
            lastPinchDist = getTouchDistance(e.touches[0], e.touches[1]);
            lastTouches = [e.touches[0], e.touches[1]];
        }
    }

    function onTouchMove(e) {
        e.preventDefault();

        if (e.touches.length === 1 && !lastTouches) {
            const touch = e.touches[0];
            const rect = canvas.getBoundingClientRect();
            const sx = touch.clientX - rect.left;
            const sy = touch.clientY - rect.top;

            if (engine.draggedNode) {
                const world = engine.screenToWorld(sx, sy);
                engine.draggedNode.x = world.x;
                engine.draggedNode.y = world.y;
                engine.draggedNode.vx = 0;
                engine.draggedNode.vy = 0;
                didDrag = true;
            } else if (isPanning) {
                const dx = sx - panStartX;
                const dy = sy - panStartY;
                engine.panX = panStartPanX + dx;
                engine.panY = panStartPanY + dy;
                if (Math.abs(dx) > 3 || Math.abs(dy) > 3) didDrag = true;
            }
        } else if (e.touches.length === 2) {
            // Pinch zoom
            const dist = getTouchDistance(e.touches[0], e.touches[1]);
            const center = getTouchCenter(e.touches[0], e.touches[1]);
            const rect = canvas.getBoundingClientRect();
            const sx = center.x - rect.left;
            const sy = center.y - rect.top;

            if (lastPinchDist > 0) {
                const scale = dist / lastPinchDist;
                const newZoom = Math.max(0.02, Math.min(10, engine.zoom * scale));

                const worldBefore = engine.screenToWorld(sx, sy);
                engine.zoom = newZoom;
                const worldAfter = engine.screenToWorld(sx, sy);

                engine.panX += (worldAfter.x - worldBefore.x) * engine.zoom;
                engine.panY += (worldAfter.y - worldBefore.y) * engine.zoom;
            }

            // Also pan with two fingers
            if (lastTouches) {
                const prevCenter = getTouchCenter(lastTouches[0], lastTouches[1]);
                const dx = center.x - prevCenter.x;
                const dy = center.y - prevCenter.y;
                engine.panX += dx;
                engine.panY += dy;
            }

            lastPinchDist = dist;
            lastTouches = [e.touches[0], e.touches[1]];
        }
    }

    function onTouchEnd(e) {
        if (e.touches.length < 2) {
            lastTouches = null;
            lastPinchDist = 0;
        }

        if (e.touches.length === 0) {
            // Check for tap (not drag) to select
            if (!didDrag && engine.draggedNode === null) {
                // Emulate dblclick with a quick-tap timeout could be added,
                // but for now single-tap selects
                const touch = e.changedTouches[0];
                if (touch) {
                    const rect = canvas.getBoundingClientRect();
                    const sx = touch.clientX - rect.left;
                    const sy = touch.clientY - rect.top;
                    const world = engine.screenToWorld(sx, sy);
                    const node = engine.getNodeAt(world.x, world.y);
                    engine.selectedNode = node;
                    if (onNodeSelect) onNodeSelect(node);
                }
            }

            engine.draggedNode = null;
            isPanning = false;
        }
    }

    // ============================================================ context menu

    function onRightClick(e) {
        e.preventDefault();
        const rect = canvas.getBoundingClientRect();
        const sx = e.clientX - rect.left;
        const sy = e.clientY - rect.top;
        const world = engine.screenToWorld(sx, sy);
        const node = engine.getNodeAt(world.x, world.y);

        if (node && onContextMenu) {
            onContextMenu(node, { x: e.clientX, y: e.clientY });
        }
    }

    // ============================================================ attach

    canvas.addEventListener('mousedown', onMouseDown);
    canvas.addEventListener('mousemove', onMouseMove);
    canvas.addEventListener('mouseup', onMouseUp);
    canvas.addEventListener('wheel', onWheel, { passive: false });
    canvas.addEventListener('dblclick', onDblClick);
    canvas.addEventListener('contextmenu', onRightClick);
    canvas.addEventListener('mouseleave', onMouseLeave);

    canvas.addEventListener('touchstart', onTouchStart, { passive: false });
    canvas.addEventListener('touchmove', onTouchMove, { passive: false });
    canvas.addEventListener('touchend', onTouchEnd);

    // ============================================================ cleanup

    return function cleanup() {
        canvas.removeEventListener('mousedown', onMouseDown);
        canvas.removeEventListener('mousemove', onMouseMove);
        canvas.removeEventListener('mouseup', onMouseUp);
        canvas.removeEventListener('wheel', onWheel);
        canvas.removeEventListener('dblclick', onDblClick);
        canvas.removeEventListener('contextmenu', onRightClick);
        canvas.removeEventListener('mouseleave', onMouseLeave);

        canvas.removeEventListener('touchstart', onTouchStart);
        canvas.removeEventListener('touchmove', onTouchMove);
        canvas.removeEventListener('touchend', onTouchEnd);
    };
}
