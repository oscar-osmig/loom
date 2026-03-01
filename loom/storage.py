"""
MongoDB storage backend for Loom.
Provides efficient persistent storage for the knowledge graph.

Collections:
- facts: Stores all knowledge triples (subject, relation, object)
- procedures: Stores procedural sequences
- inferences: Stores cached inferences
- metadata: Stores system metadata (name, version, etc.)

Install pymongo: pip install pymongo
"""

from collections import defaultdict
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Try to import pymongo
PYMONGO_AVAILABLE = False
try:
    from pymongo import MongoClient, ASCENDING, DESCENDING
    from pymongo.errors import ConnectionFailure, DuplicateKeyError
    PYMONGO_AVAILABLE = True
except ImportError:
    logger.info("pymongo not installed, MongoDB storage unavailable")


class MongoStorage:
    """
    MongoDB storage backend for Loom knowledge graph.
    Replaces JSON file storage with efficient indexed queries.
    """

    def __init__(self,
                 connection_string: str = "mongodb://localhost:27017",
                 database_name: str = "loom",
                 instance_name: str = "default"):
        """
        Initialize MongoDB connection.

        Args:
            connection_string: MongoDB connection URI
            database_name: Name of the database to use
            instance_name: Name of this Loom instance (allows multiple instances)
        """
        if not PYMONGO_AVAILABLE:
            raise ImportError("pymongo is required for MongoDB storage. Install with: pip install pymongo")

        self.connection_string = connection_string
        self.database_name = database_name
        self.instance_name = instance_name
        self.client = None
        self.db = None

        self._connect()
        self._ensure_indexes()

    def _connect(self):
        """Establish connection to MongoDB."""
        try:
            self.client = MongoClient(self.connection_string, serverSelectionTimeoutMS=5000)
            # Test connection
            self.client.admin.command('ping')
            self.db = self.client[self.database_name]
            logger.info(f"Connected to MongoDB: {self.database_name}")
        except ConnectionFailure as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise

    def _ensure_indexes(self):
        """Create indexes for efficient querying."""
        # Facts collection indexes
        facts = self.db.facts
        facts.create_index([
            ("instance", ASCENDING),
            ("subject", ASCENDING),
            ("relation", ASCENDING)
        ], name="idx_subject_relation")

        facts.create_index([
            ("instance", ASCENDING),
            ("relation", ASCENDING),
            ("object", ASCENDING)
        ], name="idx_relation_object")

        facts.create_index([
            ("instance", ASCENDING),
            ("subject", ASCENDING),
            ("relation", ASCENDING),
            ("object", ASCENDING)
        ], unique=True, name="idx_unique_fact")

        facts.create_index([
            ("instance", ASCENDING),
            ("object", ASCENDING)
        ], name="idx_object")

        # Procedures collection index
        self.db.procedures.create_index([
            ("instance", ASCENDING),
            ("name", ASCENDING)
        ], unique=True, name="idx_procedure_name")

        # Inferences collection indexes
        inferences = self.db.inferences
        inferences.create_index([
            ("instance", ASCENDING),
            ("subject", ASCENDING),
            ("relation", ASCENDING)
        ], name="idx_inference_subject")

    # ==================== FACTS ====================

    def add_fact(self, subject: str, relation: str, obj: str,
                 confidence: str = "high", constraints: list = None) -> bool:
        """
        Add a fact to the knowledge graph.

        Returns True if fact was added, False if it already exists.
        """
        doc = {
            "instance": self.instance_name,
            "subject": subject,
            "relation": relation,
            "object": obj,
            "confidence": confidence,
            "constraints": constraints or []
        }

        try:
            self.db.facts.insert_one(doc)
            return True
        except DuplicateKeyError:
            return False

    def get_facts(self, subject: str, relation: str) -> list:
        """Get all objects for a subject-relation pair."""
        cursor = self.db.facts.find({
            "instance": self.instance_name,
            "subject": subject,
            "relation": relation
        }, {"object": 1, "_id": 0})

        return [doc["object"] for doc in cursor]

    def get_fact_with_metadata(self, subject: str, relation: str, obj: str) -> Optional[dict]:
        """Get a specific fact with all its metadata."""
        return self.db.facts.find_one({
            "instance": self.instance_name,
            "subject": subject,
            "relation": relation,
            "object": obj
        })

    def get_all_facts_for_subject(self, subject: str) -> dict:
        """Get all facts for a subject, grouped by relation."""
        cursor = self.db.facts.find({
            "instance": self.instance_name,
            "subject": subject
        })

        result = defaultdict(list)
        for doc in cursor:
            result[doc["relation"]].append(doc["object"])

        return dict(result)

    def get_subjects_with_relation(self, relation: str, obj: str) -> list:
        """Find all subjects that have a relation to an object (reverse lookup)."""
        cursor = self.db.facts.find({
            "instance": self.instance_name,
            "relation": relation,
            "object": obj
        }, {"subject": 1, "_id": 0})

        return [doc["subject"] for doc in cursor]

    def retract_fact(self, subject: str, relation: str, obj: str) -> bool:
        """Remove a fact from the knowledge graph."""
        result = self.db.facts.delete_one({
            "instance": self.instance_name,
            "subject": subject,
            "relation": relation,
            "object": obj
        })
        return result.deleted_count > 0

    def update_confidence(self, subject: str, relation: str, obj: str, confidence: str):
        """Update confidence level for a fact."""
        self.db.facts.update_one(
            {
                "instance": self.instance_name,
                "subject": subject,
                "relation": relation,
                "object": obj
            },
            {"$set": {"confidence": confidence}}
        )

    def add_constraint(self, subject: str, relation: str, obj: str, constraint: str):
        """Add a constraint to a fact."""
        self.db.facts.update_one(
            {
                "instance": self.instance_name,
                "subject": subject,
                "relation": relation,
                "object": obj
            },
            {"$addToSet": {"constraints": constraint}}
        )

    def get_constraints(self, subject: str, relation: str, obj: str) -> list:
        """Get constraints for a fact."""
        doc = self.db.facts.find_one({
            "instance": self.instance_name,
            "subject": subject,
            "relation": relation,
            "object": obj
        }, {"constraints": 1})

        return doc.get("constraints", []) if doc else []

    def get_confidence(self, subject: str, relation: str, obj: str) -> str:
        """Get confidence level for a fact."""
        doc = self.db.facts.find_one({
            "instance": self.instance_name,
            "subject": subject,
            "relation": relation,
            "object": obj
        }, {"confidence": 1})

        return doc.get("confidence", "medium") if doc else "medium"

    # ==================== KNOWLEDGE GRAPH ====================

    def get_all_knowledge(self) -> dict:
        """
        Get entire knowledge graph as nested dict.
        Format: {subject: {relation: [objects]}}
        """
        cursor = self.db.facts.find({"instance": self.instance_name})

        knowledge = defaultdict(lambda: defaultdict(list))
        for doc in cursor:
            knowledge[doc["subject"]][doc["relation"]].append(doc["object"])

        # Convert to regular dict
        return {k: dict(v) for k, v in knowledge.items()}

    def get_all_nodes(self) -> list:
        """Get all unique nodes (subjects and objects)."""
        subjects = self.db.facts.distinct("subject", {"instance": self.instance_name})
        objects = self.db.facts.distinct("object", {"instance": self.instance_name})
        return list(set(subjects) | set(objects))

    def get_node_count(self) -> int:
        """Get count of unique nodes."""
        return len(self.get_all_nodes())

    def get_fact_count(self) -> int:
        """Get count of facts."""
        return self.db.facts.count_documents({"instance": self.instance_name})

    # ==================== PROCEDURES ====================

    def add_procedure(self, name: str, steps: list):
        """Add or update a procedure."""
        self.db.procedures.update_one(
            {"instance": self.instance_name, "name": name},
            {"$set": {"steps": steps}},
            upsert=True
        )

    def get_procedure(self, name: str) -> list:
        """Get steps for a procedure."""
        doc = self.db.procedures.find_one({
            "instance": self.instance_name,
            "name": name
        })
        return doc.get("steps", []) if doc else []

    def get_all_procedures(self) -> dict:
        """Get all procedures."""
        cursor = self.db.procedures.find({"instance": self.instance_name})
        return {doc["name"]: doc["steps"] for doc in cursor}

    # ==================== INFERENCES ====================

    def add_inference(self, subject: str, relation: str, obj: str, depth: int):
        """Cache an inferred fact."""
        self.db.inferences.update_one(
            {
                "instance": self.instance_name,
                "subject": subject,
                "relation": relation,
                "object": obj
            },
            {"$set": {"depth": depth}},
            upsert=True
        )

    def get_inferences(self) -> list:
        """Get all cached inferences."""
        cursor = self.db.inferences.find({"instance": self.instance_name})
        return [(doc["subject"], doc["relation"], doc["object"], doc["depth"])
                for doc in cursor]

    def clear_inferences(self):
        """Clear all cached inferences."""
        self.db.inferences.delete_many({"instance": self.instance_name})

    # ==================== CONFLICTS ====================

    def add_conflict(self, conflict: dict):
        """Record a detected conflict."""
        conflict["instance"] = self.instance_name
        self.db.conflicts.insert_one(conflict)

    def get_conflicts(self) -> list:
        """Get all detected conflicts."""
        cursor = self.db.conflicts.find(
            {"instance": self.instance_name},
            {"_id": 0, "instance": 0}
        )
        return list(cursor)

    def clear_conflicts(self):
        """Clear all conflicts."""
        self.db.conflicts.delete_many({"instance": self.instance_name})

    # ==================== ADMIN ====================

    def forget_all(self):
        """Clear all data for this instance."""
        self.db.facts.delete_many({"instance": self.instance_name})
        self.db.procedures.delete_many({"instance": self.instance_name})
        self.db.inferences.delete_many({"instance": self.instance_name})
        self.db.conflicts.delete_many({"instance": self.instance_name})

    def get_stats(self) -> dict:
        """Get storage statistics."""
        return {
            "nodes": self.get_node_count(),
            "facts": self.get_fact_count(),
            "procedures": self.db.procedures.count_documents({"instance": self.instance_name}),
            "inferences": self.db.inferences.count_documents({"instance": self.instance_name}),
            "conflicts": self.db.conflicts.count_documents({"instance": self.instance_name})
        }

    def close(self):
        """Close MongoDB connection."""
        if self.client:
            self.client.close()


