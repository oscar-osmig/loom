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
            <h3>What is Loom?</h3>
            <p>Loom is a community-built symbolic knowledge system that learns from what people teach it through natural conversation.</p>
        </section>

        <section>
            <h3>What Makes It Different</h3>
            <div class="features">
                <div class="feature">
                    <b>Built from contributions</b>
                    <span>Loom starts with minimal built-in knowledge and grows as people add and refine facts.</span>
                </div>
                <div class="feature">
                    <b>Explicit relationships</b>
                    <span>No opaque embeddings. Every idea is stored as a named connection (e.g., <code>dog → is → mammal</code>).</span>
                </div>
                <div class="feature">
                    <b>Attribution built-in</b>
                    <span>Facts, edits, and corrections are tied to the people who contributed them.</span>
                </div>
                <div class="feature">
                    <b>Consensus over time</b>
                    <span>As more people confirm or challenge a fact, its reliability becomes clearer.</span>
                </div>
            </div>
        </section>

        <section>
            <h3>How It Works</h3>
            <div class="features">
                <div class="feature">
                    <b>Knowledge graph</b>
                    <span>Knowledge is stored as a graph of concepts and relationships.</span>
                </div>
                <div class="feature">
                    <b>Natural language parser</b>
                    <span>A parser turns natural language into structured facts.</span>
                </div>
                <div class="feature">
                    <b>Spreading activation</b>
                    <span>Surfaces related concepts during conversation.</span>
                </div>
                <div class="feature">
                    <b>Hebbian strengthening</b>
                    <span>Repeated co-occurrence strengthens connections over time.</span>
                </div>
                <div class="feature">
                    <b>Inference</b>
                    <span>Derives new facts — transitive relationships, inherited properties, analogies.</span>
                </div>
                <div class="feature">
                    <b>Response composer</b>
                    <span>Combines relevant facts into natural language answers.</span>
                </div>
            </div>
        </section>

        <section>
            <h3>Community Layer</h3>
            <div class="features">
                <div class="feature">
                    <b>Corrections</b>
                    <span>Visible and attributed — click the people icon to see who's contributing.</span>
                </div>
                <div class="feature">
                    <b>Contributors</b>
                    <span>Ranked by activity and impact — facts taught, corrections made, messages sent.</span>
                </div>
                <div class="feature">
                    <b>Feedback</b>
                    <span>Rate responses with 👍/👎 to shape how Loom communicates over time.</span>
                </div>
            </div>
        </section>

        <section>
            <h3>The Idea</h3>
            <p>A knowledge system you can talk to, where every fact is transparent, attributed, and open to revision — closer to a conversational Wikipedia than a black-box model.</p>
        </section>

        <section>
            <h3>Ways to Contribute</h3>
            <div class="examples">
                <div class="example"><code>dogs are mammals</code><span>teach a fact</span></div>
                <div class="example"><code>no, that's wrong</code><span>correct a mistake</span></div>
                <div class="example"><code>tell me about cats</code><span>test Loom's knowledge</span></div>
                <div class="example"><code>/visualize</code><span>explore the knowledge graph</span></div>
                <div class="example"><code>/help</code><span>see all commands</span></div>
            </div>
            <p class="hint">You can also paste paragraphs, drag and drop training files, or upload files via the Train button.</p>
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

    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(8px); }
        to { opacity: 1; transform: translateY(0); }
    }
</style>
