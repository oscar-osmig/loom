<script>
    import { setAboutOpen } from '../stores/ui.svelte.js';
    function close() {
        setAboutOpen(false);
    }
</script>

<div class="about">
    <button class="close-btn" onclick={close} aria-label="Close about">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
        </svg>
    </button>

    <div class="about-header">
        <img src="/loom.png" alt="Loom" class="about-logo" />
        <h2>Loom</h2>
        <p class="subtitle">Knowledge Weaver</p>
    </div>

    <div class="about-body">
        <section>
            <h3>How Loom Works</h3>
            <p>Loom learns by creating <b>neurons</b> (concepts) and <b>synapses</b> (connections) from your statements. It builds a knowledge graph through natural conversation — no ML frameworks (PyTorch, scikit-learn, TensorFlow), no vector embeddings (Word2Vec, BERT). Every concept is a named node with explicit, traceable relationships — pure symbolic reasoning.</p>
        </section>

        <section>
            <h3>Teaching</h3>
            <div class="examples">
                <div class="example"><code>dogs are animals</code><span>categories</span></div>
                <div class="example"><code>birds can fly</code><span>abilities</span></div>
                <div class="example"><code>cats have fur</code><span>properties</span></div>
                <div class="example"><code>rain causes floods</code><span>causation</span></div>
                <div class="example"><code>no, that's wrong</code><span>corrections</span></div>
                <div class="example"><code>only when it's warm</code><span>constraints</span></div>
            </div>
            <p class="hint">You can also paste entire paragraphs. Loom will break them into chunks, find discourse relations, and build connections across sentences.</p>
        </section>

        <section>
            <h3>Asking</h3>
            <div class="examples">
                <div class="example"><code>what are dogs?</code><span>categories</span></div>
                <div class="example"><code>can birds fly?</code><span>abilities</span></div>
                <div class="example"><code>what does rain cause?</code><span>effects</span></div>
            </div>
        </section>

        <section>
            <h3>Commands</h3>
            <p class="hint">All commands use the <code>/</code> prefix.</p>
            <div class="commands">
                <div class="cmd"><code>/show</code><span>View knowledge summary</span></div>
                <div class="cmd"><code>/neuron X</code><span>Inspect concept X</span></div>
                <div class="cmd"><code>/frame X</code><span>Show concept frame (attribute slots)</span></div>
                <div class="cmd"><code>/bridges [X]</code><span>Show attribute bridges between concepts</span></div>
                <div class="cmd"><code>/clusters</code><span>Show emergent category clusters</span></div>
                <div class="cmd"><code>/activation</code><span>Show activation state</span></div>
                <div class="cmd"><code>/weights</code><span>Show strong connections</span></div>
                <div class="cmd"><code>/analogies X</code><span>Find similar concepts</span></div>
                <div class="cmd"><code>/stats</code><span>Storage statistics</span></div>
                <div class="cmd"><code>/clear</code><span>Clear chat history</span></div>
                <div class="cmd"><code>/forget</code><span>Erase your own facts</span></div>
                <div class="cmd"><code>/help</code><span>Show quick help</span></div>
            </div>
        </section>

        <section>
            <h3>Training Loom</h3>
            <p>There are several ways to teach Loom new knowledge:</p>
            <div class="features">
                <div class="feature">
                    <b>Chat</b>
                    <span>Just type facts in natural language. <code>dogs are animals</code>, <code>water boils at 100 degrees</code> — Loom extracts the relationships automatically.</span>
                </div>
                <div class="feature">
                    <b>Paragraphs</b>
                    <span>Paste entire paragraphs or articles. Loom splits them into sentences, detects discourse relations (cause, contrast, elaboration), and builds cross-sentence connections.</span>
                </div>
                <div class="feature">
                    <b>File Upload</b>
                    <span>Drag and drop <code>.json</code> or <code>.txt</code> files onto the chat, or use the Train button. JSON files should contain an array of fact strings. Text files are processed line by line. Uploaded files are saved in your browser so you can review and edit them.</span>
                </div>
                <div class="feature">
                    <b>Corrections</b>
                    <span>Say <code>no, that's wrong</code> or <code>actually, cats are mammals</code> to correct existing knowledge. Loom tracks provenance and updates accordingly.</span>
                </div>
            </div>
            <p class="hint">The more you teach, the more Loom can infer on its own through transitive chains, property inheritance, and analogy detection.</p>
        </section>

        <section>
            <h3>Under the Hood</h3>
            <div class="features">
                <div class="feature">
                    <b>Spreading Activation</b>
                    <span>Mentioned concepts activate nearby nodes, surfacing related knowledge automatically.</span>
                </div>
                <div class="feature">
                    <b>Hebbian Learning</b>
                    <span>Connections strengthen with use — "cells that fire together wire together."</span>
                </div>
                <div class="feature">
                    <b>Inference Engine</b>
                    <span>Transitive chaining, property inheritance, and analogy detection run in the background.</span>
                </div>
                <div class="feature">
                    <b>Discourse Parsing</b>
                    <span>Multi-sentence text is chunked and analyzed for causal, contrast, and elaboration relations.</span>
                </div>
            </div>
        </section>

    </div>
