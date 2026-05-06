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
            <p>Loom is a community-built symbolic knowledge system. It learns from what people teach it through natural conversation — structured reasoning over facts you can see and revise.</p>
        </section>

        <section>
            <h3>What Makes It Different</h3>
            <div class="features">
                <div class="feature">
                    <b>Pure symbolic reasoning</b>
                    <span>Every fact is a transparent triple (e.g., <code>dog → is → mammal</code>). No black-box models or hidden weights.</span>
                </div>
                <div class="feature">
                    <b>Community-driven knowledge</b>
                    <span>Loom starts nearly empty and grows as people teach, correct, and refine facts together.</span>
                </div>
                <div class="feature">
                    <b>Full attribution</b>
                    <span>Every fact, correction, and edit is tied to the person who contributed it.</span>
                </div>
                <div class="feature">
                    <b>Open to revision</b>
                    <span>Anyone can correct mistakes. Corrections are tracked and visible, building consensus over time.</span>
                </div>
            </div>
        </section>

        <section>
            <h3>How It Works</h3>
            <div class="features">
                <div class="feature">
                    <b>Knowledge graph</b>
                    <span>Facts are stored as neurons (concepts) connected by synapses (relationships) — visualize them live.</span>
                </div>
                <div class="feature">
                    <b>Natural language understanding</b>
                    <span>Loom parses your sentences into structured facts, handles paragraphs, lists, corrections, and questions.</span>
                </div>
                <div class="feature">
                    <b>Inference engine</b>
                    <span>Derives new facts through transitive chains, property inheritance, and analogy detection.</span>
                </div>
                <div class="feature">
                    <b>Spreading activation</b>
                    <span>Related concepts light up during conversation, surfacing connections you might not expect.</span>
                </div>
                <div class="feature">
                    <b>Hebbian learning</b>
                    <span>Connections that fire together strengthen over time — unused ones gradually fade.</span>
                </div>
            </div>
        </section>

        <section>
            <h3>Your Tools</h3>
            <div class="features">
                <div class="feature">
                    <b>Like & dislike responses</b>
                    <span>Every Loom response shows thumbs-up / thumbs-down buttons. Your ratings teach Loom which response styles work best and help improve future answers.</span>
                </div>
                <div class="feature">
                    <b>Edit Loom's answers</b>
                    <span>Click the pen icon above any response to rewrite it. Your edit is saved and used to improve how Loom communicates — think of it as coaching.</span>
                </div>
                <div class="feature">
                    <b>Instances</b>
                    <span>The shield icon in the chat lets you switch between Loom instances. <b>General</b> is the shared community brain. Create your own private instances to experiment, study, or build a personal knowledge base — you can have as many as you like.</span>
                </div>
                <div class="feature">
                    <b>Copy conversation</b>
                    <span>Right-click the chat area (when no text is selected) to copy the entire conversation to your clipboard as clean text.</span>
                </div>
                <div class="feature">
                    <b>File training</b>
                    <span>Drag-and-drop or use the Train button to upload <code>.txt</code> or <code>.json</code> files. Loom parses them into facts automatically. Uploaded files are viewable in the Files sidebar.</span>
                </div>
            </div>
        </section>

        <section>
            <h3>Community</h3>
            <div class="features">
                <div class="feature">
                    <b>Collaborator leaderboard</b>
                    <span>See who's contributing the most — ranked by neurons created, corrections made, and messages sent.</span>
                </div>
                <div class="feature">
                    <b>Style settings</b>
                    <span>Customize how Loom responds — adjust verbosity, formality, and detail level from the settings menu to match your preference.</span>
                </div>
            </div>
        </section>

        <section>
            <h3>Getting Started</h3>
            <div class="examples">
                <div class="example"><code>dogs are mammals</code><span>teach a fact</span></div>
                <div class="example"><code>cats have whiskers</code><span>add a property</span></div>
                <div class="example"><code>actually, X is Y</code><span>correct a mistake</span></div>
                <div class="example"><code>what are dogs?</code><span>ask a question</span></div>
                <div class="example"><code>/visualize</code><span>explore the graph</span></div>
                <div class="example"><code>/help</code><span>see all commands</span></div>
            </div>
            <p class="hint">Type <code>/</code> to see command autocomplete. You can also paste paragraphs, drag and drop training files, or upload via the Train button.</p>
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

    .examples {
        display: flex;
        flex-direction: column;
        gap: 0.375rem;
    }

    .example {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        padding: 0.4rem 0.625rem;
        border-radius: 8px;
        background: var(--bg-secondary);
    }

    .example code {
        color: var(--accent-hover);
        font-size: 0.8125rem;
        font-weight: 500;
        white-space: nowrap;
        min-width: 140px;
    }

    .example span {
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
