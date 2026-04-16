"""
Pydantic models and enums for Loom's data layer.
Provides validated schemas for facts, properties, and metadata.
"""

from enum import Enum
from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, Field
import uuid


class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TemporalScope(str, Enum):
    ALWAYS = "always"
    CURRENTLY = "currently"
    PAST = "past"
    FUTURE = "future"
    SOMETIMES = "sometimes"


class SourceType(str, Enum):
    USER = "user"
    INFERENCE = "inference"
    INHERITANCE = "inheritance"
    CLARIFICATION = "clarification"
    SYSTEM = "system"
    RULE = "rule"
    DISCOVERY = "discovery"


class FactProperties(BaseModel):
    """Validated properties for a knowledge fact."""
    confidence: ConfidenceLevel = ConfidenceLevel.HIGH
    temporal: TemporalScope = TemporalScope.ALWAYS
    scope: str = "universal"
    conditions: List[str] = Field(default_factory=list)
    source_type: SourceType = SourceType.USER
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    premises: List[dict] = Field(default_factory=list)
    rule_id: Optional[str] = None
    speaker_id: Optional[str] = None
    derivation_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])

    def to_mongo(self) -> dict:
        """Convert to a plain dict for MongoDB storage."""
        d = self.model_dump()
        d['confidence'] = d['confidence']  # already string via str enum
        d['temporal'] = d['temporal']
        d['source_type'] = d['source_type']
        d['created_at'] = d['created_at'].isoformat() if isinstance(d['created_at'], datetime) else d['created_at']
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "FactProperties":
        """Build from a plain dict, tolerating missing/extra keys."""
        if not d:
            return cls()
        filtered = {}
        for key in cls.model_fields:
            if key in d and d[key] is not None:
                filtered[key] = d[key]
        return cls(**filtered)


class Fact(BaseModel):
    """A single knowledge fact (triple + metadata)."""
    subject: str
    relation: str
    object: str
    context: str = "general"
    properties: FactProperties = Field(default_factory=FactProperties)

    def to_mongo(self, instance: str) -> dict:
        """Convert to a MongoDB document."""
        return {
            "instance": instance,
            "subject": self.subject,
            "relation": self.relation,
            "object": self.object,
            "context": self.context,
            "properties": self.properties.to_mongo(),
        }
