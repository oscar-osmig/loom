"""
JSON Fallback storage backend for Loom.
Used when MongoDB is not available.

Supports Quad + Properties schema:
- subject, relation, object, context (the quad)
- properties: {confidence, temporal, scope, conditions, source_type, ...}
"""

from collections import defaultdict
from datetime import datetime
import json
import os

# Default context for facts without explicit context
DEFAULT_CONTEXT = "general"

# Default properties template
DEFAULT_PROPERTIES = {
    "confidence": "high",
    "temporal": "always",      # always, sometimes, past, future
    "scope": "universal",      # universal, typical, specific
    "conditions": [],
    "source_type": "user",
    "created_at": None,
}


class JSONFallbackStorage:
    """
    Fallback storage that mimics MongoStorage interface but uses JSON files.
    Used when MongoDB is not available.
    """

    def __init__(self, memory_file: str = "loom_memory/loom_memory.json"):
        self.memory_file = memory_file
        self._data = self._load()

    def _load(self) -> dict:
        """Load data from JSON file."""
        default_data = {
            "facts": [],
            "procedures": {},
            "inferences": [],
            "conflicts": [],
            "frames": {}
        }

        if os.path.exists(self.memory_file):
            try:
                with open(self.memory_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # Handle legacy format (convert from old structure)
                if "knowledge" in data and "facts" not in data:
                    # Convert old format to new format
                    facts = []
                    for subj, relations in data.get("knowledge", {}).items():
                        for rel, objects in relations.items():
                            for obj in objects:
                                facts.append({
                                    "subject": subj,
                                    "relation": rel,
                                    "object": obj,
                                    "confidence": "high",
                                    "constraints": []
                                })
                    return {
                        "facts": facts,
                        "procedures": data.get("procedures", {}),
                        "inferences": data.get("inferences", []),
                        "conflicts": []
                    }

                # Ensure all required keys exist
                for key in default_data:
                    if key not in data:
                        data[key] = default_data[key]
                return data
            except Exception:
                pass
        return default_data

    def _save(self):
        """Save data to JSON file."""
        with open(self.memory_file, 'w', encoding='utf-8') as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)

    def add_fact(self, subject: str, relation: str, obj: str,
                 confidence: str = "high", constraints: list = None,
                 provenance: dict = None, context: str = None,
                 properties: dict = None) -> bool:
        """
        Add a fact with Quad + Properties schema.

        Args:
            subject: The subject of the fact
            relation: The relation type
            obj: The object of the fact
            confidence: Confidence level (legacy, moved to properties)
            constraints: Constraints (legacy, moved to properties.conditions)
            provenance: Provenance dict (legacy, merged into properties)
            context: Context for the fact (general, domestic, scientific, etc.)
            properties: Full properties dict with temporal, scope, etc.
        """
        ctx = context or DEFAULT_CONTEXT

        # Check for existing fact (same subject, relation, object, context)
        for fact in self._data["facts"]:
            if (fact["subject"] == subject and
                fact["relation"] == relation and
                fact["object"] == obj and
                fact.get("context", DEFAULT_CONTEXT) == ctx):
                return False

        # Build properties from new format or legacy parameters
        props = dict(DEFAULT_PROPERTIES)
        props["created_at"] = datetime.utcnow().isoformat()

        if properties:
            # New format - use provided properties
            props.update(properties)
        else:
            # Legacy format - convert to properties
            props["confidence"] = confidence
            props["conditions"] = constraints or []
            if provenance:
                props["source_type"] = provenance.get("source_type", "user")
                props["premises"] = provenance.get("premises", [])
                props["rule_id"] = provenance.get("rule_id")
                props["speaker_id"] = provenance.get("speaker_id")
                props["derivation_id"] = provenance.get("derivation_id")

        self._data["facts"].append({
            "subject": subject,
            "relation": relation,
            "object": obj,
            "context": ctx,
            "properties": props
        })
        self._save()
        return True

    def _normalize_fact(self, fact: dict) -> dict:
        """Normalize a fact to Quad + Properties format (for backward compat)."""
        if "context" not in fact:
            fact["context"] = DEFAULT_CONTEXT
        if "properties" not in fact:
            # Convert legacy format
            fact["properties"] = {
                "confidence": fact.get("confidence", "high"),
                "temporal": "always",
                "scope": "universal",
                "conditions": fact.get("constraints", []),
                "source_type": fact.get("provenance", {}).get("source_type", "user"),
                "created_at": fact.get("provenance", {}).get("created_at"),
                "premises": fact.get("provenance", {}).get("premises", []),
            }
        return fact

    def get_facts(self, subject: str, relation: str, context: str = None) -> list:
        """Get facts, optionally filtered by context."""
        results = []
        for f in self._data["facts"]:
            if f["subject"] == subject and f["relation"] == relation:
                f = self._normalize_fact(f)
                # If context specified, filter by it
                if context is None or f.get("context", DEFAULT_CONTEXT) == context:
                    results.append(f["object"])
        return results

    def get_facts_with_context(self, subject: str, relation: str) -> list:
        """Get facts with their context and properties."""
        results = []
        for f in self._data["facts"]:
            if f["subject"] == subject and f["relation"] == relation:
                f = self._normalize_fact(f)
                results.append({
                    "object": f["object"],
                    "context": f.get("context", DEFAULT_CONTEXT),
                    "properties": f.get("properties", {})
                })
        return results

    def get_all_facts_for_subject(self, subject: str) -> dict:
        result = defaultdict(list)
        for f in self._data["facts"]:
            if f["subject"] == subject:
                result[f["relation"]].append(f["object"])
        return dict(result)

    def remove_entity(self, entity: str) -> int:
        """
        Remove all facts where entity is the SUBJECT only.
        Does NOT remove facts where entity is the object (to preserve valid relations).
        Used for cleaning up junk neurons.

        Returns:
            Number of facts removed
        """
        original_count = len(self._data["facts"])
        # Only remove facts where entity is the subject
        self._data["facts"] = [
            f for f in self._data["facts"]
            if f["subject"] != entity
        ]
        removed = original_count - len(self._data["facts"])
        if removed > 0:
            self._save()
        return removed

    def get_fact_with_metadata(self, subject: str, relation: str, obj: str,
                                context: str = None) -> dict | None:
        """Get a specific fact with all its metadata."""
        for f in self._data["facts"]:
            if (f["subject"] == subject and
                f["relation"] == relation and
                f["object"] == obj):
                f = self._normalize_fact(f)
                if context is None or f.get("context", DEFAULT_CONTEXT) == context:
                    return f
        return None

    def get_facts_by_source_type(self, source_type: str) -> list:
        """Get all facts with a specific source type."""
        results = []
        for f in self._data["facts"]:
            f = self._normalize_fact(f)
            # Check both new properties format and legacy provenance
            src = f.get("properties", {}).get("source_type")
            if src is None:
                src = f.get("provenance", {}).get("source_type")
            if src == source_type:
                results.append(f)
        return results

    def get_facts_depending_on(self, subject: str, relation: str, obj: str) -> list:
        """
        Get all facts that depend on the given fact as a premise.
        Used for truth maintenance.
        """
        dependents = []
        for f in self._data["facts"]:
            f = self._normalize_fact(f)
            # Check both new properties format and legacy provenance
            premises = f.get("properties", {}).get("premises", [])
            if not premises:
                premises = f.get("provenance", {}).get("premises", [])
            for p in premises:
                if (p.get("subject") == subject and
                    p.get("relation") == relation and
                    p.get("object") == obj):
                    dependents.append(f)
                    break
        return dependents

    def get_inferred_facts(self) -> list:
        """Get all facts that were inferred (not directly stated by user)."""
        results = []
        for f in self._data["facts"]:
            f = self._normalize_fact(f)
            src = f.get("properties", {}).get("source_type")
            if src is None:
                src = f.get("provenance", {}).get("source_type")
            if src in ["inference", "inheritance"]:
                results.append(f)
        return results

    def retract_fact(self, subject: str, relation: str, obj: str,
                     cascade: bool = False) -> dict:
        """
        Remove a fact from the knowledge graph.

        Args:
            subject: The subject of the fact
            relation: The relation type
            obj: The object of the fact
            cascade: If True, also retract all facts that depend on this fact

        Returns:
            dict with 'retracted' (bool) and 'cascade_count' (int) keys
        """
        result = {"retracted": False, "cascade_count": 0, "cascaded_facts": []}

        # First, find dependents if cascade is enabled
        if cascade:
            dependents = self.get_facts_depending_on(subject, relation, obj)
            for dep in dependents:
                # Recursively retract dependent facts
                sub_result = self.retract_fact(
                    dep["subject"], dep["relation"], dep["object"],
                    cascade=True
                )
                if sub_result["retracted"]:
                    result["cascade_count"] += 1 + sub_result["cascade_count"]
                    result["cascaded_facts"].append({
                        "subject": dep["subject"],
                        "relation": dep["relation"],
                        "object": dep["object"]
                    })
                    result["cascaded_facts"].extend(sub_result["cascaded_facts"])

        # Fetch the fact before deleting so we can return its metadata
        for f in self._data["facts"]:
            if (f["subject"] == subject and
                    f["relation"] == relation and
                    f["object"] == obj):
                normalized = self._normalize_fact(dict(f))
                result["old_properties"] = normalized.get("properties", {})
                result["old_context"] = normalized.get("context", "general")
                result["old_object"] = normalized.get("object")
                break

        # Now delete the actual fact
        original_len = len(self._data["facts"])
        self._data["facts"] = [
            f for f in self._data["facts"]
            if not (f["subject"] == subject and
                   f["relation"] == relation and
                   f["object"] == obj)
        ]
        if len(self._data["facts"]) < original_len:
            self._save()
            result["retracted"] = True

        return result

    def get_constraints(self, subject: str, relation: str, obj: str) -> list:
        for f in self._data["facts"]:
            if (f["subject"] == subject and
                f["relation"] == relation and
                f["object"] == obj):
                f = self._normalize_fact(f)
                # Check new format first, then legacy
                conditions = f.get("properties", {}).get("conditions", [])
                if not conditions:
                    conditions = f.get("constraints", [])
                return conditions
        return []

    def add_constraint(self, subject: str, relation: str, obj: str, constraint: str):
        for f in self._data["facts"]:
            if (f["subject"] == subject and
                f["relation"] == relation and
                f["object"] == obj):
                f = self._normalize_fact(f)
                conditions = f.get("properties", {}).get("conditions", [])
                if constraint not in conditions:
                    if "properties" not in f:
                        f["properties"] = dict(DEFAULT_PROPERTIES)
                    if "conditions" not in f["properties"]:
                        f["properties"]["conditions"] = []
                    f["properties"]["conditions"].append(constraint)
                    self._save()
                return

    def get_confidence(self, subject: str, relation: str, obj: str) -> str:
        for f in self._data["facts"]:
            if (f["subject"] == subject and
                f["relation"] == relation and
                f["object"] == obj):
                f = self._normalize_fact(f)
                # Check new format first, then legacy
                conf = f.get("properties", {}).get("confidence")
                if conf is None:
                    conf = f.get("confidence", "medium")
                return conf
        return "medium"

    def update_confidence(self, subject: str, relation: str, obj: str, confidence: str):
        for f in self._data["facts"]:
            if (f["subject"] == subject and
                f["relation"] == relation and
                f["object"] == obj):
                f = self._normalize_fact(f)
                if "properties" not in f:
                    f["properties"] = dict(DEFAULT_PROPERTIES)
                f["properties"]["confidence"] = confidence
                self._save()
                return

    def get_all_knowledge(self) -> dict:
        knowledge = defaultdict(lambda: defaultdict(list))
        for f in self._data["facts"]:
            knowledge[f["subject"]][f["relation"]].append(f["object"])
        return {k: dict(v) for k, v in knowledge.items()}

    def get_subjects_with_relation(self, relation: str, obj: str) -> list:
        return [f["subject"] for f in self._data["facts"]
                if f["relation"] == relation and f["object"] == obj]

    def add_procedure(self, name: str, steps: list):
        self._data["procedures"][name] = steps
        self._save()

    def get_procedure(self, name: str) -> list:
        return self._data["procedures"].get(name, [])

    def get_all_procedures(self) -> dict:
        return self._data["procedures"]

    def add_inference(self, subject: str, relation: str, obj: str, depth: int):
        for inf in self._data["inferences"]:
            if (inf[0] == subject and inf[1] == relation and inf[2] == obj):
                return
        self._data["inferences"].append((subject, relation, obj, depth))
        self._save()

    def get_inferences(self) -> list:
        return self._data["inferences"]

    def clear_inferences(self):
        self._data["inferences"] = []
        self._save()

    def add_conflict(self, conflict: dict):
        self._data["conflicts"].append(conflict)
        self._save()

    def get_conflicts(self) -> list:
        return self._data["conflicts"]

    def clear_conflicts(self):
        self._data["conflicts"] = []
        self._save()

    def save_frames(self, frame_data: dict):
        """Persist frame data."""
        self._data["frames"] = frame_data
        self._save()

    def load_frames(self) -> dict:
        """Load frame data."""
        return self._data.get("frames", {})

    def forget_all(self):
        self._data = {
            "facts": [],
            "procedures": {},
            "inferences": [],
            "conflicts": [],
            "frames": {}
        }
        if os.path.exists(self.memory_file):
            os.remove(self.memory_file)

    def get_stats(self) -> dict:
        subjects = set(f["subject"] for f in self._data["facts"])
        objects = set(f["object"] for f in self._data["facts"])
        return {
            "nodes": len(subjects | objects),
            "facts": len(self._data["facts"]),
            "procedures": len(self._data["procedures"]),
            "inferences": len(self._data["inferences"]),
            "conflicts": len(self._data["conflicts"])
        }

    def close(self):
        pass
