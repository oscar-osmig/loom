"""
Loom Web Interface - Flask Backend
A minimalistic chat interface for Loom.
"""

from flask import Flask, request, jsonify, send_file
import json
import os

from loom import Loom

app = Flask(__name__)

# Initialize Loom instance with MongoDB
loom = Loom(verbose=False, use_mongo=True, mongo_uri="mongodb://loom:Coltkhan22!@localhost:27017/loom_memory?authSource=loom_memory", database_name="loom_memory")
loom.context.set_knowledge_ref(loom.knowledge)


@app.route('/')
def index():
    """Serve the main chat page."""
    return send_file('web_chat.html')


@app.route('/loom.png')
def loom_icon():
    """Serve the Loom icon."""
    return send_file('loom.png', mimetype='image/png')


@app.route('/api/upload-training', methods=['POST'])
def upload_training():
    """Upload and validate a JSON or TXT training file."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided.'}), 400

    file = request.files['file']
    filename = file.filename or ''

    if not filename.lower().endswith(('.json', '.txt')):
        return jsonify({
            'error': 'Unsupported file type. Only .json and .txt files are accepted.'
        }), 400

    try:
        content = file.read().decode('utf-8')
    except UnicodeDecodeError:
        return jsonify({'error': 'File must be UTF-8 encoded text.'}), 400

    if not content.strip():
        return jsonify({'error': 'File is empty.'}), 400

    count = 0
    errors = []

    if filename.lower().endswith('.json'):
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            return jsonify({
                'error': f'Invalid JSON syntax: {e.msg} at line {e.lineno}.'
            }), 400

        if not isinstance(data, list):
            return jsonify({
                'error': 'JSON must be an array of objects. Expected: [{"subject": "...", "relation": "...", "object": "..."}, ...]'
            }), 400

        if not data:
            return jsonify({'error': 'JSON array is empty.'}), 400

        # Validate structure
        for i, item in enumerate(data):
            if not isinstance(item, dict):
                errors.append(f'Item {i+1} is not an object.')
                continue
            subj = item.get('subject', item.get('s', ''))
            rel = item.get('relation', item.get('r', ''))
            obj = item.get('object', item.get('o', ''))
            if not subj or not rel or not obj:
                missing = []
                if not subj: missing.append('subject')
                if not rel: missing.append('relation')
                if not obj: missing.append('object')
                errors.append(f'Item {i+1} missing: {", ".join(missing)}.')
                continue
            loom.add_fact(subj, rel, obj)
            count += 1

    else:  # .txt
        lines = content.strip().split('\n')
        for i, line in enumerate(lines):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '|' in line:
                parts = [p.strip() for p in line.split('|')]
            else:
                parts = [p.strip() for p in line.split(',')]
            if len(parts) < 3:
                errors.append(f'Line {i+1}: expected "subject | relation | object" but got {len(parts)} parts.')
                continue
            if not parts[0] or not parts[1] or not parts[2]:
                errors.append(f'Line {i+1}: empty field.')
                continue
            loom.add_fact(parts[0], parts[1], parts[2])
            count += 1

    if errors and count == 0:
        return jsonify({
            'error': f'No valid facts found. {len(errors)} errors:\n' + '\n'.join(errors[:5])
        }), 400

    result = {'loaded': count, 'filename': filename}
    if errors:
        result['warnings'] = errors[:5]
        result['warning_count'] = len(errors)

    return jsonify(result)


@app.route('/api/chat', methods=['POST'])
def chat():
    """Process a chat message and return response."""
    data = request.json
    message = data.get('message', '').strip()

    if not message:
        return jsonify({'response': 'Please enter a message.', 'type': 'error'})

    # Commands require / prefix
    if message.startswith('/'):
        cmd = message[1:].lower().strip()

        if cmd == 'help':
            return jsonify({'response': get_help_text(), 'type': 'help'})

        elif cmd == 'show':
            return jsonify({'response': get_knowledge_summary(), 'type': 'info'})

        elif cmd == 'activation':
            return jsonify({'response': get_activation_state(), 'type': 'info'})

        elif cmd == 'weights':
            return jsonify({'response': get_weights(), 'type': 'info'})

        elif cmd == 'stats':
            return jsonify({'response': get_stats(), 'type': 'info'})

        elif cmd == 'forget':
            loom.forget_all()
            return jsonify({'response': 'Memory erased. Starting fresh.', 'type': 'info'})

        elif cmd == 'about':
            return jsonify({'response': get_about_text(), 'type': 'info'})

        elif cmd.startswith('analogies '):
            concept = cmd[10:].strip()
            return jsonify({'response': get_analogies(concept), 'type': 'info'})

        elif cmd.startswith('neuron '):
            node = cmd[7:].strip()
            return jsonify({'response': get_neuron_info(node), 'type': 'info'})

        elif cmd.startswith('frame '):
            concept = cmd[6:].strip()
            if concept:
                return jsonify({
                    'response': loom.frame_manager.format_frame(concept).replace('\n', '<br>').replace('  ', '&nbsp;&nbsp;'),
                    'type': 'info'
                })

        elif cmd.startswith('bridges'):
            arg = cmd[7:].strip() if len(cmd) > 7 else ""
            return jsonify({
                'response': loom.frame_manager.format_bridges(arg if arg else None).replace('\n', '<br>').replace('  ', '&nbsp;&nbsp;'),
                'type': 'info'
            })

        elif cmd == 'clusters':
            return jsonify({
                'response': loom.frame_manager.format_clusters().replace('\n', '<br>').replace('  ', '&nbsp;&nbsp;'),
                'type': 'info'
            })

        elif cmd.startswith('train '):
            from loom.trainer import train
            pack_name = cmd[6:].strip()
            count, msg = train(loom, pack_name)
            return jsonify({'response': msg, 'type': 'info'})

        elif cmd == 'train':
            from loom.trainer import list_packs
            packs = list_packs()
            return jsonify({'response': 'Available packs: ' + ', '.join(packs), 'type': 'info'})

        elif cmd.startswith('load '):
            from loom.trainer import train_from_file
            filepath = cmd[5:].strip()
            count, msg = train_from_file(loom, filepath)
            return jsonify({'response': msg, 'type': 'info'})

        else:
            return jsonify({'response': f'Unknown command: /{cmd}. Type /help for commands.', 'type': 'error'})

    else:
        # Detect pasted JSON array -> load as training data
        stripped = message.strip()
        if stripped.startswith('[') and stripped.endswith(']'):
            try:
                import json
                data = json.loads(stripped)
                if isinstance(data, list) and data and isinstance(data[0], dict):
                    count = 0
                    for item in data:
                        subj = item.get('subject', item.get('s', ''))
                        rel = item.get('relation', item.get('r', ''))
                        obj = item.get('object', item.get('o', ''))
                        if subj and rel and obj:
                            loom.add_fact(subj, rel, obj)
                            count += 1
                    return jsonify({
                        'response': f'Loaded {count} facts from pasted JSON.',
                        'type': 'info'
                    })
            except (json.JSONDecodeError, ValueError):
                pass  # Not valid JSON, fall through to normal processing

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

<b>Commands</b> (require / prefix)
• /about - what is Loom?
• /show - view knowledge summary
• /neuron X - inspect concept X
• /frame X - show concept frame
• /bridges [X] - show attribute bridges
• /clusters - show emergent clusters
• /activation - show activation state
• /weights - show strong connections
• /analogies X - find similar concepts
• /stats - storage statistics
• /clear - clear chat history
• /forget - erase all memory
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

    # Collect ALL node ids first (subjects + all targets they reference)
    all_node_ids = set()
    for node_id, relations in knowledge.items():
        all_node_ids.add(node_id)
        for targets in relations.values():
            for target in targets:
                all_node_ids.add(target)

    # Build incoming counts
    incoming_counts = {}
    for node_id, relations in knowledge.items():
        for targets in relations.values():
            for target in targets:
                incoming_counts[target] = incoming_counts.get(target, 0) + 1

    # Create nodes for every referenced entity
    for node_id in all_node_ids:
        relations = knowledge.get(node_id, {})
        outgoing = sum(len(targets) for targets in relations.values()) if isinstance(relations, dict) else 0
        incoming = incoming_counts.get(node_id, 0)

        nodes.append({
            'id': node_id,
            'label': node_id.replace('_', ' ').title(),
            'connections': outgoing + incoming,
            'outgoing': outgoing,
            'incoming': incoming,
            'is_lonely': node_id in lonely_node_ids,
            'relations': {rel: list(targets) for rel, targets in relations.items()} if isinstance(relations, dict) else {}
        })
        node_ids.add(node_id)

    # Create edges from relations (all targets now have nodes)
    for source_id, relations in knowledge.items():
        if not isinstance(relations, dict):
            continue
        for relation, targets in relations.items():
            for target in targets:
                weight = loom.get_connection_weight(source_id, relation, target)
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
    storage_type = "MongoDB" if loom.use_mongo else "JSON File"
    print("\n  Loom Web Interface")
    print(f"  Storage: {storage_type}")
    if loom.use_mongo:
        print(f"  Database: loom_memory")
    else:
        print(f"  File: loom_memory/loom_memory.json")
    stats = loom.get_stats()
    print(f"  Loaded: {stats['nodes']} neurons, {stats['facts']} synapses")
    print("  Open http://localhost:5000 in your browser\n")
    app.run(debug=True, port=5000)
