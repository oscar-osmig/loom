"""
Loom Web Interface - Flask Backend
A minimalistic chat interface for Loom.
"""

from flask import Flask, request, jsonify, send_file
import os

from loom import Loom

app = Flask(__name__)

# Initialize Loom instance
loom = Loom(verbose=False)
loom.context.set_knowledge_ref(loom.knowledge)


@app.route('/')
def index():
    """Serve the main chat page."""
    return send_file('web_chat.html')


@app.route('/api/chat', methods=['POST'])
def chat():
    """Process a chat message and return response."""
    data = request.json
    message = data.get('message', '').strip()

    if not message:
        return jsonify({'response': 'Please enter a message.', 'type': 'error'})

    # Check for commands (support both /cmd and cmd)
    cmd = message.lower()
    if cmd.startswith('/'):
        cmd = cmd[1:]  # Strip leading slash

    if cmd == 'help':
        return jsonify({
            'response': get_help_text(),
            'type': 'help'
        })

    elif cmd == 'show':
        return jsonify({
            'response': get_knowledge_summary(),
            'type': 'info'
        })

    elif cmd == 'activation':
        return jsonify({
            'response': get_activation_state(),
            'type': 'info'
        })

    elif cmd == 'weights':
        return jsonify({
            'response': get_weights(),
            'type': 'info'
        })

    elif cmd == 'stats':
        return jsonify({
            'response': get_stats(),
            'type': 'info'
        })

    elif cmd == 'forget':
        loom.forget_all()
        return jsonify({
            'response': 'Memory erased. Starting fresh.',
            'type': 'info'
        })

    elif cmd == 'about':
        return jsonify({
            'response': get_about_text(),
            'type': 'info'
        })

    elif cmd.startswith('analogies '):
        concept = cmd[10:].strip()
        return jsonify({
            'response': get_analogies(concept),
            'type': 'info'
        })

    elif cmd.startswith('neuron '):
        node = cmd[7:].strip()
        return jsonify({
            'response': get_neuron_info(node),
            'type': 'info'
        })

    else:
        # Process as natural language
        if '. ' in message or len(message) > 100:
            # Paragraph processing
            result = loom.process_paragraph(message)
            response = f"Processed {result['chunks_processed']} chunks. Theme: {result['theme'] or 'general'}"

            # Add individual responses if verbose
            if result['responses']:
                main_response = result['responses'][0] if result['responses'] else response
                return jsonify({
                    'response': main_response,
                    'type': 'response',
                    'meta': {
                        'chunks': result['chunks_processed'],
                        'facts_added': result['facts_added'],
                        'theme': result['theme']
                    }
                })
        else:
            # Single statement
            response = loom.process_with_activation(message)

        return jsonify({
            'response': response,
            'type': 'response'
        })


def get_about_text():
    """Return about text."""
    return """<b>About Loom</b>

Loom is a symbolic, knowledge-graph-based AI system designed to store, reason about, and expand knowledge in a human-like way.

Unlike statistical or vector-based AI, Loom relies on explicit symbolic representations (neurons and synapses) and logical reasoning mechanisms to understand and interact with the world.

<b>Core Components</b>
• <b>Neurons</b> — Concepts or entities (e.g., 'dogs', 'mammals')
• <b>Synapses</b> — Connections stored as quads: (subject, relation, object, context)
• <b>Graph</b> — Maps neurons to outgoing synapses

<b>Key Features</b>
• Fully explainable chains of inference
• Curiosity-driven discovery of new knowledge
• Context-aware dialogue understanding
• Hebbian learning (connections strengthen with use)
• Spreading activation for related concept discovery
• Property inheritance through category hierarchies
• Temporal awareness for time-sensitive facts"""


def get_help_text():
    """Return help text."""
    return """<b>How Loom Works</b>
Loom learns by creating neurons (concepts) and synapses (connections) from your statements.

<b>Teaching</b>
• "dogs are animals" - categories
• "birds can fly" - abilities
• "rain causes floods" - causation
• "cats have fur" - properties

<b>Asking</b>
• "what are dogs?" - categories
• "can birds fly?" - abilities

<b>Commands</b>
• /about - what is Loom?
• /show - view knowledge summary
• /neuron X - inspect concept X
• /activation - show activation state
• /weights - show strong connections
• /analogies X - find similar concepts
• /stats - storage statistics
• /clear - clear chat history
• /forget - erase memory
• /help - show this help"""


