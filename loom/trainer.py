"""
Trainer module for Loom.
Pre-loads knowledge packs to give Loom a foundation to build upon.
"""

import json
import os

# Knowledge packs - each is a list of (subject, relation, object) tuples
KNOWLEDGE_PACKS = {
    "animals": [
        # Categories
        ("dogs", "is", "mammals"),
        ("cats", "is", "mammals"),
        ("birds", "is", "animals"),
        ("fish", "is", "animals"),
        ("mammals", "is", "animals"),
        ("reptiles", "is", "animals"),
        ("insects", "is", "animals"),

        # Properties
        ("dogs", "has", "four legs"),
        ("dogs", "has", "fur"),
        ("dogs", "has", "a tail"),
        ("cats", "has", "four legs"),
        ("cats", "has", "fur"),
        ("cats", "has", "whiskers"),
        ("birds", "has", "wings"),
        ("birds", "has", "feathers"),
        ("birds", "has", "a beak"),
        ("fish", "has", "fins"),
        ("fish", "has", "gills"),
        ("fish", "has", "scales"),

        # Abilities
        ("dogs", "can", "bark"),
        ("dogs", "can", "run"),
        ("dogs", "can", "swim"),
        ("cats", "can", "meow"),
        ("cats", "can", "climb"),
        ("cats", "can", "hunt"),
        ("birds", "can", "fly"),
        ("birds", "can", "sing"),
        ("fish", "can", "swim"),

        # Habitats
        ("fish", "lives_in", "water"),
        ("birds", "lives_in", "nests"),
        ("bears", "lives_in", "forests"),
        ("penguins", "lives_in", "antarctica"),
        ("camels", "lives_in", "deserts"),

        # Diet
        ("cats", "eats", "fish"),
        ("cats", "eats", "mice"),
        ("dogs", "eats", "meat"),
        ("birds", "eats", "seeds"),
        ("birds", "eats", "worms"),
        ("cows", "eats", "grass"),
        ("lions", "eats", "meat"),

        # Specific animals
        ("lions", "is", "mammals"),
        ("lions", "is", "predators"),
        ("elephants", "is", "mammals"),
        ("elephants", "has", "trunk"),
        ("elephants", "has", "tusks"),
        ("whales", "is", "mammals"),
        ("whales", "lives_in", "ocean"),
        ("dolphins", "is", "mammals"),
        ("dolphins", "can", "swim"),
        ("dolphins", "is", "intelligent"),
    ],

    "nature": [
        # Weather causes
        ("rain", "causes", "floods"),
        ("rain", "causes", "wet ground"),
        ("sun", "causes", "heat"),
        ("sun", "causes", "light"),
        ("wind", "causes", "waves"),
        ("cold", "causes", "ice"),
        ("heat", "causes", "evaporation"),
        ("evaporation", "causes", "clouds"),
        ("clouds", "causes", "rain"),

        # Nature facts
        ("trees", "has", "leaves"),
        ("trees", "has", "roots"),
        ("trees", "has", "branches"),
        ("trees", "needs", "water"),
        ("trees", "needs", "sunlight"),
        ("plants", "needs", "water"),
        ("plants", "needs", "sunlight"),
        ("flowers", "has", "petals"),
        ("flowers", "is", "plants"),

        # Colors
        ("sky", "color", "blue"),
        ("grass", "color", "green"),
        ("sun", "color", "yellow"),
        ("snow", "color", "white"),
        ("roses", "color", "red"),
        ("leaves", "color", "green"),

        # Water cycle
        ("ocean", "contains", "salt water"),
        ("rivers", "contains", "fresh water"),
        ("lakes", "contains", "fresh water"),
        ("rain", "is", "water"),
        ("snow", "is", "frozen water"),
        ("ice", "is", "frozen water"),
    ],

    "science": [
        # Physics
        ("gravity", "causes", "falling"),
        ("heat", "causes", "expansion"),
        ("cold", "causes", "contraction"),
        ("friction", "causes", "heat"),
        ("light", "is", "energy"),
        ("sound", "is", "vibration"),

        # Solar system
        ("earth", "is", "planet"),
        ("mars", "is", "planet"),
        ("jupiter", "is", "planet"),
        ("sun", "is", "star"),
        ("moon", "is", "satellite"),
        ("earth", "has", "moon"),
        ("jupiter", "has", "moons"),

        # Elements
        ("water", "is", "liquid"),
        ("ice", "is", "solid"),
        ("steam", "is", "gas"),
        ("oxygen", "is", "gas"),
        ("iron", "is", "metal"),
        ("gold", "is", "metal"),

        # Biology
        ("humans", "is", "mammals"),
        ("humans", "needs", "oxygen"),
        ("humans", "needs", "water"),
        ("humans", "needs", "food"),
        ("brain", "is", "organ"),
        ("heart", "is", "organ"),
        ("lungs", "is", "organ"),
    ],

    "geography": [
        # Continents
        ("africa", "is", "continent"),
        ("asia", "is", "continent"),
        ("europe", "is", "continent"),
        ("america", "is", "continent"),
        ("australia", "is", "continent"),

        # Countries
        ("france", "located_in", "europe"),
        ("japan", "located_in", "asia"),
        ("brazil", "located_in", "america"),
        ("egypt", "located_in", "africa"),

        # Landmarks
        ("eiffel tower", "located_in", "paris"),
        ("paris", "located_in", "france"),
        ("pyramids", "located_in", "egypt"),
        ("mount everest", "located_in", "asia"),

        # Features
        ("sahara", "is", "desert"),
        ("amazon", "is", "river"),
        ("pacific", "is", "ocean"),
        ("atlantic", "is", "ocean"),
        ("alps", "is", "mountains"),
    ],
}


