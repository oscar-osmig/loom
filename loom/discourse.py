"""
Discourse analysis module for Loom.
Extracts knowledge from natural speech patterns using discourse markers.

Based on linguistic research:
- Hebbian learning: concepts mentioned together strengthen connections
- Discourse markers: words that signal semantic relationships
- Cell assemblies: related concepts that activate together
"""

import re

# Discourse markers that signal relationships
DISCOURSE_MARKERS = {
    # Additive - adds information to existing concept
    "additive": [
        "also", "too", "as well", "in addition", "additionally",
        "moreover", "furthermore", "plus", "and also", "besides",
        "another thing", "on top of that", "not only", "along with"
    ],

    # Causal - shows cause and effect
    "causal": [
        "because", "since", "so", "therefore", "thus", "hence",
        "as a result", "consequently", "due to", "owing to",
        "leads to", "causes", "results in", "makes", "creates",
        "that's why", "for this reason", "this means"
    ],

    # Similarity - shows likeness between concepts
    "similarity": [
        "like", "similarly", "likewise", "same as", "just like",
        "just as", "similar to", "resembles", "is like", "are like",
        "reminds me of", "comparable to", "equivalent to"
    ],

    # Contrastive - shows difference or opposition
    "contrastive": [
        "but", "however", "although", "yet", "nevertheless",
        "unlike", "whereas", "while", "on the other hand",
        "in contrast", "different from", "instead", "rather than",
        "except", "not like"
    ],

    # Exemplification - gives examples
    "example": [
        "for example", "for instance", "such as", "like",
        "e.g.", "including", "especially", "particularly",
        "one example is", "to illustrate"
    ],

    # Elaboration - expands on a concept
    "elaboration": [
        "meaning", "that is", "in other words", "i mean",
        "specifically", "namely", "which means", "basically",
        "essentially", "actually", "in fact", "really"
    ],

    # Temporal - shows time relationships
    "temporal": [
        "then", "after", "before", "when", "while", "during",
        "first", "next", "finally", "later", "earlier",
        "at the same time", "meanwhile", "subsequently"
    ],

    # Conditional - shows conditions
    "conditional": [
        "if", "unless", "when", "whenever", "in case",
        "provided that", "as long as", "assuming"
    ],
}

# Flatten for quick lookup
ALL_MARKERS = {}
for category, markers in DISCOURSE_MARKERS.items():
    for marker in markers:
        ALL_MARKERS[marker] = category


def find_discourse_markers(text: str) -> list:
    """Find all discourse markers in text and their positions."""
    text_lower = text.lower()
    found = []

    for marker, category in ALL_MARKERS.items():
        # Use word boundaries to avoid partial matches
        pattern = r'\b' + re.escape(marker) + r'\b'
        for match in re.finditer(pattern, text_lower):
            found.append({
                "marker": marker,
                "category": category,
                "start": match.start(),
                "end": match.end()
            })

    # Sort by position
    found.sort(key=lambda x: x["start"])
    return found


def extract_connected_concepts(text: str) -> list:
    """
    Extract concepts that should be connected based on discourse markers.
    Returns list of (concept1, relation, concept2, marker_used) tuples.
    """
    connections = []
    markers = find_discourse_markers(text)
    text_lower = text.lower()

    for marker_info in markers:
        marker = marker_info["marker"]
        category = marker_info["category"]
        pos = marker_info["start"]

        # Get text before and after marker
        before = text_lower[:pos].strip()
        after = text_lower[marker_info["end"]:].strip()

        # Clean up
        before = re.sub(r'^(and|but|so|well|oh|um|uh)\s+', '', before)
        after = re.sub(r'^(that|it|they|this)\s+', '', after)

        if not before or not after:
            continue

        # Map category to relation
        relation_map = {
            "additive": "has",  # X also has Y -> adds property
            "causal": "causes",  # X because Y -> causal link
            "similarity": "is_like",  # X like Y -> similarity
            "contrastive": "differs_from",  # X but Y -> contrast
            "example": "example_of",  # X such as Y -> instance
            "elaboration": "means",  # X meaning Y -> definition
            "temporal": "then",  # X then Y -> sequence
            "conditional": "if_then",  # if X then Y -> condition
        }

        relation = relation_map.get(category, "related_to")
        connections.append((before, relation, after, marker))

    return connections


def extract_cooccurrence(text: str) -> list:
    """
    Hebbian principle: concepts mentioned together should connect.
    Extract noun phrases that appear in same sentence.
    """
    # Simple extraction of potential concepts (nouns/noun phrases)
    # Remove common words
    stopwords = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been",
        "have", "has", "had", "do", "does", "did", "will", "would",
        "could", "should", "may", "might", "must", "can", "this",
        "that", "these", "those", "i", "you", "he", "she", "it",
        "we", "they", "my", "your", "his", "her", "its", "our",
        "their", "what", "which", "who", "whom", "where", "when",
        "why", "how", "all", "each", "every", "both", "few", "more",
        "most", "other", "some", "such", "no", "not", "only", "own",
        "same", "so", "than", "too", "very", "just", "also", "and",
        "but", "or", "if", "because", "as", "of", "to", "in", "for",
        "on", "with", "at", "by", "from", "about", "into", "through"
    }

    # Split into sentences
    sentences = re.split(r'[.!?]', text.lower())
    cooccurrences = []

    for sentence in sentences:
        words = re.findall(r'\b[a-z]+\b', sentence)
        concepts = [w for w in words if w not in stopwords and len(w) > 2]

        # Concepts in same sentence are related (Hebbian)
        for i, c1 in enumerate(concepts):
            for c2 in concepts[i+1:]:
                if c1 != c2:
                    cooccurrences.append((c1, "mentioned_with", c2))

    return cooccurrences


def analyze_speech(text: str) -> dict:
    """
    Full analysis of natural speech for knowledge extraction.
    Returns structured analysis with connections to create.
    """
    return {
        "discourse_connections": extract_connected_concepts(text),
        "cooccurrences": extract_cooccurrence(text),
        "markers_found": find_discourse_markers(text)
    }