def get_knowledge_summary():
    """Get a summary of current knowledge."""
    knowledge = loom.knowledge
    if not knowledge:
        return "No knowledge stored yet."

    lines = ["<b>Knowledge Graph</b>", ""]
    for node, relations in knowledge.items():
        rel_count = sum(len(v) for v in relations.values())
        lines.append(f"• <b>{node}</b>: {rel_count} connections")

    lines.append(f"\nTotal: {len(knowledge)} neurons")
    return "\n".join(lines)


def get_activation_state():
    """Get current activation state."""
    state = loom.activation.get_state()
    lines = ["<b>Activation State</b>", ""]

    if state['primed']:
        lines.append(f"Primed nodes: {len(state['primed'])}")
        for node in state['primed'][:5]:
            level = loom.activation.get_activation(node)
            lines.append(f"  • {node}: {level:.2f}")
    else:
        lines.append("No primed nodes.")

    lines.append("")
    if state['top_activated']:
        lines.append("Top activated:")
        for node, level in state['top_activated']:
            lines.append(f"  • {node}: {level:.2f}")

    return "\n".join(lines)


def get_weights():
    """Get strong connection weights."""
    strong = loom.get_strong_connections(threshold=1.2)

    if not strong:
        return "No strengthened connections yet."

    lines = ["<b>Strong Connections (Hebbian)</b>", ""]
    for subj, rel, obj, weight in strong[:10]:
        lines.append(f"• {subj} —[{rel}]→ {obj}: <b>{weight:.2f}</b>")

    return "\n".join(lines)


def get_stats():
    """Get storage statistics."""
    stats = loom.get_stats()
    storage_type = "MongoDB" if loom.use_mongo else "JSON File"

    return f"""<b>Storage Statistics</b>

Storage: {storage_type}
Neurons: {stats['nodes']}
Synapses: {stats['facts']}
Procedures: {stats['procedures']}
Inferences: {stats['inferences']}
Conflicts: {stats['conflicts']}"""


def get_analogies(concept):
    """Find analogies for a concept."""
    analogies = loom.inference.find_analogies(concept)

    if not analogies:
        return f"No analogies found for '{concept}'."

    lines = [f"<b>Analogies for '{concept}'</b>", ""]
    for analog, sim in analogies:
        lines.append(f"• {analog}: {sim:.0%} similar")

    return "\n".join(lines)


def get_neuron_info(node):
    """Get information about a specific neuron."""
    from loom.normalizer import normalize
    node_norm = normalize(node)

    if node_norm not in loom.knowledge:
        return f"Neuron '{node}' not found."

    relations = loom.knowledge[node_norm]
    lines = [f"<b>Neuron: {node}</b>", ""]

    for rel, targets in relations.items():
        for target in targets:
            weight = loom.get_connection_weight(node_norm, rel, target)
            weight_str = f" ({weight:.1f})" if weight > 1.0 else ""
            lines.append(f"• —[{rel}]→ {target}{weight_str}")

    return "\n".join(lines)


# ==================== SPEECH ENDPOINTS ====================

@app.route('/api/speech', methods=['POST'])
def process_speech():
    """
    Process speech input (text with speech metadata).

    Expected JSON:
    {
        "text": "The transcribed text",
        "speaker_id": "optional_speaker_id",
        "confidence": 0.95  // ASR confidence 0.0-1.0
    }
    """
    data = request.json
    text = data.get('text', '').strip()
    speaker_id = data.get('speaker_id')
    confidence = data.get('confidence', 1.0)

    if not text:
        return jsonify({'error': 'No text provided', 'type': 'error'}), 400

    try:
        response = loom.process_speech(text, speaker_id=speaker_id, confidence=confidence)
        return jsonify({
            'response': response,
            'type': 'speech_response',
            'source': {
                'type': 'speech',
                'speaker_id': speaker_id,
                'confidence': confidence
            }
        })
    except Exception as e:
        return jsonify({'error': str(e), 'type': 'error'}), 500