</div>

<style>
    .about {
        flex: 1;
        overflow-y: auto;
        padding: 2rem 1.5rem;
        position: relative;
        animation: fadeIn 0.3s ease;
    }

    .close-btn {
        position: absolute;
        top: 1rem;
        right: 0.5rem;
        background: var(--bg-secondary);
        border: 1px solid var(--border);
        color: var(--text-muted);
        cursor: pointer;
        padding: 0.4rem;
        border-radius: 8px;
        transition: all 0.2s;
        display: flex;
        align-items: center;
        z-index: 1;
    }

    .close-btn:hover {
        color: var(--text-primary);
        border-color: var(--accent);
    }

    .about-header {
        text-align: center;
        margin-bottom: 2rem;
    }

    .about-logo {
        width: 64px;
        height: 64px;
        border-radius: 16px;
        margin-bottom: 0.75rem;
    }

    .about-header h2 {
        font-size: 1.5rem;
        font-weight: 700;
    }

    .subtitle {
        color: var(--text-muted);
        font-size: 0.875rem;
        margin-top: 0.25rem;
    }

    .about-body {
        max-width: 560px;
        margin: 0 auto;
        display: flex;
        flex-direction: column;
        gap: 1.75rem;
    }

    section h3 {
        font-size: 0.9375rem;
        font-weight: 600;
        color: var(--accent-hover);
        margin-bottom: 0.625rem;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    section p {
        color: var(--text-secondary);
        font-size: 0.875rem;
        line-height: 1.7;
    }

    section p :global(b) {
        color: var(--text-primary);
        font-weight: 600;
    }

    .hint {
        margin-top: 0.5rem;
        font-size: 0.8125rem !important;
        color: var(--text-muted) !important;
    }

    .hint code {
        background: var(--bg-tertiary);
        padding: 0.1rem 0.35rem;
        border-radius: 4px;
        font-size: 0.8125rem;
    }

    .examples, .commands {
        display: flex;
        flex-direction: column;
        gap: 0.375rem;
    }

    .example, .cmd {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        padding: 0.4rem 0.625rem;
        border-radius: 8px;
        background: var(--bg-secondary);
    }

    .example code, .cmd code {
        color: var(--accent-hover);
        font-size: 0.8125rem;
        font-weight: 500;
        white-space: nowrap;
        min-width: 140px;
    }

    .example span, .cmd span {
        color: var(--text-muted);
        font-size: 0.8125rem;
    }

    .features {
        display: flex;
        flex-direction: column;
        gap: 0.625rem;
    }

    .feature {
        padding: 0.75rem 1rem;
        background: var(--bg-secondary);
        border-radius: 10px;
        border: 1px solid var(--border);
    }

    .feature b {
        display: block;
        font-size: 0.875rem;
        color: var(--text-primary);
        margin-bottom: 0.25rem;
    }

    .feature span {
        font-size: 0.8125rem;
        color: var(--text-muted);
        line-height: 1.5;
    }

    .style-stats {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 0.625rem;
        margin: 0.875rem 0;
    }

    .stat-box {
        display: flex;
        flex-direction: column;
        align-items: center;
        padding: 0.875rem 0.5rem;
        background: var(--bg-secondary);
        border: 1px solid var(--border);
        border-radius: 10px;
        text-align: center;
    }

    .stat-value {
        font-size: 1.375rem;
        font-weight: 700;
        color: var(--accent-hover);
        font-variant-numeric: tabular-nums;
    }

    .stat-label {
        font-size: 0.6875rem;
        color: var(--text-muted);
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-top: 0.25rem;
    }

    .patterns-list {
        display: flex;
        flex-direction: column;
        gap: 0.25rem;
        margin-top: 1rem;
    }

    .patterns-title {
        font-size: 0.75rem;
        color: var(--text-muted);
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 0.375rem;
    }

    .pattern-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 0.375rem 0.625rem;
        background: var(--bg-secondary);
        border-radius: 6px;
    }

    .pattern-label {
        font-size: 0.8125rem;
        color: var(--accent-hover);
        background: transparent;
        padding: 0;
    }

    .pattern-feedback {
        display: inline-flex;
        gap: 0.5rem;
        font-size: 0.75rem;
    }

    .like-count { color: var(--success); }
    .dislike-count { color: var(--error); }
    .neutral { color: var(--text-muted); font-style: italic; }

    .pattern-count {
        font-size: 0.75rem;
        color: var(--text-muted);
    }

    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(8px); }
        to { opacity: 1; transform: translateY(0); }
    }
</style>
