"""
Smart Loom Knowledge Map Demo

Demonstrates all key features working together:
1. Recursive Expansion (category hierarchy)
2. Property Inheritance (down the chain)
3. Multi-Hop Inference (transitive syllogism)
4. Similarity Links (shared properties)
5. Curiosity Nodes (unknown concepts)
6. Co-Activation Discovery (spreading activation)
7. Temporal/Contextual Awareness
"""

import sys
import os
import time

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Fix Windows encoding
if os.name == 'nt':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, errors='replace')

from loom import Loom


def print_section(title):
    print(f"\n{'='*70}")
    print(f" {title}")
    print('='*70)


def print_box(title, content):
    """Print content in a box."""
    width = 60
    print(f"\n  +{'-'*(width-2)}+")
    print(f"  | {title:<{width-4}} |")
    print(f"  +{'-'*(width-2)}+")
    for line in content:
        print(f"  | {line:<{width-4}} |")
    print(f"  +{'-'*(width-2)}+")


def demo_smart_loom():
    """Full Smart Loom demonstration."""

    print("\n" + "="*70)
    print("       SMART LOOM KNOWLEDGE MAP DEMO")
    print("       Building an Intelligent Animal Knowledge Graph")
    print("="*70)

    loom = Loom(verbose=True)
    loom.forget_all()  # Start fresh

    # =========================================
    print_section("STEP 1: RECURSIVE EXPANSION (Category Hierarchy)")
    # =========================================

    hierarchy_facts = [
        # Top level
        "mammals are animals",
        "reptiles are animals",
        "birds are animals",
        "fish are animals",

        # Mammals
        "dogs are mammals",
        "cats are mammals",
        "whales are mammals",
        "dolphins are mammals",

        # Reptiles
        "snakes are reptiles",
        "lizards are reptiles",

        # Birds
        "eagles are birds",
        "penguins are birds",

        # Fish
        "sharks are fish",
        "salmon are fish",
    ]

    print("\n  Teaching category hierarchy:")
    for fact in hierarchy_facts:
        loom.process(fact)
        print(f"    + {fact}")

    print(f"\n  Hierarchy established: {len(hierarchy_facts)} facts")

    # =========================================
    print_section("STEP 2: PROPERTY INHERITANCE (Down the Chain)")
    # =========================================

    property_facts = [
        # Mammal properties
        "mammals have fur",
        "mammals can breathe_air",
        "mammals are warm_blooded",

        # Reptile properties
        "reptiles have scales",
        "reptiles are cold_blooded",

        # Bird properties
        "birds have feathers",
        "birds can fly",
        "birds lay eggs",

        # Fish properties
        "fish have gills",
        "fish can swim",

        # Specific overrides
        "penguins cannot fly",
        "whales live in the ocean",
        "dolphins live in the ocean",
        "sharks live in the ocean",
    ]

    print("\n  Teaching category properties:")
    for fact in property_facts:
        loom.process(fact)
        print(f"    + {fact}")

    # Propagate properties down
    time.sleep(0.5)
    propagated = loom._propagate_properties_down()

    print(f"\n  Properties propagated to instances: {len(propagated)}")
    print("\n  Inherited properties (samples):")
    for entity in ['dogs', 'cats', 'snakes', 'eagles']:
        has_props = loom.get(entity, 'has') or []
        can_props = loom.get(entity, 'can') or []
        if has_props or can_props:
            print(f"    [{entity}]")
            for p in has_props[:2]:
                print(f"      has: {p} (inherited)")
            for p in can_props[:2]:
                print(f"      can: {p} (inherited)")

    # =========================================
    print_section("STEP 3: MULTI-HOP INFERENCE (Transitive Syllogism)")
    # =========================================

    print("\n  Applying transitive inference (A->B, B->C => A->C):")

    # Apply syllogisms
    for entity in ['dogs', 'cats', 'whales', 'snakes', 'eagles', 'sharks']:
        loom.inference._apply_syllogism(entity, 'is')

    # Show inferred chains
    inferred_count = 0
    for entity in ['dogs', 'cats', 'whales', 'snakes', 'eagles', 'sharks']:
        categories = loom.get(entity, 'is') or []
        if 'animals' in categories:
            chain = []
            if entity in ['dogs', 'cats', 'whales', 'dolphins']:
                chain = [entity, 'mammals', 'animals']
            elif entity in ['snakes', 'lizards']:
                chain = [entity, 'reptiles', 'animals']
            elif entity in ['eagles', 'penguins']:
                chain = [entity, 'birds', 'animals']
            elif entity in ['sharks', 'salmon']:
                chain = [entity, 'fish', 'animals']
            print(f"    [INFERRED] {' -> '.join(chain)}")
            inferred_count += 1

    print(f"\n  Total multi-hop inferences: {inferred_count}")

    # =========================================
    print_section("STEP 4: SIMILARITY LINKS (Shared Properties)")
    # =========================================

    print("\n  Discovering similarity connections...")
    discovered = loom.discover_connections()

    # Show similar_to relationships
    similar_pairs = set()
    for entity, relations in loom.knowledge.items():
        if 'similar_to' in relations:
            for similar in relations['similar_to']:
                pair = tuple(sorted([entity, similar]))
                similar_pairs.add(pair)

    print("\n  Similar entities detected:")
    for e1, e2 in list(similar_pairs)[:10]:
        # Find shared properties
        e1_has = set(loom.get(e1, 'has') or [])
        e2_has = set(loom.get(e2, 'has') or [])
        shared = e1_has & e2_has
        shared_str = ", ".join(list(shared)[:2]) if shared else "category"
        print(f"    {e1} <=> {e2}  (shared: {shared_str})")

    print(f"\n  Total similarity links: {len(similar_pairs)}")

    # =========================================
    print_section("STEP 5: CURIOSITY NODES (Unknown Concepts)")
    # =========================================

    print("\n  Creating curiosity about unknown concepts...")

    # Ask about unknown things
    unknowns = [
        "what are dragons?",
        "what are unicorns?",
        "can whales fly?",
    ]

    for question in unknowns:
        print(f"\n  Q: {question}")
        response = loom.process(question)
        print(f"  A: {response}")

    # Show curiosity nodes
    print("\n  Active curiosity nodes:")
    loom.show_curiosity_nodes()

    # Demonstrate hypothesis generation
    if loom.is_curious_about("dragons"):
        print("  Hypotheses for 'dragons':")
        hypotheses = loom.get_curiosity_hypotheses("dragons")
        for h in hypotheses[:3]:
            print(f"    - dragons might {h['relation']} {h['object']} (conf: {h['confidence']:.2f})")

    # =========================================
    print_section("STEP 6: CO-ACTIVATION DISCOVERY (Spreading Activation)")
    # =========================================

    print("\n  Simulating co-activation patterns...")

    # Teach hunting behavior
    hunting_facts = [
        "dogs hunt prey",
        "cats hunt prey",
        "eagles hunt prey",
        "sharks hunt prey",
    ]

    for fact in hunting_facts:
        loom.process(fact)
        print(f"    + {fact}")

    # Check what got activated together
    print("\n  Co-activated concepts (hunting context):")

    # Activate hunting-related concepts
    loom.activation.activate("hunting", amount=1.0)
    loom.activation.activate("prey", amount=1.0)

    # Find highly activated concepts
    activated = []
    for entity in loom.knowledge.keys():
        if entity.startswith("?_") or entity in ['self', 'user']:
            continue
        level = loom.activation.get_activation(entity)
        if level > 0.2:
            activated.append((entity, level))

    activated.sort(key=lambda x: x[1], reverse=True)
    for entity, level in activated[:8]:
        print(f"    {entity}: {level:.2f}")

    # =========================================
    print_section("STEP 7: TEMPORAL/CONTEXTUAL AWARENESS")
    # =========================================

    print("\n  Teaching temporal/contextual facts:")

    temporal_facts = [
        "snakes hibernate in winter",
        "birds migrate in autumn",
        "salmon spawn in spring",
    ]

    for fact in temporal_facts:
        loom.process(fact)
        print(f"    + {fact}")

    # Query with context
    print("\n  Context-aware queries:")
    queries = [
        "what do snakes do in winter?",
        "when do birds migrate?",
    ]

    for q in queries:
        response = loom.process(q)
        print(f"    Q: {q}")
        print(f"    A: {response}")

    # =========================================
    print_section("FINAL KNOWLEDGE GRAPH STATISTICS")
    # =========================================

    total_neurons = len([k for k in loom.knowledge.keys() if not k.startswith("?_")])
    total_synapses = sum(
        sum(len(targets) for targets in rels.values())
        for entity, rels in loom.knowledge.items()
        if not entity.startswith("?_")
    )

    curiosity_nodes = len([k for k in loom.knowledge.keys() if k.startswith("?_")])

    print(f"""
  +----------------------------------+--------+
  | Metric                           | Count  |
  +----------------------------------+--------+
  | Neurons (concepts)               | {total_neurons:>6} |
  | Synapses (connections)           | {total_synapses:>6} |
  | Similarity links                 | {len(similar_pairs):>6} |
  | Curiosity nodes                  | {curiosity_nodes:>6} |
  | Multi-hop inferences             | {inferred_count:>6} |
  | Inherited properties             | {len(propagated):>6} |
  +----------------------------------+--------+
    """)

    # =========================================
    print_section("VISUAL MAP (ASCII)")
    # =========================================

    print("""
                              [animals]
                                  |
           +----------------------+----------------------+
           |                      |                      |
           v                      v                      v
       [mammals]              [reptiles]             [birds]              [fish]
           |                      |                      |                   |
    +------+------+         +-----+-----+         +-----+-----+       +-----+-----+
    |      |      |         |           |         |           |       |           |
    v      v      v         v           v         v           v       v           v
 [dogs] [cats] [whales]  [snakes]  [lizards]  [eagles] [penguins] [sharks] [salmon]
    |      |      |         |           |         |           |       |           |
    |      |      |         |           |         |           |       |           |
   has:   has:   lives:   has:       has:      has:      cannot:   has:     lives:
   fur    fur    ocean    scales     scales    feathers   fly      gills    rivers
    |      |               |           |         |                   |
    +======+               +===========+         |                   |
    similar                 similar              |                   |
                                                 v                   v
                                             [?_dragons]        [?_unicorns]
                                               (curious)          (curious)

    LEGEND:
    ─────>  is (category)
    ······> has/can (property)
    <=====> similar_to (discovered)
    [?_X]   curiosity node (unknown)
    """)

    return loom


