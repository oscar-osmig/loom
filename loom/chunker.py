"""
Text Chunker for Loom.
Implements cognitive chunking theory for processing paragraphs and large texts.

Breaks text into semantic units (chunks) and identifies discourse relations
between them using Rhetorical Structure Theory (RST) principles.
"""

import re
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field


@dataclass
class Chunk:
    """Represents a semantic chunk of text."""
    text: str
    chunk_type: str = "statement"  # statement, question, command
    connector: Optional[str] = None
    relation_type: Optional[str] = None
    entities: List[str] = field(default_factory=list)
    is_nucleus: bool = True  # RST: nucleus (main) vs satellite (supporting)


@dataclass
class ChunkedText:
    """Result of chunking a text."""
    original: str
    sentences: List[str]
    chunks: List[Chunk]
    paragraph_theme: Optional[str] = None
    discourse_structure: List[Dict] = field(default_factory=list)


class TextChunker:
    """
    Breaks text into cognitive chunks for processing.
    Identifies discourse relations between chunks.
    """

    # Discourse connectors grouped by relation type
    DISCOURSE_CONNECTORS = {
        'causal': [
            'because', 'since', 'so', 'therefore', 'thus', 'hence',
            'consequently', 'as a result', 'causes', 'leads to',
            'due to', 'owing to', 'for this reason', 'that is why'
        ],
        'contrast': [
            'but', 'however', 'although', 'though', 'whereas',
            'while', 'yet', 'nevertheless', 'nonetheless',
            'on the other hand', 'in contrast', 'unlike',
            'instead', 'rather', 'conversely', 'still'
        ],
        'elaboration': [
            'also', 'furthermore', 'moreover', 'additionally',
            'in addition', 'besides', 'in fact', 'indeed',
            'specifically', 'particularly', 'especially',
            'that is', 'namely', 'in other words', 'for instance'
        ],
        'temporal': [
            'then', 'after', 'before', 'when', 'while', 'during',
            'first', 'second', 'third', 'finally', 'next',
            'subsequently', 'previously', 'meanwhile', 'later',
            'earlier', 'soon', 'eventually', 'initially', 'afterwards'
        ],
        'example': [
            'for example', 'for instance', 'such as', 'like',
            'including', 'e.g.', 'i.e.', 'to illustrate',
            'as an example', 'in particular'
        ],
        'condition': [
            'if', 'unless', 'when', 'whenever', 'provided that',
            'assuming', 'in case', 'supposing', 'given that',
            'only if', 'except when', 'except if'
        ],
        'similarity': [
            'similarly', 'likewise', 'in the same way', 'equally',
            'just as', 'as with', 'comparable to', 'like'
        ],
        'conclusion': [
            'in conclusion', 'to summarize', 'in summary', 'overall',
            'to sum up', 'in short', 'ultimately', 'finally',
            'all in all', 'in the end'
        ]
    }

    # Sentence ending patterns
    SENTENCE_ENDINGS = re.compile(r'(?<=[.!?])\s+(?=[A-Z])')

    # Clause separators
    CLAUSE_SEPARATORS = [
        ', and ', ', but ', ', or ', ', so ', ', yet ',
        '; ', ' - ', ' — ',
        ', which ', ', who ', ', that ', ', where ', ', when '
    ]

    def __init__(self):
        # Build reverse lookup: connector -> relation type
        self.connector_to_relation = {}
        for rel_type, connectors in self.DISCOURSE_CONNECTORS.items():
            for connector in connectors:
                self.connector_to_relation[connector.lower()] = rel_type

    def chunk_text(self, text: str) -> ChunkedText:
        """
        Main entry point: chunk a text into semantic units.

        Args:
            text: Input text (can be paragraph or multiple paragraphs)

        Returns:
            ChunkedText with sentences, chunks, and discourse structure
        """
        # Normalize whitespace
        text = ' '.join(text.split())

        # Split into sentences
        sentences = self.split_sentences(text)

        # Process each sentence into chunks
        all_chunks = []
        discourse_structure = []

        prev_chunk = None
        for i, sentence in enumerate(sentences):
            # Split sentence into clauses
            clauses = self.split_clauses(sentence)

            for j, clause in enumerate(clauses):
                if not clause.strip():
                    continue

                # Detect connector and relation
                connector, relation = self.detect_connector(clause)

                # Determine chunk type
                chunk_type = self.detect_chunk_type(clause)

                # Determine if nucleus or satellite
                is_nucleus = self.is_nucleus(clause, connector, j == 0)

                chunk = Chunk(
                    text=clause.strip(),
                    chunk_type=chunk_type,
                    connector=connector,
                    relation_type=relation,
                    is_nucleus=is_nucleus
                )

                # Record discourse relation to previous chunk
                if prev_chunk and relation:
                    discourse_structure.append({
                        'from_chunk': len(all_chunks) - 1,
                        'to_chunk': len(all_chunks),
                        'relation': relation,
                        'connector': connector
                    })

                all_chunks.append(chunk)
                prev_chunk = chunk

        # Detect paragraph theme (most mentioned concepts)
        theme = self.detect_theme(all_chunks) if all_chunks else None

        return ChunkedText(
            original=text,
            sentences=sentences,
            chunks=all_chunks,
            paragraph_theme=theme,
            discourse_structure=discourse_structure
        )

    def split_sentences(self, text: str) -> List[str]:
        """Split text into sentences."""
        # Handle common abbreviations
        text = re.sub(r'\b(Mr|Mrs|Ms|Dr|Prof|Sr|Jr|vs|etc|e\.g|i\.e)\.',
                      r'\1<PERIOD>', text)

        # Split on sentence endings
        sentences = self.SENTENCE_ENDINGS.split(text)

        # Restore periods
        sentences = [s.replace('<PERIOD>', '.').strip() for s in sentences]

        # Filter empty sentences
        return [s for s in sentences if s]

    def split_clauses(self, sentence: str) -> List[str]:
        """Split a sentence into clauses."""
        clauses = [sentence]

        for separator in self.CLAUSE_SEPARATORS:
            new_clauses = []
            for clause in clauses:
                parts = clause.split(separator)
                if len(parts) > 1:
                    # Keep the connector with the second part
                    new_clauses.append(parts[0])
                    for part in parts[1:]:
                        connector = separator.strip(' ,;')
                        new_clauses.append(f"{connector} {part}")
                else:
                    new_clauses.append(clause)
            clauses = new_clauses

        return [c.strip() for c in clauses if c.strip()]

    def detect_connector(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Detect discourse connector and its relation type.

        Returns:
            (connector, relation_type) or (None, None)
        """
        text_lower = text.lower()

        # Check for multi-word connectors first (longer matches)
        all_connectors = []
        for connectors in self.DISCOURSE_CONNECTORS.values():
            all_connectors.extend(connectors)
        all_connectors.sort(key=len, reverse=True)

        for connector in all_connectors:
            # Check if text starts with connector or has it after punctuation
            patterns = [
                rf'^{re.escape(connector)}\b',
                rf'^[,;]\s*{re.escape(connector)}\b',
                rf'\b{re.escape(connector)}\b'
            ]
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    return connector, self.connector_to_relation.get(connector)

        return None, None

    def detect_chunk_type(self, text: str) -> str:
        """Detect if chunk is statement, question, or command."""
        text = text.strip()

        if text.endswith('?'):
            return 'question'

        # Command indicators
        command_starters = ['do', 'please', 'make', 'let', 'try', 'remember']
        first_word = text.split()[0].lower() if text.split() else ''
        if first_word in command_starters:
            return 'command'

        return 'statement'

    def is_nucleus(self, text: str, connector: Optional[str],
                   is_first_clause: bool) -> bool:
        """
        Determine if this chunk is a nucleus (main point) or satellite (supporting).

        RST principles:
        - First clause is usually nucleus
        - Clauses with elaboration connectors are usually satellites
        - Clauses with causal 'because' are usually satellites
        """
        if is_first_clause and not connector:
            return True

        if connector:
            relation = self.connector_to_relation.get(connector)
            # These relations typically mark satellites
            if relation in ['elaboration', 'example', 'condition']:
                return False
            # 'because' introduces a satellite (the reason)
            if connector in ['because', 'since', 'as']:
                return False

        return True

    def detect_theme(self, chunks: List[Chunk]) -> Optional[str]:
        """Detect the main theme of the chunks (most frequent entity)."""
        if not chunks:
            return None

        # Count word frequencies (simplified entity extraction)
        word_counts: Dict[str, int] = {}
        stop_words = {
            'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
            'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
            'would', 'could', 'should', 'may', 'might', 'must', 'shall',
            'can', 'need', 'dare', 'ought', 'used', 'to', 'of', 'in',
            'for', 'on', 'with', 'at', 'by', 'from', 'as', 'into',
            'through', 'during', 'before', 'after', 'above', 'below',
            'between', 'under', 'again', 'further', 'then', 'once',
            'and', 'but', 'or', 'nor', 'so', 'yet', 'both', 'either',
            'neither', 'not', 'only', 'own', 'same', 'than', 'too',
            'very', 'just', 'also', 'now', 'it', 'its', 'they', 'them',
            'their', 'this', 'that', 'these', 'those', 'which', 'who',
            'whom', 'whose', 'what', 'when', 'where', 'why', 'how'
        }

        for chunk in chunks:
            words = re.findall(r'\b[a-zA-Z]+\b', chunk.text.lower())
            for word in words:
                if word not in stop_words and len(word) > 2:
                    word_counts[word] = word_counts.get(word, 0) + 1

        if word_counts:
            return max(word_counts, key=word_counts.get)

        return None

    def get_discourse_relations(self, chunked: ChunkedText) -> List[Dict]:
        """
        Extract discourse relations between chunks.
        Returns relations suitable for knowledge graph insertion.
        """
        relations = []

        for rel in chunked.discourse_structure:
            from_idx = rel['from_chunk']
            to_idx = rel['to_chunk']

            if from_idx < len(chunked.chunks) and to_idx < len(chunked.chunks):
                from_chunk = chunked.chunks[from_idx]
                to_chunk = chunked.chunks[to_idx]

                relations.append({
                    'from_text': from_chunk.text,
                    'to_text': to_chunk.text,
                    'relation': rel['relation'],
                    'connector': rel['connector'],
                    'from_is_nucleus': from_chunk.is_nucleus,
                    'to_is_nucleus': to_chunk.is_nucleus
                })

        return relations

    def process_for_knowledge(self, text: str) -> Dict:
        """
        Process text and return structured data for knowledge extraction.

        Returns dict with:
        - chunks: list of chunk texts
        - relations: discourse relations between chunks
        - theme: detected theme
        - processing_order: suggested order to process chunks
        """
        chunked = self.chunk_text(text)

        # Determine processing order (nuclei first, then satellites)
        nuclei_indices = [i for i, c in enumerate(chunked.chunks) if c.is_nucleus]
        satellite_indices = [i for i, c in enumerate(chunked.chunks) if not c.is_nucleus]
        processing_order = nuclei_indices + satellite_indices

        return {
            'chunks': [c.text for c in chunked.chunks],
            'chunk_types': [c.chunk_type for c in chunked.chunks],
            'relations': self.get_discourse_relations(chunked),
            'theme': chunked.paragraph_theme,
            'processing_order': processing_order,
            'sentence_count': len(chunked.sentences),
            'chunk_count': len(chunked.chunks)
        }

    def iter_chunks(self, text: str):
        """
        Generator that yields chunks one at a time for streaming processing.
        """
        chunked = self.chunk_text(text)

        # Yield nuclei first
        for i, chunk in enumerate(chunked.chunks):
            if chunk.is_nucleus:
                yield {
                    'index': i,
                    'text': chunk.text,
                    'type': chunk.chunk_type,
                    'relation': chunk.relation_type,
                    'connector': chunk.connector,
                    'is_nucleus': True
                }

        # Then satellites
        for i, chunk in enumerate(chunked.chunks):
            if not chunk.is_nucleus:
                yield {
                    'index': i,
                    'text': chunk.text,
                    'type': chunk.chunk_type,
                    'relation': chunk.relation_type,
                    'connector': chunk.connector,
                    'is_nucleus': False
                }
