"""
Loom Web Interface - Flask Backend
A minimalistic chat interface for Loom.
"""

from dotenv import load_dotenv
load_dotenv()

from flask import Flask, request, jsonify, send_file
import json
import os
import pathlib

from loom import Loom

app = Flask(__name__, static_folder='static', static_url_path='')

# Initialize Loom instance with MongoDB (connection string loaded from MONGO_URI env var)
loom = Loom(verbose=False, use_mongo=True, database_name="loom_memory")
loom.context.set_knowledge_ref(loom.knowledge)


def is_admin(email: str) -> bool:
    """Check if the given email matches the admin email from environment."""
    admin_email = os.environ.get('ADMIN_EMAIL', '')
    return bool(email and admin_email and email.lower() == admin_email.lower())


@app.route('/api/config', methods=['GET'])
def get_config():
    """Return public client-side configuration."""
    return jsonify({
        'google_client_id': os.environ.get('google_client_id', '')
    })


@app.route('/')
def index():
    """Serve the Svelte SPA (falls back to legacy HTML if not built)."""
    static_index = os.path.join(app.static_folder, 'index.html')
    if os.path.exists(static_index):
        return send_file(static_index)
    return send_file('web_chat.html')


@app.route('/loom.png')
def loom_icon():
    """Serve the Loom icon."""
    return send_file('loom.png', mimetype='image/png')


def forget_user_facts(username: str) -> int:
    """Remove all facts created by a specific user."""
    result = loom.storage.db.facts.delete_many({
        "instance": loom.storage.instance_name,
        "properties.speaker_id": username
    })
    count = result.deleted_count

    # Rebuild in-memory cache
    if count > 0:
        loom._invalidate_cache()
        # Rebuild frame manager from remaining knowledge
        if hasattr(loom, 'frame_manager'):
            loom.frame_manager.reset()
            loom.frame_manager.hydrate_from_knowledge()

    return count


def _process_training_file(file) -> dict:
    """Process a single training file. Returns dict with loaded/errors/filename."""
    filename = file.filename or ''

    if not filename.lower().endswith(('.json', '.txt')):
        return {'error': f'{filename}: unsupported file type.', 'loaded': 0, 'filename': filename}

    try:
        content = file.read().decode('utf-8')
    except UnicodeDecodeError:
        return {'error': f'{filename}: not UTF-8.', 'loaded': 0, 'filename': filename}

    if not content.strip():
        return {'error': f'{filename}: empty.', 'loaded': 0, 'filename': filename}

    count = 0
    errors = []

    if filename.lower().endswith('.json'):
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            return {'error': f'{filename}: invalid JSON at line {e.lineno}.', 'loaded': 0, 'filename': filename}

        if not isinstance(data, list) or not data:
            return {'error': f'{filename}: JSON must be a non-empty array.', 'loaded': 0, 'filename': filename}

        for i, item in enumerate(data):
            if not isinstance(item, dict):
                errors.append(f'{filename} item {i+1}: not an object.')
                continue
            subj = item.get('subject', item.get('s', ''))
            rel = item.get('relation', item.get('r', ''))
            obj = item.get('object', item.get('o', ''))
            if not subj or not rel or not obj:
                continue
            loom.add_fact(subj, rel, obj)
            count += 1
    else:
        for i, line in enumerate(content.strip().split('\n')):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = [p.strip() for p in (line.split('|') if '|' in line else line.split(','))]
            if len(parts) >= 3 and parts[0] and parts[1] and parts[2]:
                loom.add_fact(parts[0], parts[1], parts[2])
                count += 1

    result = {'loaded': count, 'filename': filename}
    if errors:
        result['warnings'] = errors[:5]
    return result