def demo_interactive_queries(loom):
    """Demonstrate interactive queries on the built graph."""

    print_section("INTERACTIVE QUERIES")

    queries = [
        # Category queries
        ("what are dogs?", "Category lookup"),
        ("what are mammals?", "Instance lookup"),

        # Property queries
        ("do dogs have fur?", "Inherited property"),
        ("can penguins fly?", "Override property"),

        # Similarity queries
        ("what is similar to dogs?", "Similarity lookup"),

        # Causal queries
        ("what do cats hunt?", "Action lookup"),

        # Unknown concept
        ("what are griffins?", "Creates curiosity node"),
    ]

    print()
    for query, description in queries:
        print(f"  [{description}]")
        print(f"  Q: {query}")
        response = loom.process(query)
        print(f"  A: {response}")
        print()


if __name__ == "__main__":
    loom = demo_smart_loom()
    demo_interactive_queries(loom)

    print("\n" + "="*70)
    print("  Smart Loom demo complete!")
    print("  All 7 features demonstrated:")
    print("    1. Recursive Expansion")
    print("    2. Property Inheritance")
    print("    3. Multi-Hop Inference")
    print("    4. Similarity Links")
    print("    5. Curiosity Nodes")
    print("    6. Co-Activation Discovery")
    print("    7. Temporal Awareness")
    print("="*70 + "\n")
