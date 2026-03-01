"""
JSON Fallback storage backend for Loom.
Used when MongoDB is not available.
"""

from collections import defaultdict
import json
import os


class JSONFallbackStorage:
    """
    Fallback storage that mimics MongoStorage interface but uses JSON files.
    Used when MongoDB is not available.
    """

    def __init__(self, memory_file: str = "loom_memory.json"):
        self.memory_file = memory_file
        self._data = self._load()

    def _load(self) -> dict:
        """Load data from JSON file."""
        default_data = {
            "facts": [],
            "procedures": {},
            "inferences": [],
            "conflicts": []
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
                 confidence: str = "high", constraints: list = None) -> bool:
        for fact in self._data["facts"]:
            if (fact["subject"] == subject and
                fact["relation"] == relation and
                fact["object"] == obj):
                return False

        self._data["facts"].append({
            "subject": subject,
            "relation": relation,
            "object": obj,
            "confidence": confidence,
            "constraints": constraints or []
        })
        self._save()
        return True

    def get_facts(self, subject: str, relation: str) -> list:
        return [f["object"] for f in self._data["facts"]
                if f["subject"] == subject and f["relation"] == relation]

    def get_all_facts_for_subject(self, subject: str) -> dict:
        result = defaultdict(list)
        for f in self._data["facts"]:
            if f["subject"] == subject:
                result[f["relation"]].append(f["object"])
        return dict(result)

    def retract_fact(self, subject: str, relation: str, obj: str) -> bool:
        original_len = len(self._data["facts"])
        self._data["facts"] = [
            f for f in self._data["facts"]
            if not (f["subject"] == subject and
                   f["relation"] == relation and
                   f["object"] == obj)
        ]
        if len(self._data["facts"]) < original_len:
            self._save()
            return True
        return False

    def get_constraints(self, subject: str, relation: str, obj: str) -> list:
        for f in self._data["facts"]:
            if (f["subject"] == subject and
                f["relation"] == relation and
                f["object"] == obj):
                return f.get("constraints", [])
        return []

    def add_constraint(self, subject: str, relation: str, obj: str, constraint: str):
        for f in self._data["facts"]:
            if (f["subject"] == subject and
                f["relation"] == relation and
                f["object"] == obj):
                if "constraints" not in f:
                    f["constraints"] = []
                if constraint not in f["constraints"]:
                    f["constraints"].append(constraint)
                    self._save()
                return

    def get_confidence(self, subject: str, relation: str, obj: str) -> str:
        for f in self._data["facts"]:
            if (f["subject"] == subject and
                f["relation"] == relation and
                f["object"] == obj):
                return f.get("confidence", "medium")
        return "medium"

    def update_confidence(self, subject: str, relation: str, obj: str, confidence: str):
        for f in self._data["facts"]:
            if (f["subject"] == subject and
                f["relation"] == relation and
                f["object"] == obj):
                f["confidence"] = confidence
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

    def forget_all(self):
        self._data = {
            "facts": [],
            "procedures": {},
            "inferences": [],
            "conflicts": []
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
