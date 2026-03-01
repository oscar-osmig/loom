"""
Loom Training Module - Methods for training the knowledge system.

Contains:
- train: Main training entry point supporting multiple formats
- train_facts: Train from tuples
- train_dicts: Train from dictionaries
- train_statements: Train from natural language
- train_batch: Batch training for efficiency
- available_packs: List available knowledge packs
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .brain import Loom


class TrainingMixin:
    """Mixin class providing training capabilities for Loom."""

    def train(self: "Loom", source) -> int:
        """
        Train Loom with knowledge from various sources.

        Args:
            source: Can be one of:
                - str: Pack name ("animals", "nature", "science", "geography")
                       or file path (.json, .txt)
                - list of tuples: [("dogs", "is", "animals"), ...]
                - list of dicts: [{"subject": "dogs", "relation": "is", "object": "animals"}, ...]
                - list of strings: ["dogs are animals", "cats can meow", ...]

        Returns:
            Number of facts added.

        Examples:
            loom.train("animals")  # Load animals pack
            loom.train("data.json")  # Load from JSON file
            loom.train([("dogs", "is", "mammals"), ("cats", "can", "meow")])
            loom.train(["dogs are mammals", "cats can meow"])
        """
        if isinstance(source, str):
            # Check if it's a pack name or file path
            from .trainer import KNOWLEDGE_PACKS, train as train_pack, train_from_file
            if source in KNOWLEDGE_PACKS:
                count, _ = train_pack(self, source)
                return count
            else:
                # Assume it's a file path
                count, _ = train_from_file(self, source)
                return count

        elif isinstance(source, list):
            if not source:
                return 0

            # Detect format from first item
            first = source[0]

            if isinstance(first, tuple) and len(first) >= 3:
                # List of tuples: [(subj, rel, obj), ...]
                return self.train_facts(source)

            elif isinstance(first, dict):
                # List of dicts: [{"subject": ..., "relation": ..., "object": ...}, ...]
                return self.train_dicts(source)

            elif isinstance(first, str):
                # List of natural language statements
                return self.train_statements(source)

        return 0

    def train_facts(self: "Loom", facts: list) -> int:
        """
        Train from a list of (subject, relation, object) tuples.

        Args:
            facts: List of tuples like [("dogs", "is", "animals"), ...]

        Returns:
            Number of facts added.
        """
        count = 0
        for fact in facts:
            if len(fact) >= 3:
                subj, rel, obj = fact[0], fact[1], fact[2]
                existing = self.get(subj, rel) or []
                if obj.lower() not in [e.lower() for e in existing]:
                    self.add_fact(subj, rel, obj)
                    count += 1
        return count

    def train_dicts(self: "Loom", facts: list) -> int:
        """
        Train from a list of dictionaries.

        Args:
            facts: List of dicts like [{"subject": "dogs", "relation": "is", "object": "animals"}, ...]
                   Also accepts short forms: {"s": ..., "r": ..., "o": ...}

        Returns:
            Number of facts added.
        """
        count = 0
        for item in facts:
            subj = item.get('subject', item.get('s', ''))
            rel = item.get('relation', item.get('r', ''))
            obj = item.get('object', item.get('o', ''))

            if subj and rel and obj:
                existing = self.get(subj, rel) or []
                if obj.lower() not in [e.lower() for e in existing]:
                    self.add_fact(subj, rel, obj)
                    count += 1
        return count

    def train_statements(self: "Loom", statements: list, silent: bool = True) -> int:
        """
        Train from natural language statements.

        Args:
            statements: List of strings like ["dogs are animals", "cats can meow"]
            silent: If True, don't print responses (default True for bulk training)

        Returns:
            Number of statements processed.
        """
        count = 0
        for stmt in statements:
            if stmt and stmt.strip():
                response = self.process(stmt.strip())
                if not silent and self.verbose:
                    print(f"  {stmt} -> {response}")
                count += 1
        return count

    def train_batch(self: "Loom", facts: list, batch_size: int = 100) -> int:
        """
        Train from a large list of facts in batches (more efficient for MongoDB).

        Args:
            facts: List of (subject, relation, object) tuples
            batch_size: Number of facts per batch

        Returns:
            Number of facts added.
        """
        count = 0
        for i in range(0, len(facts), batch_size):
            batch = facts[i:i + batch_size]
            count += self.train_facts(batch)
        return count

    @staticmethod
    def available_packs() -> list:
        """Return list of available knowledge packs."""
        from .trainer import list_packs
        return list_packs()
