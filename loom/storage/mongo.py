"""
MongoDB storage backend for Loom.
Provides efficient persistent storage for the knowledge graph.

Collections:
- facts: Stores knowledge quads (subject, relation, object, context) with properties
- procedures: Stores procedural sequences
- inferences: Stores cached inferences
- metadata: Stores system metadata (name, version, etc.)

Supports Quad + Properties schema:
- subject, relation, object, context (the quad)
- properties: {confidence, temporal, scope, conditions, source_type, ...}

Install pymongo: pip install pymongo
"""

from collections import defaultdict
from typing import Optional, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

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

# Try to import pymongo
PYMONGO_AVAILABLE = False
try:
    from pymongo import MongoClient, ASCENDING, DESCENDING
    from pymongo.errors import ConnectionFailure, DuplicateKeyError
    PYMONGO_AVAILABLE = True
except ImportError:
    logger.info("pymongo not installed, MongoDB storage unavailable")
    # Define placeholder classes for type checking
    MongoClient = None
    ASCENDING = 1
    DESCENDING = -1
    ConnectionFailure = Exception
    DuplicateKeyError = Exception


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
                 confidence: str = "high", constraints: list = None,
                 provenance: dict = None, context: str = None,
                 properties: dict = None) -> bool:
        """
        Add a fact to the knowledge graph with Quad + Properties schema.

        Args:
            subject: The subject of the fact
            relation: The relation type
            obj: The object of the fact
            confidence: Confidence level (legacy, moved to properties)
            constraints: Optional constraints (legacy, moved to properties.conditions)
            provenance: Provenance metadata (legacy, merged into properties)
            context: Context for the fact (general, domestic, scientific, etc.)
            properties: Full properties dict with temporal, scope, etc.

        Returns True if fact was added, False if it already exists.
        """
        ctx = context or DEFAULT_CONTEXT

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

        doc = {
            "instance": self.instance_name,
            "subject": subject,
            "relation": relation,
            "object": obj,
            "context": ctx,
            "properties": props
        }

        try:
            self.db.facts.insert_one(doc)
            return True
        except DuplicateKeyError:
            # Fact already exists — increment agreement and add this speaker
            speaker = props.get("speaker_id")
            update = {"$inc": {"properties.agreement_count": 1}}
            if speaker:
                update["$addToSet"] = {"properties.agreed_by": speaker}
            try:
                self.db.facts.update_one(
                    {"instance": self.instance_name, "subject": subject,
                     "relation": relation, "object": obj},
                    update
                )
            except Exception:
                pass
            return False

    def add_facts_bulk(self, docs: list) -> int:
        """
        Bulk-insert pre-built fact documents into MongoDB.
        Skips duplicates silently. Returns count of successfully inserted docs.
        """
        if not docs:
            return 0
        try:
            result = self.db.facts.insert_many(docs, ordered=False)
            return len(result.inserted_ids)
        except Exception as e:
            # BulkWriteError contains partial results — count successes
            if hasattr(e, 'details'):
                inserted = e.details.get('nInserted', 0)
                return inserted
            return 0

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
        """Get all objects for a subject-relation pair, optionally filtered by context."""
        query = {
            "instance": self.instance_name,
            "subject": subject,
            "relation": relation
        }
        if context:
            query["context"] = context

        cursor = self.db.facts.find(query, {"object": 1, "_id": 0})
        return [doc["object"] for doc in cursor]

    def get_facts_with_context(self, subject: str, relation: str) -> list:
        """Get facts with their context and properties."""
        cursor = self.db.facts.find({
            "instance": self.instance_name,
            "subject": subject,
            "relation": relation
        })

        results = []
        for doc in cursor:
            doc = self._normalize_fact(doc)
            results.append({
                "object": doc["object"],
                "context": doc.get("context", DEFAULT_CONTEXT),
                "properties": doc.get("properties", {})
            })
        return results

    def get_fact_with_metadata(self, subject: str, relation: str, obj: str,
                                context: str = None) -> Optional[dict]:
        """Get a specific fact with all its metadata."""
        query = {
            "instance": self.instance_name,
            "subject": subject,
            "relation": relation,
            "object": obj
        }
        if context:
            query["context"] = context

        doc = self.db.facts.find_one(query)
        if doc:
            return self._normalize_fact(doc)
        return None

    def get_facts_by_source_type(self, source_type: str) -> List[dict]:
        """Get all facts with a specific source type."""
        # Query both new and legacy formats
        cursor = self.db.facts.find({
            "instance": self.instance_name,
            "$or": [
                {"properties.source_type": source_type},
                {"provenance.source_type": source_type}
            ]
        })
        return [self._normalize_fact(doc) for doc in cursor]

    def get_facts_depending_on(self, subject: str, relation: str, obj: str) -> List[dict]:
        """
        Get all facts that depend on the given fact as a premise.
        Used for truth maintenance - when a fact is retracted,
        its dependents may need to be invalidated.
        """
        # Query both new and legacy formats
        cursor = self.db.facts.find({
            "instance": self.instance_name,
            "$or": [
                {"properties.premises": {
                    "$elemMatch": {
                        "subject": subject,
                        "relation": relation,
                        "object": obj
                    }
                }},
                {"provenance.premises": {
                    "$elemMatch": {
                        "subject": subject,
                        "relation": relation,
                        "object": obj
                    }
                }}
            ]
        })
        return [self._normalize_fact(doc) for doc in cursor]

    def get_inferred_facts(self) -> List[dict]:
        """Get all facts that were inferred (not directly stated by user)."""
        # Query both new and legacy formats
        cursor = self.db.facts.find({
            "instance": self.instance_name,
            "$or": [
                {"properties.source_type": {"$in": ["inference", "inheritance"]}},
                {"provenance.source_type": {"$in": ["inference", "inheritance"]}}
            ]
        })
        return [self._normalize_fact(doc) for doc in cursor]

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

    def remove_entity(self, entity: str) -> int:
        """
        Remove all facts where entity is the SUBJECT only.
        Does NOT remove facts where entity is the object (to preserve valid relations).
        Used for cleaning up junk neurons.

        Returns:
            Number of facts removed
        """
        # Only remove facts where entity is the subject
        # Keep facts where entity is the object (these are valid relations from other entities)
        result = self.db.facts.delete_many({
            "instance": self.instance_name,
            "subject": entity
        })

        return result.deleted_count

    def get_subjects_with_relation(self, relation: str, obj: str) -> list:
        """Find all subjects that have a relation to an object (reverse lookup)."""
        cursor = self.db.facts.find({
            "instance": self.instance_name,
            "relation": relation,
            "object": obj
        }, {"subject": 1, "_id": 0})

        return [doc["subject"] for doc in cursor]

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
        query = {
            "instance": self.instance_name,
            "subject": subject,
            "relation": relation,
            "object": obj
        }
        existing_doc = self.db.facts.find_one(query)
        if existing_doc:
            existing_doc = self._normalize_fact(existing_doc)
            result["old_properties"] = existing_doc.get("properties", {})
            result["old_context"] = existing_doc.get("context", DEFAULT_CONTEXT)
            result["old_object"] = existing_doc.get("object")

        # Now delete the actual fact
        delete_result = self.db.facts.delete_one(query)
        result["retracted"] = delete_result.deleted_count > 0

        return result

    def update_confidence(self, subject: str, relation: str, obj: str, confidence: str):
        """Update confidence level for a fact."""
        # Update both new and legacy formats for compatibility
        self.db.facts.update_one(
            {
                "instance": self.instance_name,
                "subject": subject,
                "relation": relation,
                "object": obj
            },
            {"$set": {
                "properties.confidence": confidence,
                "confidence": confidence  # Legacy field
            }}
        )

    def add_constraint(self, subject: str, relation: str, obj: str, constraint: str):
        """Add a constraint to a fact."""
        # Update both new and legacy formats for compatibility
        self.db.facts.update_one(
            {
                "instance": self.instance_name,
                "subject": subject,
                "relation": relation,
                "object": obj
            },
            {"$addToSet": {
                "properties.conditions": constraint,
                "constraints": constraint  # Legacy field
            }}
        )

    def get_constraints(self, subject: str, relation: str, obj: str) -> list:
        """Get constraints for a fact."""
        doc = self.db.facts.find_one({
            "instance": self.instance_name,
            "subject": subject,
            "relation": relation,
            "object": obj
        }, {"constraints": 1, "properties.conditions": 1})

        if not doc:
            return []
        # Check new format first, then legacy
        conditions = doc.get("properties", {}).get("conditions", [])
        if conditions:
            return conditions
        return doc.get("constraints", [])

    def get_confidence(self, subject: str, relation: str, obj: str) -> str:
        """Get confidence level for a fact."""
        doc = self.db.facts.find_one({
            "instance": self.instance_name,
            "subject": subject,
            "relation": relation,
            "object": obj
        }, {"confidence": 1, "properties.confidence": 1})

        if not doc:
            return "medium"
        # Check new format first, then legacy
        conf = doc.get("properties", {}).get("confidence")
        if conf:
            return conf
        return doc.get("confidence", "medium")

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

    def delete_user_facts(self, username: str) -> int:
        """Remove all facts created by a specific user. Returns count deleted."""
        result = self.db.facts.delete_many({
            "instance": self.instance_name,
            "properties.speaker_id": username
        })
        return result.deleted_count

    def forget_all(self):
        """Clear ALL data for this instance — every collection."""
        inst = {"instance": self.instance_name}
        self.db.facts.delete_many(inst)
        self.db.procedures.delete_many(inst)
        self.db.inferences.delete_many(inst)
        self.db.conflicts.delete_many(inst)
        self.db.style_patterns.delete_many(inst)
        self.db.feedback.delete_many(inst)
        # Clear any other collections that might exist
        for coll_name in self.db.list_collection_names():
            if coll_name not in ('system.indexes',):
                try:
                    self.db[coll_name].delete_many(inst)
                except Exception:
                    pass

    def get_stats(self) -> dict:
        """Get storage statistics."""
        # Count inferences from facts collection (source_type = inference/inheritance/rule)
        inferred_count = self.db.facts.count_documents({
            "instance": self.instance_name,
            "properties.source_type": {"$in": ["inference", "inheritance", "rule", "discovery"]}
        })
        return {
            "nodes": self.get_node_count(),
            "facts": self.get_fact_count(),
            "procedures": self.db.procedures.count_documents({"instance": self.instance_name}),
            "inferences": inferred_count,
            "conflicts": self.db.conflicts.count_documents({"instance": self.instance_name})
        }

    def close(self):
        """Close MongoDB connection."""
        if self.client:
            self.client.close()