class JSONFallbackStorage:
    """
    Fallback storage that mimics MongoStorage interface but uses JSON files.
    Used when MongoDB is not available.
    """

    def __init__(self, memory_file: str = "loom_memory.json"):
        import json
        import os
        self.memory_file = memory_file
        self.json = json
        self.os = os
        self._data = self._load()

    def _load(self) -> dict:
        """Load data from JSON file."""
        default_data = {
            "facts": [],
            "procedures": {},
            "inferences": [],
            "conflicts": []
        }

        if self.os.path.exists(self.memory_file):
            try:
                with open(self.memory_file, 'r', encoding='utf-8') as f:
                    data = self.json.load(f)

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
            self.json.dump(self._data, f, indent=2, ensure_ascii=False)

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
        if self.os.path.exists(self.memory_file):
            self.os.remove(self.memory_file)

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


def get_storage(use_mongo: bool = True, **kwargs):
    """
    Factory function to get appropriate storage backend.
    Falls back to JSON if MongoDB is not available.
    """
    memory_file = kwargs.pop("memory_file", "loom_memory.json")

    if use_mongo and PYMONGO_AVAILABLE:
        try:
            return MongoStorage(**kwargs)
        except Exception as e:
            logger.warning(f"MongoDB not available, falling back to JSON: {e}")
            return JSONFallbackStorage(memory_file)
    else:
        if use_mongo and not PYMONGO_AVAILABLE:
            logger.info("pymongo not installed, using JSON storage. Install with: pip install pymongo")
        return JSONFallbackStorage(memory_file)
