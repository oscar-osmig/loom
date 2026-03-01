"""
Command Line Interface for Loom.
"""

from .brain import Loom
from .trainer import train, train_from_file, list_packs, get_pack_info


def print_header():
    """Print the welcome header."""
    print()
    print("  ╔═══════════════════════════════════════════════════╗")
    print("  ║                                                   ║")
    print("  ║                 L O O M  v0.5                     ║")
    print("  ║                                                   ║")
    print("  ║       Weaving Knowledge, Thread by Thread         ║")
    print("  ║                                                   ║")
    print("  ╚═══════════════════════════════════════════════════╝")
    print()
    print("  Type 'help' for commands. Just talk to me naturally!")
    print()


def print_help():
    """Print help information."""
    print()
    print("  HOW LOOM WORKS")
    print("  ──────────────────────────────────────────────────")
    print("  Loom learns by creating neurons (concepts) and")
    print("  synapses (connections) from your statements.")
    print()
    print("  TEACHING")
    print("    'dogs are animals'      - categories")
    print("    'birds can fly'         - abilities")
    print("    'cats also have claws'  - additive")
    print("    'rain causes floods'    - causation")
    print("    'no, that's wrong'      - corrections")
    print("    'only when it's warm'   - constraints")
    print("    'first X, then Y'       - procedures")
    print()
    print("  PARAGRAPHS")
    print("    Type or paste multiple sentences. Loom will:")
    print("    - Break text into chunks")
    print("    - Find discourse relations (cause, contrast, etc)")
    print("    - Build connections across sentences")
    print()
    print("  ASKING")
    print("    'what are dogs?'        - categories")
    print("    'can birds fly?'        - abilities")
    print("    'what does X cause?'    - effects")
    print()
    print("  COMMANDS")
    print("  ──────────────────────────────────────────────────")
    print("    show           View neural knowledge map")
    print("    neuron X       Inspect a specific neuron")
    print("    compact        Compact neuron list")
    print("    inferences     View inferred connections")
    print("    conflicts      View detected contradictions")
    print("    procedures     View stored procedures")
    print("    context        Show current context")
    print("    activation     Show activation state")
    print("    weights        Show strong connections")
    print("    analogies X    Find concepts similar to X")
    print("    chain X R      Trace reasoning chain")
    print("    train [pack]   Load knowledge pack")
    print("    load [file]    Load from custom file")
    print("    stats          Show storage statistics")
    print("    forget         Erase all memory")
    print("    verbose        Toggle debug output")
    print("    clear          Clear screen")
    print("    quit           Exit")
    print()


def clear_screen():
    """Clear the terminal screen."""
    print("\033[H\033[J", end="")


def run_cli():
    """Main CLI loop."""
    print_header()
    loom = Loom()

    # Connect context to knowledge graph for semantic resolution
    loom.context.set_knowledge_ref(loom.knowledge)

    while True:
        try:
            user_input = input("  you > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  Goodbye!")
            break

        if not user_input:
            continue

        cmd = user_input.lower()

        # Handle commands
        if cmd in ["quit", "exit", "bye", "q"]:
            clear_screen()
            print("  Goodbye!")
            break

        elif cmd == "show":
            loom.show_knowledge()

        elif cmd == "compact":
            loom.show_compact()

        elif cmd.startswith("neuron "):
            node_name = cmd[7:].strip()
            if node_name:
                loom.show_neuron(node_name)
            else:
                print("  Usage: neuron <name>")

        elif cmd == "inferences":
            loom.show_inferences()

        elif cmd == "conflicts":
            loom.show_conflicts()

        elif cmd == "procedures":
            loom.show_procedures()

        elif cmd == "context":
            ctx = loom.context.get_context_summary()
            print()
            print("  +-- Current Context --------------------------+")
            print(f"  |  Topic: {ctx['topic'] or '(none)'}")
            print(f"  |  Last subject: {ctx['last_subject'] or '(none)'}")
            print(f"  |  Last relation: {ctx['last_relation'] or '(none)'}")
            print(f"  |  Mode: {ctx['mode']}")
            print(f"  |  Recent statements: {ctx['recent_count']}")
            if ctx['pending_clarification']:
                print(f"  |  Pending: {ctx['pending_clarification']['question']}")
            print("  +----------------------------------------------+")
            print()

        elif cmd.startswith("chain "):
            parts = cmd[6:].split()
            if len(parts) >= 2:
                loom.trace_chain(parts[0], parts[1])
            else:
                print("  Usage: chain <subject> <relation>")

        elif cmd == "clear":
            clear_screen()

        elif cmd == "help":
            print_help()

        elif cmd == "verbose":
            loom.verbose = not loom.verbose
            state = "on" if loom.verbose else "off"
            print(f"  Verbose mode {state}.")

        elif cmd == "forget":
            loom.forget_all()
            print("  Memory erased. Starting fresh.")

        elif cmd == "train":
            # Show available packs
            packs = list_packs()
            print("  Available knowledge packs:")
            for pack in packs:
                print(f"    - {pack}")
            print("  Usage: train <pack_name>")

        elif cmd.startswith("train "):
            pack_name = cmd[6:].strip()
            count, msg = train(loom, pack_name)
            print(f"  {msg}")

        elif cmd.startswith("load "):
            filepath = cmd[5:].strip()
            count, msg = train_from_file(loom, filepath)
            print(f"  {msg}")

        elif cmd == "stats":
            stats = loom.get_stats()
            print()
            print("  +-- Storage Statistics -------------------------+")
            storage_type = "MongoDB" if loom.use_mongo else "JSON File"
            print(f"  |  Storage: {storage_type}")
            print(f"  |  Neurons: {stats['nodes']}")
            print(f"  |  Synapses: {stats['facts']}")
            print(f"  |  Procedures: {stats['procedures']}")
            print(f"  |  Inferences: {stats['inferences']}")
            print(f"  |  Conflicts: {stats['conflicts']}")
            print("  +-----------------------------------------------+")
            print()

        elif cmd == "activation":
            loom.show_activation()

        elif cmd == "weights":
            loom.show_weights()

        elif cmd.startswith("analogies "):
            concept = cmd[10:].strip()
            if concept:
                analogies = loom.inference.find_analogies(concept)
                print()
                print(f"  +-- Analogies for '{concept}' -------------------+")
                if not analogies:
                    print("  |  No analogies found.")
                else:
                    for analog, sim in analogies:
                        print(f"  |  {analog}: {sim:.2f} similarity")
                print("  +-----------------------------------------------+")
                print()
            else:
                print("  Usage: analogies <concept>")

        elif cmd == "entities":
            # Show salient entities in context
            entities = loom.context.get_salient_entities()
            print()
            print("  +-- Salient Entities ---------------------------+")
            if not entities:
                print("  |  No entities tracked yet.")
            else:
                for entity, salience in entities:
                    print(f"  |  {entity}: {salience:.2f}")
            print("  +-----------------------------------------------+")
            print()

        else:
            # Process as natural language
            # Check if it's a multi-sentence input (paragraph)
            if '. ' in user_input or len(user_input) > 100:
                # Use paragraph processing
                response = loom.process_text(user_input)
            else:
                # Single statement - use activation-enhanced processing
                response = loom.process_with_activation(user_input)
            print(f"  loom > {response}")


if __name__ == "__main__":
    run_cli()
