"""
Demo: Building the Animals Knowledge Graph

Shows how Loom creates and discovers connections:
1. Direct facts (black solid)
2. Multi-hop inference (blue dashed)
3. Property inheritance (green dotted)
4. Similarity detection (red double line)
5. Category bridging (orange dashed)
"""

import sys
import os
import time

# Fix Windows encoding
if os.name == 'nt':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, errors='replace')

from loom import Loom


def print_section(title):
    print(f"\n{'='*70}")
    print(f" {title}")
    print('='*70)


def print_graph(knowledge, title="Knowledge Graph"):
    """Print a visual representation of the graph."""
    print(f"\n{title}:")
    print("-" * 50)

    for entity, relations in sorted(knowledge.items()):
        if entity in ['self', 'user']:
            continue
        print(f"\n  [{entity}]")
        for rel, targets in sorted(relations.items()):
            # Choose symbol based on relation type
            if rel == 'is':
                symbol = "===>"  # Black solid (category)
            elif rel == 'has' or rel == 'can':
                symbol = "--->"  # Green (property)
            elif rel == 'similar_to':
                symbol = "<=>"   # Red (similarity)
            elif rel == 'related_to':
                symbol = "o--o"  # Orange (bridge)
            elif rel == 'habitat_type':
                symbol = "@-->"  # Location facet
            else:
                symbol = "--->"

            for target in targets:
                print(f"      {symbol} {rel}: {target}")