@app.route('/api/speech/audio', methods=['POST'])
def process_audio():
    """
    Process an audio file directly.

    Expects multipart form data with 'audio' file.
    Optional: 'backend' parameter (whisper_local, whisper_api, vosk, mock)
    """
    if 'audio' not in request.files:
        return jsonify({'error': 'No audio file provided', 'type': 'error'}), 400

    audio_file = request.files['audio']
    backend = request.form.get('backend', 'mock')

    # Save temporarily
    import tempfile
    with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp:
        audio_file.save(tmp.name)
        tmp_path = tmp.name

    try:
        result = loom.process_audio(tmp_path, backend=backend)
        return jsonify({
            'type': 'audio_response',
            'transcript': result.get('transcript', {}),
            'segments_processed': result.get('segments_processed', 0),
            'responses': result.get('responses', [])
        })
    except Exception as e:
        return jsonify({'error': str(e), 'type': 'error'}), 500
    finally:
        # Clean up temp file
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@app.route('/api/questions', methods=['GET'])
def get_questions():
    """Get curiosity engine questions."""
    loom.run_curiosity_cycle()
    questions = loom.get_questions(5)
    return jsonify({
        'questions': questions,
        'count': len(questions),
        'type': 'questions'
    })


@app.route('/api/graph', methods=['GET'])
def get_graph():
    """Get knowledge graph data for visualization."""
    knowledge = loom.knowledge

    nodes = []
    edges = []
    node_ids = set()
    lonely_node_ids = set()

    # Get discovery data first to identify lonely neurons
    discovery_data = {}
    if hasattr(loom, 'discovery_engine'):
        discovery_data = loom.discovery_engine.get_visualization_data()
        for lonely in discovery_data.get('lonely_neurons', []):
            lonely_node_ids.add(lonely['id'])

    # Create nodes from knowledge graph with full relation data
    for node_id, relations in knowledge.items():
        connection_count = sum(len(targets) for targets in relations.values())
        # Count incoming connections too
        incoming = 0
        for other_id, other_rels in knowledge.items():
            if other_id != node_id:
                for targets in other_rels.values():
                    if node_id in targets:
                        incoming += 1

        nodes.append({
            'id': node_id,
            'label': node_id.replace('_', ' ').title(),
            'connections': connection_count + incoming,
            'outgoing': connection_count,
            'incoming': incoming,
            'is_lonely': node_id in lonely_node_ids,
            'relations': {rel: list(targets) for rel, targets in relations.items()}
        })
        node_ids.add(node_id)

    # Create edges from relations
    for source_id, relations in knowledge.items():
        for relation, targets in relations.items():
            for target in targets:
                # Get connection weight if available
                weight = loom.get_connection_weight(source_id, relation, target)

                # Only include edge if target exists as a node
                if target in node_ids:
                    edges.append({
                        'source': source_id,
                        'target': target,
                        'relation': relation,
                        'weight': weight
                    })

    # Get discovery data
    co_occurrences = []
    patterns = []
    potential_edges = []
    clusters = []
    transitive_gaps = []
    missing_properties = []

    if hasattr(loom, 'discovery_engine'):
        # Get co-occurrence data
        for (e1, e2), count in loom.discovery_engine._co_occurrence.items():
            if count >= 2 and e1 in node_ids and e2 in node_ids:
                co_occurrences.append({
                    'entity1': e1,
                    'entity2': e2,
                    'count': count
                })

        # Get discovered patterns (potential new connections)
        for name, pattern in loom.discovery_engine._patterns.items():
            if pattern.confidence >= 0.5:
                patterns.append({
                    'name': name,
                    'type': pattern.pattern_type,
                    'confidence': pattern.confidence,
                    'entities': list(pattern.entities)[:5]
                })

        # Get suggested connections as potential edges
        for conn in discovery_data.get('suggested_connections', []):
            if conn['source'] in node_ids and conn['target'] in node_ids:
                potential_edges.append({
                    'source': conn['source'],
                    'target': conn['target'],
                    'relation': conn['type'],
                    'confidence': conn['confidence']
                })

        # Get clusters
        clusters = discovery_data.get('clusters', [])

        # Get transitive gaps
        for gap in discovery_data.get('transitive_gaps', []):
            if gap['source'] in node_ids and gap['target'] in node_ids:
                transitive_gaps.append(gap)

        # Get missing properties
        missing_properties = discovery_data.get('missing_properties', [])

    return jsonify({
        'nodes': nodes,
        'edges': edges,
        'co_occurrences': co_occurrences,
        'patterns': patterns,
        'potential_edges': potential_edges,
        'clusters': clusters,
        'transitive_gaps': transitive_gaps,
        'missing_properties': missing_properties,
        'lonely_neurons': discovery_data.get('lonely_neurons', []),
        'statistics': discovery_data.get('statistics', {})
    })


if __name__ == '__main__':
    print("\n  Loom Web Interface")
    print("  Open http://localhost:5000 in your browser\n")
    app.run(debug=True, port=5000)
