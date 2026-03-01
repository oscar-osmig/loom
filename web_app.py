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

    # Check for commands
    cmd = message.lower()

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
• show - view knowledge summary
• neuron X - inspect concept X
• activation - show activation state
• weights - show strong connections
• analogies X - find similar concepts
• stats - storage statistics
• forget - erase memory
• help - show this help"""


def get_knowledge_summary():
    """Get a summary of current knowledge."""
    knowledge = loom.knowledge
    if not knowledge:
        return "No knowledge stored yet."

    lines = ["<b>Knowledge Graph</b>", ""]
    count = 0
    for node, relations in list(knowledge.items())[:15]:
        rel_count = sum(len(v) for v in relations.values())
        lines.append(f"• <b>{node}</b>: {rel_count} connections")
        count += 1

    if len(knowledge) > 15:
        lines.append(f"... and {len(knowledge) - 15} more neurons")

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


if __name__ == '__main__':
    print("\n  Loom Web Interface")
    print("  Open http://localhost:5000 in your browser\n")
    app.run(debug=True, port=5000)