@app.route('/api/upload-training', methods=['POST'])
def upload_training():
    """Upload and validate a single JSON or TXT training file."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided.'}), 400

    upload_user = request.form.get('user', '')
    if upload_user:
        loom._session_speaker_id = upload_user

    result = _process_training_file(request.files['file'])
    if 'error' in result and result['loaded'] == 0:
        return jsonify(result), 400
    return jsonify(result)


@app.route('/api/upload-training-batch', methods=['POST'])
def upload_training_batch():
    """Upload and process up to 50 training files in a single request."""
    files = request.files.getlist('files')
    if not files:
        return jsonify({'error': 'No files provided.'}), 400

    if len(files) > 50:
        return jsonify({'error': 'Maximum 50 files per batch.'}), 400

    upload_user = request.form.get('user', '')
    if upload_user:
        loom._session_speaker_id = upload_user

    total_loaded = 0
    file_results = []
    errors = []

    for file in files:
        result = _process_training_file(file)
        total_loaded += result.get('loaded', 0)
        file_results.append({'filename': result['filename'], 'loaded': result.get('loaded', 0)})
        if 'error' in result:
            errors.append(result['error'])

    # Rebuild frames once after all files are processed
    if total_loaded > 0 and hasattr(loom, 'frame_manager'):
        loom.frame_manager.hydrate_from_knowledge()

    response = {
        'total_loaded': total_loaded,
        'files_processed': len(file_results),
        'files': file_results,
    }
    if errors:
        response['errors'] = errors

    return jsonify(response)


@app.route('/api/chat', methods=['POST'])
def chat():
    """Process a chat message and return response."""
    data = request.json
    message = data.get('message', '').strip()
    user = data.get('user', '').strip()
    email = data.get('email', '').strip()
    conversation_id = data.get('conversation_id', '').strip()

    if not message:
        return jsonify({'response': 'Please enter a message.', 'type': 'error'})

    # Switch to this conversation's context (isolates multi-user state)
    if conversation_id:
        loom.set_conversation(conversation_id)
    else:
        loom.set_conversation("_default")

    # Tag all facts with the current user
    if user:
        loom._session_speaker_id = user
        # Track message count for leaderboard
        try:
            loom.storage.db.user_stats.update_one(
                {"instance": loom.storage.instance_name, "user": user},
                {"$inc": {"message_count": 1}, "$set": {"last_active": __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()}},
                upsert=True,
            )
        except Exception:
            pass

    # Commands require / prefix
    if message.startswith('/'):
        cmd = message[1:].lower().strip()

        if cmd == 'help':
            return jsonify({'response': get_help_text(admin=is_admin(email)), 'type': 'help'})

        elif cmd == 'style':
            if not is_admin(email):
                return jsonify({'response': 'Permission denied. Only admins can view style data.', 'type': 'error'})
            return jsonify({'response': 'open_style_page', 'type': 'style'})

        elif cmd == 'visualize' or cmd == 'viz' or cmd == 'graph':
            return jsonify({'response': 'open_visualizer', 'type': 'visualize'})

        elif cmd == 'about':
            return jsonify({'response': 'open_about', 'type': 'about'})

        elif cmd == 'procedures':
            procs = loom.storage.get_all_procedures()
            if not procs:
                return jsonify({'response': 'No procedures stored yet. Teach me steps like "first boil water, then add pasta, finally drain it."', 'type': 'response'})
            lines = ["<b>Stored Procedures</b>\n"]
            for name, steps in procs.items():
                lines.append(f"<b>{name}</b>")
                for i, step in enumerate(steps, 1):
                    lines.append(f"  {i}. {step}")
                lines.append("")
            return jsonify({'response': '\n'.join(lines), 'type': 'info'})

        elif cmd == 'show':
            return jsonify({'response': get_knowledge_summary(), 'type': 'info'})

        elif cmd == 'activation':
            return jsonify({'response': get_activation_state(), 'type': 'info'})

        elif cmd == 'weights':
            return jsonify({'response': get_weights(), 'type': 'info'})

        elif cmd == 'stats':
            return jsonify({'response': get_stats(), 'type': 'info'})

        elif cmd == 'forget-all':
            if not is_admin(email):
                return jsonify({'response': 'Permission denied. Only admins can erase all memory.', 'type': 'error'})
            try:
                # Count what exists before wiping
                facts_before = loom.storage.get_fact_count()
                loom.forget_all()
                facts_after = loom.storage.get_fact_count()
                return jsonify({
                    'response': f'All memory erased. Removed {facts_before} facts, rebuilt {facts_after} system neurons. Starting fresh.',
                    'type': 'info'
                })
            except Exception as e:
                return jsonify({'response': f'Error during forget-all: {e}', 'type': 'error'})

        elif cmd == 'forget':
            if user:
                count = forget_user_facts(user)
                return jsonify({'response': f'Erased {count} of your facts.', 'type': 'info'})
            else:
                return jsonify({'response': 'No user identified. Sign in first.', 'type': 'error'})

        elif cmd == 'load-all':
            if not is_admin(email):
                return jsonify({'response': 'Permission denied. Only admins can load all training files.', 'type': 'error'})
            import glob
            training_dir = os.path.join(os.path.dirname(__file__), 'training')
            files = sorted(glob.glob(os.path.join(training_dir, '*.json')) + glob.glob(os.path.join(training_dir, '*.txt')))
            if not files:
                return jsonify({'response': 'No training files found in training/ folder.', 'type': 'error'})
            total_loaded = 0
            results = []
            for filepath in files:
                fname = os.path.basename(filepath)
                try:
                    count, msg = loom.train_from_file(filepath) if hasattr(loom, 'train_from_file') else (0, 'N/A')
                    if count == 0:
                        from loom.trainer import train_from_file
                        count, msg = train_from_file(loom, filepath)
                    total_loaded += count
                    results.append({"name": fname, "count": count, "ok": True})
                except Exception as e:
                    results.append({"name": fname, "count": 0, "ok": False, "error": str(e)[:80]})
            return jsonify({
                'response': 'open_load_results',
                'type': 'load_results',
                'meta': {
                    'total_loaded': total_loaded,
                    'total_files': len(files),
                    'files': results,
                }
            })

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


def get_help_text(admin=False):
    """Return help text, filtering commands by role."""
    text = """<b>Loom — Community Knowledge System</b>