def demo_animals_graph():
    """Build and demonstrate the animals knowledge graph."""

    print_section("STEP 1: DIRECT FACTS (Base Knowledge)")

    loom = Loom(verbose=False)

    # Category hierarchy
    base_facts = [
        # Top level
        "mammals are animals",
        "reptiles are animals",
        "birds are animals",
        "fish are animals",

        # Mammals
        "cats are mammals",
        "dogs are mammals",
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

        # Properties of categories
        "mammals have fur",
        "mammals can breathe_air",
        "birds have feathers",
        "birds can fly",
        "fish have scales",
        "fish can swim",
        "reptiles have scales",
        "reptiles are cold_blooded",

        # Specific properties
        "penguins cannot fly",
        "whales live in the ocean",
        "dolphins live in the ocean",
        "sharks live in the ocean",
        "eagles live in mountains",
    ]

    print("\nTeaching base facts:")
    for fact in base_facts:
        result = loom.process(fact)
        print(f"  + {fact}")

    print(f"\n  Total facts taught: {len(base_facts)}")

    # Show initial state
    print_graph(loom.knowledge, "Initial Knowledge Graph")

    # ===========================================
    print_section("STEP 2: MULTI-HOP INFERENCE (Transitive Chains)")

    # Trigger inference
    time.sleep(0.5)

    # Apply syllogisms for key entities
    for entity in ['cats', 'dogs', 'whales', 'snakes', 'eagles', 'sharks']:
        loom.inference._apply_syllogism(entity, 'is')

    # Check what was inferred
    print("\nInferred category chains:")
    for entity in ['cats', 'dogs', 'whales', 'snakes', 'eagles', 'sharks']:
        categories = loom.get(entity, 'is') or []
        if 'animals' in categories:
            print(f"  [INFERRED] {entity} is animals (via transitive chain)")

    # ===========================================
    print_section("STEP 3: PROPERTY INHERITANCE (Down the Chain)")

    # Propagate properties
    propagated = loom._propagate_properties_down()

    print(f"\nProperties propagated: {len(propagated)}")

    # Show inherited properties
    print("\nInherited properties:")
    for entity in ['cats', 'dogs', 'whales', 'eagles', 'sharks']:
        entity_has = loom.get(entity, 'has') or []
        entity_can = loom.get(entity, 'can') or []

        if entity_has or entity_can:
            print(f"\n  [{entity}]")
            for prop in entity_has:
                print(f"      [INHERITED] has: {prop}")
            for prop in entity_can:
                print(f"      [INHERITED] can: {prop}")

    # ===========================================
    print_section("STEP 4: SIMILARITY DETECTION (Shared Properties)")

    # Run discovery
    discovered = loom.discover_connections()

    print(f"\nSimilarity connections discovered: {len([d for d in discovered if d[1] == 'similar_to'])}")

    # Show similar_to relationships
    print("\nSimilar entities:")
    shown = set()
    for entity, relations in loom.knowledge.items():
        if 'similar_to' in relations:
            for similar in relations['similar_to']:
                pair = tuple(sorted([entity, similar]))
                if pair not in shown:
                    shown.add(pair)
                    print(f"  {entity} <=> {similar}")

    # ===========================================
    print_section("STEP 5: FACET GROUPING (Habitat-Based)")

    # Show habitat facets
    print("\nHabitat groupings:")
    for entity, relations in loom.knowledge.items():
        if 'habitat_type' in relations:
            for habitat in relations['habitat_type']:
                print(f"  {entity} -> {habitat}_creatures")

    # ===========================================
    print_section("FINAL KNOWLEDGE GRAPH")

    print_graph(loom.knowledge, "Complete Knowledge Graph")

    # ===========================================
    print_section("GRAPH STATISTICS")

    total_neurons = len(loom.knowledge)
    total_synapses = sum(
        sum(len(targets) for targets in rels.values())
        for rels in loom.knowledge.values()
    )

    # Count by type
    direct_facts = len(base_facts)
    inferred_count = len([1 for e, r in loom.knowledge.items()
                          for rel, targets in r.items()
                          for t in targets
                          if rel == 'is' and t == 'animals' and e not in ['mammals', 'reptiles', 'birds', 'fish']])
    inherited_count = len(propagated)
    similar_count = len(shown)

    print(f"""
  +------------------------+--------+
  | Connection Type        | Count  |
  +------------------------+--------+
  | Neurons (concepts)     | {total_neurons:>6} |
  | Total synapses         | {total_synapses:>6} |
  +------------------------+--------+
  | Direct facts taught    | {direct_facts:>6} |
  | Inferred (multi-hop)   | {inferred_count:>6} |
  | Inherited (properties) | {inherited_count:>6} |
  | Similar (discovered)   | {similar_count:>6} |
  +------------------------+--------+
    """)

    # ===========================================
    print_section("VISUAL GRAPH (ASCII)")

    print("""
                            [animals]
                               |
              +----------------+----------------+
              |                |                |
              v                v                v
          [mammals]       [reptiles]        [birds]         [fish]
              |                |                |               |
    +---------+---------+      |          +----+----+     +----+----+
    |         |         |      |          |         |     |         |
    v         v         v      v          v         v     v         v
 [cats]    [dogs]   [whales] [snakes]  [eagles] [penguins] [sharks] [salmon]
    |         |         |                  |
    | has:fur | has:fur | can:breathe_air  | has:feathers
    |         |         |                  |
    +====<similar_to>===+                  +--- cannot:fly (override)
                        |
                        +--- lives_in:ocean --> [aquatic_creatures]

    LEGEND:
    ------> is (category)
    ······> has/can (property)
    <=====> similar_to (discovered)
    @-----> habitat_type (facet)
    """)

    return loom


def demo_query_the_graph():
    """Show how to query the built graph."""

    print_section("QUERYING THE GRAPH")

    loom = demo_animals_graph()

    print("\n" + "="*70)
    print(" SAMPLE QUERIES")
    print("="*70)

    queries = [
        "what are cats?",
        "what do mammals have?",
        "can whales breathe?",
        "what is similar to dogs?",
        "what lives in the ocean?",
        "can penguins fly?",
    ]

    print()
    for query in queries:
        result = loom.process(query)
        print(f"  Q: {query}")
        print(f"  A: {result}")
        print()


if __name__ == "__main__":
    demo_query_the_graph()
