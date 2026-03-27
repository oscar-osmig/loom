"""
Provenance tracking for Loom facts.
Tracks where facts came from and their dependencies.
"""

from dataclasses import dataclass, field, asdict
from typing import List, Optional
from datetime import datetime
from enum import Enum
import uuid


class SourceType(Enum):
    """How a fact was added to the knowledge base."""
    USER = "user"              # Directly stated by user
    INFERENCE = "inference"    # Derived by inference engine
    CLARIFICATION = "clarification"  # Added via clarification dialogue
    INHERITANCE = "inheritance"  # Propagated from parent category
    SYSTEM = "system"          # System-generated (e.g., self-knowledge)


@dataclass
class FactReference:
    """Reference to a specific fact (subject, relation, object triple)."""
    subject: str
    relation: str
    object: str

    def to_dict(self) -> dict:
        return {"subject": self.subject, "relation": self.relation, "object": self.object}

    @classmethod
    def from_dict(cls, d: dict) -> "FactReference":
        return cls(subject=d["subject"], relation=d["relation"], object=d["object"])

    def __hash__(self):
        return hash((self.subject, self.relation, self.object))

    def __eq__(self, other):
        if not isinstance(other, FactReference):
            return False
        return (self.subject, self.relation, self.object) == (other.subject, other.relation, other.object)


@dataclass
class Provenance:
    """
    Provenance metadata for a fact.
    Tracks origin, dependencies, and derivation information.
    """
    source_type: SourceType = SourceType.USER
    premises: List[FactReference] = field(default_factory=list)
    rule_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    speaker_id: Optional[str] = None
    derivation_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])

    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            "source_type": self.source_type.value,
            "premises": [p.to_dict() for p in self.premises],
            "rule_id": self.rule_id,
            "created_at": self.created_at.isoformat(),
            "speaker_id": self.speaker_id,
            "derivation_id": self.derivation_id,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Provenance":
        """Create from dictionary (from storage)."""
        if not d:
            return cls()
        return cls(
            source_type=SourceType(d.get("source_type", "user")),
            premises=[FactReference.from_dict(p) for p in d.get("premises", [])],
            rule_id=d.get("rule_id"),
            created_at=datetime.fromisoformat(d["created_at"]) if d.get("created_at") else datetime.utcnow(),
            speaker_id=d.get("speaker_id"),
            derivation_id=d.get("derivation_id", str(uuid.uuid4())[:8]),
        )

    @classmethod
    def user(cls, speaker_id: Optional[str] = None) -> "Provenance":
        """Create provenance for a user-stated fact."""
        return cls(source_type=SourceType.USER, speaker_id=speaker_id)

    @classmethod
    def inference(cls, premises: List[FactReference], rule_id: str) -> "Provenance":
        """Create provenance for an inferred fact."""
        return cls(
            source_type=SourceType.INFERENCE,
            premises=premises,
            rule_id=rule_id,
        )

    @classmethod
    def inheritance(cls, parent_fact: FactReference) -> "Provenance":
        """Create provenance for an inherited fact."""
        return cls(
            source_type=SourceType.INHERITANCE,
            premises=[parent_fact],
            rule_id="inheritance",
        )

    @classmethod
    def system(cls) -> "Provenance":
        """Create provenance for system-generated facts."""
        return cls(source_type=SourceType.SYSTEM)


# Confidence levels with semantic meaning
CONFIDENCE_HIGH = "high"      # Directly stated by user or verified
CONFIDENCE_MEDIUM = "medium"  # Inferred with strong support
CONFIDENCE_LOW = "low"        # Weak inference or needs verification


def confidence_for_source(source_type: SourceType) -> str:
    """Get default confidence level based on source type."""
    if source_type == SourceType.USER:
        return CONFIDENCE_HIGH
    elif source_type == SourceType.INFERENCE:
        return CONFIDENCE_MEDIUM
    elif source_type == SourceType.INHERITANCE:
        return CONFIDENCE_MEDIUM
    elif source_type == SourceType.CLARIFICATION:
        return CONFIDENCE_HIGH
    else:
        return CONFIDENCE_LOW


class DependencyGraph:
    """
    Tracks dependencies between facts for truth maintenance.
    When a fact is retracted, dependent facts can be invalidated.
    """

    def __init__(self):
        # Map from fact -> facts that depend on it
        self._dependents: dict[FactReference, set[FactReference]] = {}
        # Map from fact -> facts it depends on
        self._dependencies: dict[FactReference, set[FactReference]] = {}

    def add_dependency(self, fact: FactReference, depends_on: FactReference):
        """Record that `fact` depends on `depends_on`."""
        if depends_on not in self._dependents:
            self._dependents[depends_on] = set()
        self._dependents[depends_on].add(fact)

        if fact not in self._dependencies:
            self._dependencies[fact] = set()
        self._dependencies[fact].add(depends_on)

    def add_dependencies(self, fact: FactReference, premises: List[FactReference]):
        """Record that `fact` depends on all `premises`."""
        for premise in premises:
            self.add_dependency(fact, premise)

    def get_dependents(self, fact: FactReference) -> set[FactReference]:
        """Get all facts that directly depend on this fact."""
        return self._dependents.get(fact, set())

    def get_all_dependents(self, fact: FactReference) -> set[FactReference]:
        """Get all facts that depend on this fact (transitive closure)."""
        result = set()
        to_process = [fact]

        while to_process:
            current = to_process.pop()
            for dependent in self._dependents.get(current, set()):
                if dependent not in result:
                    result.add(dependent)
                    to_process.append(dependent)

        return result

    def remove_fact(self, fact: FactReference):
        """Remove a fact from the dependency graph."""
        # Remove from dependents of its dependencies
        for dep in self._dependencies.get(fact, set()):
            if dep in self._dependents:
                self._dependents[dep].discard(fact)

        # Remove its own entries
        self._dependents.pop(fact, None)
        self._dependencies.pop(fact, None)

    def get_dependencies(self, fact: FactReference) -> set[FactReference]:
        """Get all facts this fact depends on."""
        return self._dependencies.get(fact, set())