A knowledge system built from what people teach it. Every fact is transparent, attributed, and open to revision.

<b>Contribute</b>
• "dogs are mammals" — teach a fact
• "no, that's wrong" — correct a mistake
• "actually, cats are felines" — update knowledge
• Paste paragraphs — Loom extracts knowledge automatically

<b>Ask</b>
• "what are dogs?" — query categories
• "tell me about elephants" — full description
• "where do fish live?" — locations
• "can birds fly?" — abilities

<b>Commands</b> (use / prefix)
• /about — what is Loom + how to contribute
• /help — this help
• /visualize — explore the knowledge graph
• /clear — clear chat history
• /forget — erase your own facts"""

    if admin:
        text += """

<b>Admin</b>
• /show — knowledge summary
• /stats — storage statistics
• /style — writing style analytics
• /load-all — load all training files
• /neuron X — inspect concept
• /frame X — concept frame
• /clusters — emergent clusters
• /analogies X — find similar concepts
• /forget-all — erase all memory"""

    return text


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
    return f"""<b>Storage Statistics</b>

Storage: MongoDB
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


@app.route('/api/check-nickname', methods=['GET'])
def check_nickname():
    """Check if a nickname is available (not already used by another user)."""
    name = request.args.get('name', '').strip()
    if not name:
        return jsonify({'available': False, 'reason': 'Empty name'})

    try:
        existing = loom.storage.db.facts.distinct(
            'properties.speaker_id',
            {'instance': loom.storage.instance_name}
        )
        # Case-insensitive check
        taken = any(s.lower() == name.lower() for s in existing if s)
        return jsonify({'available': not taken})
    except Exception:
        # Fallback: allow it if we can't check
        return jsonify({'available': True})


