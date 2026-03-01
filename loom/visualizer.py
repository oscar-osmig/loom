"""
ASCII Neuron Visualizer for Loom.
Displays knowledge graph as connected neuron nodes.
"""

from typing import Dict, List, Set


# Neuron styles
NEURON_STYLES = {
    "default": ("(", ")"),
    "concept": ("⟨", "⟩"),
    "action": ("[", "]"),
    "property": ("{", "}"),
}

# Relation symbols for connections
RELATION_SYMBOLS = {
    "is": "═══",
    "has": "───",
    "can": "~~~",
    "causes": ">>>",
    "leads_to": "-->",
    "looks_like": "~~~",
    "lives_in": "@──",
    "located_in": "@──",
    "found_in": "@──",
    "part_of": "◄──",
    "contains": "──►",
    "eats": "nom",
    "likes": "♥──",
    "loves": "♥♥─",
    "hates": "✗──",
    "fears": "!──",
    "needs": "?──",
    "wants": "○──",
    "uses": "⚙──",
    "made_of": "═▷─",
    "color": "●──",
    "is_not": "≠══",
    "has_not": "─≠─",
    "cannot": "~≠~",
    "belongs_to": "──◄",
    "owns": "──●",
    "knows": "───",
}


def truncate(text: str, max_len: int = 12) -> str:
    """Truncate text to fit in neuron display."""
    if len(text) <= max_len:
        return text
    return text[:max_len-2] + ".."


def get_neuron_type(node: str, relations: dict) -> str:
    """Determine the type of neuron based on its relations."""
    if "is" in relations:
        return "concept"
    if "can" in relations:
        return "action"
    if "color" in relations:
        return "property"
    return "default"


def draw_neuron(name: str, style: str = "default", width: int = 14) -> List[str]:
    """Draw a single neuron node."""
    left, right = NEURON_STYLES.get(style, NEURON_STYLES["default"])
    name = truncate(name, width - 4)
    padding = width - len(name) - 2

    lines = [
        f"    ╭{'─' * width}╮",
        f"   {left} {name}{' ' * padding}{right}",
        f"    ╰{'─' * width}╯",
    ]
    return lines


def draw_connection(relation: str, target: str, indent: int = 8) -> str:
    """Draw a connection line to another neuron."""
    symbol = RELATION_SYMBOLS.get(relation, "───")
    target_display = truncate(target, 15)
    return f"{' ' * indent}├{symbol}─► ({target_display})"


def visualize_graph(knowledge: Dict, max_nodes: int = 20) -> str:
    """
    Create ASCII visualization of the knowledge graph as neurons.
    """
    lines = []
    lines.append("")
    lines.append("  ╔══════════════════════════════════════════════════════════╗")
    lines.append("  ║              🧠  NEURAL KNOWLEDGE MAP  🧠                ║")
    lines.append("  ╚══════════════════════════════════════════════════════════╝")
    lines.append("")

    if not knowledge:
        lines.append("    (empty mind - teach me something!)")
        lines.append("")
        return "\n".join(lines)

    # Filter out internal nodes
    visible_nodes = {k: v for k, v in knowledge.items()
                     if not k.startswith("self") and "has_open_question" not in str(v)}

    # Sort by number of connections (most connected first)
    sorted_nodes = sorted(visible_nodes.items(),
                          key=lambda x: sum(len(v) for v in x[1].values()),
                          reverse=True)[:max_nodes]

    for node, relations in sorted_nodes:
        # Determine neuron style
        style = get_neuron_type(node, relations)

        # Draw the neuron
        neuron_lines = draw_neuron(node, style)
        for line in neuron_lines:
            lines.append(line)

        # Draw connections
        connection_count = 0
        for relation, targets in relations.items():
            if relation == "has_open_question":
                continue
            for target in targets:
                if connection_count < 5:  # Limit connections shown
                    lines.append(draw_connection(relation, target))
                    connection_count += 1
                else:
                    remaining = sum(len(t) for t in relations.values()) - 5
                    lines.append(f"        └─── (+{remaining} more connections)")
                    break
            else:
                continue
            break

        lines.append("")

    # Show stats
    total_nodes = len(knowledge)
    total_connections = sum(
        sum(len(targets) for targets in rels.values())
        for rels in knowledge.values()
    )

    lines.append(f"  ┌────────────────────────────────┐")
    lines.append(f"  │  Neurons: {total_nodes:<5} Synapses: {total_connections:<5} │")
    lines.append(f"  └────────────────────────────────┘")
    lines.append("")
    lines.append("  LEGEND:")
    lines.append("  ───────────────────────────────────")
    lines.append("  ═══  is/category    ───  has/property")
    lines.append("  ~~~  can/ability    >>>  causes/leads to")
    lines.append("  @──  lives in       nom  eats")
    lines.append("  ♥──  likes          ●──  color")
    lines.append("")
    lines.append("  ( )  default   ⟨ ⟩  concept")
    lines.append("  [ ]  action    { }  property")
    lines.append("")

    return "\n".join(lines)


def visualize_node(knowledge: Dict, node_name: str) -> str:
    """
    Visualize a single node and all its connections in detail.
    """
    from .normalizer import normalize

    node = normalize(node_name)

    if node not in knowledge:
        return f"  Node '{node_name}' not found in knowledge."

    lines = []
    relations = knowledge[node]

    lines.append("")
    lines.append(f"  ╔══════════════════════════════════════════╗")
    lines.append(f"  ║  Neuron: {node:<32} ║")
    lines.append(f"  ╚══════════════════════════════════════════╝")
    lines.append("")

    # Draw central neuron
    neuron_lines = draw_neuron(node, "concept", 20)
    for line in neuron_lines:
        lines.append(line)

    lines.append("        │")
    lines.append("        │  OUTGOING CONNECTIONS")
    lines.append("        │")

    # Draw all outgoing connections
    for relation, targets in relations.items():
        if relation == "has_open_question":
            continue
        symbol = RELATION_SYMBOLS.get(relation, "───")
        for target in targets:
            lines.append(f"        ├──{symbol}──► [ {target} ]")

    lines.append("        │")
    lines.append("        │  INCOMING CONNECTIONS")
    lines.append("        │")

    # Find incoming connections (reverse lookup)
    incoming = []
    for other_node, other_rels in knowledge.items():
        if other_node == node:
            continue
        for rel, targets in other_rels.items():
            if node in targets:
                incoming.append((other_node, rel))

    if incoming:
        for source, rel in incoming:
            symbol = RELATION_SYMBOLS.get(rel, "───")
            lines.append(f"        ◄──{symbol}──┤ [ {source} ]")
    else:
        lines.append("        (no incoming connections)")

    lines.append("")
    return "\n".join(lines)


def visualize_compact(knowledge: Dict) -> str:
    """
    Compact visualization showing just nodes and connection counts.
    """
    lines = []
    lines.append("")
    lines.append("  NEURONS          SYNAPSES")
    lines.append("  ─────────────────────────")

    for node, relations in sorted(knowledge.items()):
        if node.startswith("self"):
            continue
        conn_count = sum(len(targets) for targets in relations.values())
        rel_types = [r for r in relations.keys() if r != "has_open_question"]

        # Visual bar
        bar = "█" * min(conn_count, 10)
        lines.append(f"  ({node[:12]:<12}) {bar:<10} {conn_count}")

    lines.append("")
    return "\n".join(lines)