def train(loom, pack_name: str) -> tuple[int, str]:
    """
    Train loom with a knowledge pack.
    Returns (count, message).
    """
    if pack_name not in KNOWLEDGE_PACKS:
        available = ", ".join(KNOWLEDGE_PACKS.keys())
        return 0, f"Unknown pack '{pack_name}'. Available: {available}"

    facts = KNOWLEDGE_PACKS[pack_name]
    count = 0

    for subject, relation, obj in facts:
        # Check if fact already exists
        existing = loom.get(subject, relation) or []
        if obj not in [e.lower() for e in existing]:
            loom.add_fact(subject, relation, obj)
            count += 1

    return count, f"Loaded {count} facts from '{pack_name}' pack."


def train_from_file(loom, filepath: str) -> tuple[int, str]:
    """
    Train loom from a custom file.
    Supports .json and .txt formats.

    JSON format: [{"subject": "X", "relation": "is", "object": "Y"}, ...]
    TXT format: subject | relation | object (one per line)
    """
    if not os.path.exists(filepath):
        return 0, f"File not found: {filepath}"

    count = 0

    try:
        if filepath.endswith('.json'):
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)

            for item in data:
                subj = item.get('subject', item.get('s', ''))
                rel = item.get('relation', item.get('r', ''))
                obj = item.get('object', item.get('o', ''))

                if subj and rel and obj:
                    loom.add_fact(subj, rel, obj)
                    count += 1

        else:  # Assume text format
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue

                    # Support both | and , as separators
                    if '|' in line:
                        parts = [p.strip() for p in line.split('|')]
                    else:
                        parts = [p.strip() for p in line.split(',')]

                    if len(parts) >= 3:
                        loom.add_fact(parts[0], parts[1], parts[2])
                        count += 1

        return count, f"Loaded {count} facts from '{os.path.basename(filepath)}'."

    except Exception as e:
        return 0, f"Error loading file: {e}"


def list_packs() -> list[str]:
    """Return list of available knowledge packs."""
    return list(KNOWLEDGE_PACKS.keys())


def get_pack_info(pack_name: str) -> str:
    """Get info about a knowledge pack."""
    if pack_name not in KNOWLEDGE_PACKS:
        return f"Unknown pack: {pack_name}"

    facts = KNOWLEDGE_PACKS[pack_name]
    relations = {}

    for _, rel, _ in facts:
        relations[rel] = relations.get(rel, 0) + 1

    info = [f"Pack '{pack_name}': {len(facts)} facts"]
    for rel, count in sorted(relations.items(), key=lambda x: -x[1]):
        info.append(f"  - {rel}: {count}")

    return "\n".join(info)