@app.route('/api/collaborators', methods=['GET'])
def get_collaborators():
    """Aggregate user contributions: neurons created, corrections, messages."""
    inst = loom.storage.instance_name

    try:
        # Neurons created per user (from facts.properties.speaker_id)
        neurons_pipeline = [
            {"$match": {"instance": inst, "properties.speaker_id": {"$exists": True, "$ne": None, "$ne": ""}}},
            {"$group": {"_id": "$properties.speaker_id", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 50},
        ]
        neurons_by_user = {doc["_id"]: doc["count"] for doc in loom.storage.db.facts.aggregate(neurons_pipeline)}

        # Corrections per user
        corrections_pipeline = [
            {"$match": {"instance": inst, "corrected_by": {"$exists": True, "$ne": None, "$ne": ""}}},
            {"$group": {"_id": "$corrected_by", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 50},
        ]
        corrections_by_user = {doc["_id"]: doc["count"] for doc in loom.storage.db.corrections.aggregate(corrections_pipeline)}

        # Messages per user
        messages_by_user = {}
        for doc in loom.storage.db.user_stats.find({"instance": inst}):
            messages_by_user[doc["user"]] = doc.get("message_count", 0)

        # Admin detection
        admin_email = os.environ.get('ADMIN_EMAIL', '').lower()
        # Also collect admin names from user_stats where we can store email
        admin_names = set()
        if admin_email:
            admin_names.add(admin_email)
            admin_names.add(admin_email.split('@')[0])
            admin_names.add(admin_email.split('@')[0].replace('.', ' '))
            admin_names.add(admin_email.split('@')[0].replace('.', ''))
        # Caller can pass their email to tag themselves
        caller_email = request.args.get('email', '').lower()
        caller_user = request.args.get('user', '')
        if caller_email and is_admin(caller_email) and caller_user:
            admin_names.add(caller_user.lower())

        # Merge all users (filter out None/empty)
        all_users = set(neurons_by_user.keys()) | set(corrections_by_user.keys()) | set(messages_by_user.keys())
        all_users = {u for u in all_users if u}  # remove None and ""

        collaborators = []
        for u in all_users:
            # Check admin
            user_is_admin = u.lower() in admin_names if admin_names else False
            collaborators.append({
                "user": u,
                "neurons": neurons_by_user.get(u, 0),
                "corrections": corrections_by_user.get(u, 0),
                "messages": messages_by_user.get(u, 0),
                "is_admin": user_is_admin,
            })

        # Sorted lists
        by_neurons = sorted(collaborators, key=lambda x: x["neurons"], reverse=True)
        by_corrections = sorted(collaborators, key=lambda x: x["corrections"], reverse=True)
        by_messages = sorted(collaborators, key=lambda x: x["messages"], reverse=True)

        return jsonify({
            "total_collaborators": len(all_users),
            "by_neurons": by_neurons[:20],
            "by_corrections": by_corrections[:20],
            "by_messages": by_messages[:20],
        })
    except Exception as e:
        return jsonify({"error": str(e), "total_collaborators": 0, "by_neurons": [], "by_corrections": [], "by_messages": []})


@app.route('/api/style', methods=['GET'])
def get_style():
    """Return what Loom has learned about writing style. Admin only."""
    email = request.args.get('email', '')
    if not is_admin(email):
        return jsonify({'error': 'Admin access required'}), 403
    if not hasattr(loom, 'style_learner'):
        return jsonify({'stats': {}, 'patterns': []})

    stats = loom.style_learner.get_stats()

    # Top patterns per kind
    patterns = {
        'openers': [
            {'value': v, 'score': s, 'likes': doc.get('likes', 0), 'dislikes': doc.get('dislikes', 0), 'count': doc.get('count', 0)}
            for v, s, doc in loom.style_learner.get_top_patterns('opener', limit=5)
        ],
        'connectives': [
            {'value': v, 'score': s, 'likes': doc.get('likes', 0), 'dislikes': doc.get('dislikes', 0), 'count': doc.get('count', 0)}
            for v, s, doc in loom.style_learner.get_top_patterns('connective', limit=5)
        ],
        'templates': [
            {'value': v, 'score': s, 'likes': doc.get('likes', 0), 'dislikes': doc.get('dislikes', 0), 'count': doc.get('count', 0)}
            for v, s, doc in loom.style_learner.get_top_patterns('template', limit=5)
        ],
        'composer_templates': [
            {'value': v, 'score': s, 'likes': doc.get('likes', 0), 'dislikes': doc.get('dislikes', 0), 'count': doc.get('count', 0)}
            for v, s, doc in loom.style_learner.get_top_patterns('composer_template', limit=10)
        ],
    }

    return jsonify({'stats': stats, 'patterns': patterns})


@app.route('/api/response-edit', methods=['POST'])
def record_response_edit():
    """Store a user-edited version of Loom's response for style learning."""
    from datetime import datetime, timezone
    data = request.json or {}
    original = (data.get('original_response') or '').strip()
    edited = (data.get('edited_response') or '').strip()

    if not edited or not original:
        return jsonify({'error': 'Both original and edited text required'}), 400
    if edited == original:
        return jsonify({'ok': True, 'changed': False})

    doc = {
        'instance': loom.storage.instance_name,
        'message_id': data.get('message_id'),
        'original': original[:2000],
        'edited': edited[:2000],
        'user': data.get('user', ''),
        'input_text': (data.get('input_text') or '')[:500],
        'created_at': datetime.now(timezone.utc).isoformat(),
    }
    try:
        loom.storage.db.response_edits.insert_one(doc)
        # Also record as negative feedback for the original style
        if hasattr(loom, 'style_learner'):
            loom.style_learner.record(
                input_text=doc['input_text'],
                response_text=original,
                rating='dislike',
            )
    except Exception:
        pass
    return jsonify({'ok': True, 'changed': True})


@app.route('/api/feedback', methods=['POST'])
def record_feedback():
    """Record user feedback on an assistant response (for style learning)."""
    from datetime import datetime, timezone
    data = request.json or {}
    rating = data.get('rating')
    if rating not in ('like', 'dislike'):
        return jsonify({'error': 'Invalid rating'}), 400

    doc = {
        'instance': loom.storage.instance_name,
        'message_id': data.get('message_id'),
        'rating': rating,
        'user': data.get('user', ''),
        'input_text': (data.get('input_text') or '')[:500],
        'response_text': (data.get('response_text') or '')[:1000],
        'created_at': datetime.now(timezone.utc).isoformat(),
    }
    try:
        loom.storage.db.feedback.insert_one(doc)
        # Feed into style learner if available
        if hasattr(loom, 'style_learner'):
            loom.style_learner.record(
                input_text=doc['input_text'],
                response_text=doc['response_text'],
                rating=rating,
            )
    except Exception:
        pass
    return jsonify({'ok': True})


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

    # Collect creators (speaker_id) per node from stored facts
    node_creators = {}
    pipeline = [
        {"$match": {"instance": loom.storage.instance_name, "properties.speaker_id": {"$exists": True, "$ne": None}}},
        {"$group": {"_id": "$subject", "creators": {"$addToSet": "$properties.speaker_id"}}}
    ]
    try:
        for doc in loom.storage.db.facts.aggregate(pipeline):
            node_creators[doc["_id"]] = set(doc["creators"])
    except Exception:
        pass

    # Collect correctors per node from corrections collection
    node_correctors = {}
    try:
        corr_pipeline = [
            {"$match": {"instance": loom.storage.instance_name, "corrected_by": {"$exists": True, "$ne": ""}}},
            {"$group": {"_id": "$subject", "correctors": {"$addToSet": "$corrected_by"}}}
        ]
        for doc in loom.storage.db.corrections.aggregate(corr_pipeline):
            node_correctors[doc["_id"]] = set(doc["correctors"])
    except Exception:
        pass

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

        creators = list(node_creators.get(node_id, []))
        correctors = list(node_correctors.get(node_id, []))
        nodes.append({
            'id': node_id,
            'label': node_id.replace('_', ' ').title(),
            'connections': outgoing + incoming,
            'is_lonely': node_id in lonely_node_ids,
            'is_system': node_id == 'loom',
            'creators': creators,
            'correctors': correctors,
        })
        node_ids.add(node_id)

    # Create edges from relations (all targets now have nodes)
    # Pre-fetch all connection weights for fast lookup
    weights = loom.connection_weights
    for source_id, relations in knowledge.items():
        if not isinstance(relations, dict):
            continue
        for relation, targets in relations.items():
            for target in targets:
                key = (source_id, relation, target)
                weight = weights.get(key, 1.0)
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
    print(f"  Storage: MongoDB")
    stats = loom.get_stats()
    print(f"  Loaded: {stats['nodes']} neurons, {stats['facts']} synapses")
    print("  Open http://localhost:5000 in your browser\n")
    app.run(debug=True, port=5000)
