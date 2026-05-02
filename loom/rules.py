"""
Explicit Rule Neurons for Loom.
Stores and manages reusable logic rules with forward chaining support.

A rule is:
    premises[] → conclusion

Example:
    ["X is mammal", "X has fur"] → "X is warm-blooded"

Rules are learned from:
1. Repeated conversational patterns
2. Explicit teaching ("if X then Y")
3. Inference patterns that get confirmed
"""

import time
import logging
import json
import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class RuleStatus(Enum):
    """Status of a rule in the system."""
    CANDIDATE = "candidate"      # Learned but not confirmed
    ACTIVE = "active"            # Confirmed and active
    SUSPENDED = "suspended"      # Temporarily disabled
    REJECTED = "rejected"        # User rejected this rule


@dataclass
class RulePremise:
    """A single premise in a rule."""
    subject_var: str      # Variable like "X" or concrete value
    relation: str         # The relation type
    object_var: str       # Variable like "Y" or concrete value

    def to_dict(self) -> dict:
        return {
            "subject_var": self.subject_var,
            "relation": self.relation,
            "object_var": self.object_var
        }

    @classmethod
    def from_dict(cls, d: dict) -> "RulePremise":
        return cls(
            subject_var=d["subject_var"],
            relation=d["relation"],
            object_var=d["object_var"]
        )

    def __str__(self) -> str:
        return f"{self.subject_var} {self.relation} {self.object_var}"


@dataclass
class RuleConclusion:
    """The conclusion of a rule."""
    subject_var: str
    relation: str
    object_var: str

    def to_dict(self) -> dict:
        return {
            "subject_var": self.subject_var,
            "relation": self.relation,
            "object_var": self.object_var
        }

    @classmethod
    def from_dict(cls, d: dict) -> "RuleConclusion":
        return cls(
            subject_var=d["subject_var"],
            relation=d["relation"],
            object_var=d["object_var"]
        )

    def __str__(self) -> str:
        return f"{self.subject_var} {self.relation} {self.object_var}"


@dataclass
class Rule:
    """
    An explicit rule neuron.

    Represents: IF premises THEN conclusion

    Example:
        IF X is mammal AND X has live_birth
        THEN X is placental_mammal
    """
    rule_id: str
    premises: List[RulePremise]
    conclusion: RuleConclusion
    support_count: int = 0           # How many times this pattern was seen
    confidence: float = 0.5          # Confidence in this rule
    status: RuleStatus = RuleStatus.CANDIDATE
    created_at: float = field(default_factory=time.time)
    last_fired: Optional[float] = None
    fire_count: int = 0              # How many times rule has fired
    provenance: List[dict] = field(default_factory=list)  # Where this rule came from
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "premises": [p.to_dict() for p in self.premises],
            "conclusion": self.conclusion.to_dict(),
            "support_count": self.support_count,
            "confidence": self.confidence,
            "status": self.status.value,
            "created_at": self.created_at,
            "last_fired": self.last_fired,
            "fire_count": self.fire_count,
            "provenance": self.provenance,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Rule":
        return cls(
            rule_id=d["rule_id"],
            premises=[RulePremise.from_dict(p) for p in d["premises"]],
            conclusion=RuleConclusion.from_dict(d["conclusion"]),
            support_count=d.get("support_count", 0),
            confidence=d.get("confidence", 0.5),
            status=RuleStatus(d.get("status", "candidate")),
            created_at=d.get("created_at", time.time()),
            last_fired=d.get("last_fired"),
            fire_count=d.get("fire_count", 0),
            provenance=d.get("provenance", []),
            metadata=d.get("metadata", {})
        )

    def matches_premises(self, knowledge: dict, bindings: dict = None) -> List[dict]:
        """
        Check if all premises match with the given knowledge.

        Returns list of valid variable bindings, or empty list if no match.
        """
        if bindings is None:
            bindings = {}

        return self._match_recursive(0, knowledge, bindings)

    def _match_recursive(self, premise_idx: int, knowledge: dict,
                         bindings: dict) -> List[dict]:
        """Recursively match premises and collect all valid bindings."""
        if premise_idx >= len(self.premises):
            # All premises matched
            return [bindings.copy()]

        premise = self.premises[premise_idx]
        all_bindings = []

        # Get the subject to check
        if premise.subject_var.startswith("?"):
            # Variable - need to iterate or use existing binding
            if premise.subject_var in bindings:
                subjects = [bindings[premise.subject_var]]
            else:
                # Try all entities in knowledge
                subjects = list(knowledge.keys())
        else:
            subjects = [premise.subject_var]

        for subject in subjects:
            if subject not in knowledge:
                continue

            relations = knowledge[subject]
            if premise.relation not in relations:
                continue

            objects = relations[premise.relation]

            for obj in objects:
                # Check object match
                if premise.object_var.startswith("?"):
                    if premise.object_var in bindings:
                        if bindings[premise.object_var] != obj:
                            continue
                    # Variable matches
                else:
                    # Allow singular/plural matching
                    if not self._fuzzy_match(premise.object_var, obj):
                        continue

                # Create new bindings
                new_bindings = bindings.copy()
                if premise.subject_var.startswith("?"):
                    new_bindings[premise.subject_var] = subject
                if premise.object_var.startswith("?"):
                    new_bindings[premise.object_var] = obj

                # Recurse to next premise
                results = self._match_recursive(premise_idx + 1, knowledge, new_bindings)
                all_bindings.extend(results)

        return all_bindings

    def _fuzzy_match(self, pattern: str, value: str) -> bool:
        """
        Check if pattern matches value, allowing singular/plural variations.
        """
        if pattern == value:
            return True

        # Try singular/plural
        pattern_lower = pattern.lower()
        value_lower = value.lower()

        # bird == birds, mammal == mammals
        if pattern_lower + 's' == value_lower:
            return True
        if pattern_lower == value_lower + 's':
            return True

        # Handle -es plurals (fish/fishes, etc.)
        if pattern_lower + 'es' == value_lower:
            return True
        if pattern_lower == value_lower + 'es':
            return True

        # Handle -ies plurals (fly/flies)
        if pattern_lower.endswith('y') and pattern_lower[:-1] + 'ies' == value_lower:
            return True
        if value_lower.endswith('y') and value_lower[:-1] + 'ies' == pattern_lower:
            return True

        return False

    def apply_conclusion(self, bindings: dict) -> Tuple[str, str, str]:
        """
        Apply bindings to conclusion to get concrete fact.

        Returns: (subject, relation, object)
        """
        subject = bindings.get(self.conclusion.subject_var, self.conclusion.subject_var)
        obj = bindings.get(self.conclusion.object_var, self.conclusion.object_var)

        return (subject, self.conclusion.relation, obj)

    def __str__(self) -> str:
        premises_str = " AND ".join(str(p) for p in self.premises)
        return f"IF {premises_str} THEN {self.conclusion}"


class RuleMemory:
    """
    Storage and management for rule neurons.

    Handles:
    - Rule storage (MongoDB or JSON)
    - Rule retrieval by premises/conclusions
    - Rule learning from patterns
    - Forward chaining execution
    """

    def __init__(self, loom, use_mongo: bool = False, storage_path: str = None):
        """
        Initialize rule memory.

        Args:
            loom: The Loom instance
            use_mongo: Whether to use MongoDB
            storage_path: Path for JSON storage
        """
        self.loom = loom
        self.use_mongo = use_mongo
        self.storage_path = storage_path or "loom_memory/loom_rules.json"

        # In-memory rule cache
        self._rules: Dict[str, Rule] = {}
        self._rule_counter = 0

        # Pattern tracking for rule learning
        self._pattern_counts: Dict[str, int] = {}

        # MongoDB collection
        self._mongo_collection = None
        if use_mongo:
            self._init_mongo()
        else:
            self._load_from_json()

    def _init_mongo(self):
        """Initialize MongoDB collection for rules."""
        try:
            if self.loom and hasattr(self.loom, 'storage') and self.loom.storage and self.loom.storage.db is not None:
                self._mongo_collection = self.loom.storage.db['rules']
            else:
                import os
                from pymongo import MongoClient
                uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
                client = MongoClient(uri, serverSelectionTimeoutMS=5000)
                client.admin.command('ping')
                db = client['loom']
                self._mongo_collection = db['rules']
            self._load_from_mongo()
            logger.info("Connected to MongoDB for rule storage")
        except Exception as e:
            logger.warning(f"Could not connect to MongoDB: {e}")
            self.use_mongo = False
            self._load_from_json()

    def _load_from_mongo(self):
        """Load rules from MongoDB."""
        if self._mongo_collection is None:
            return

        for doc in self._mongo_collection.find():
            rule = Rule.from_dict(doc)
            self._rules[rule.rule_id] = rule

        logger.info(f"Loaded {len(self._rules)} rules from MongoDB")

    def _load_from_json(self):
        """Load rules from JSON file."""
        import os
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, 'r') as f:
                    data = json.load(f)
                    for rule_data in data.get("rules", []):
                        rule = Rule.from_dict(rule_data)
                        self._rules[rule.rule_id] = rule
                    self._rule_counter = data.get("counter", 0)
                logger.info(f"Loaded {len(self._rules)} rules from {self.storage_path}")
            except Exception as e:
                logger.warning(f"Could not load rules: {e}")

    def _save_to_json(self):
        """Save rules to JSON file."""
        if self.use_mongo:
            return

        data = {
            "rules": [r.to_dict() for r in self._rules.values()],
            "counter": self._rule_counter
        }

        with open(self.storage_path, 'w') as f:
            json.dump(data, f, indent=2)

    def add_rule(self, rule: Rule) -> str:
        """
        Add a rule to memory.

        Returns the rule ID.
        """
        if not rule.rule_id:
            self._rule_counter += 1
            rule.rule_id = f"rule_{self._rule_counter}_{int(time.time())}"

        self._rules[rule.rule_id] = rule

        if self.use_mongo and self._mongo_collection:
            self._mongo_collection.update_one(
                {"rule_id": rule.rule_id},
                {"$set": rule.to_dict()},
                upsert=True
            )
        else:
            self._save_to_json()

        logger.info(f"Added rule: {rule}")
        return rule.rule_id

    def get_rule(self, rule_id: str) -> Optional[Rule]:
        """Get a rule by ID."""
        return self._rules.get(rule_id)

    def get_all_rules(self, status: RuleStatus = None) -> List[Rule]:
        """Get all rules, optionally filtered by status."""
        if status is None:
            return list(self._rules.values())
        return [r for r in self._rules.values() if r.status == status]

    def get_active_rules(self) -> List[Rule]:
        """Get all active rules."""
        return self.get_all_rules(RuleStatus.ACTIVE)

    def get_candidate_rules(self) -> List[Rule]:
        """Get all candidate rules awaiting confirmation."""
        return self.get_all_rules(RuleStatus.CANDIDATE)

    def update_rule_status(self, rule_id: str, status: RuleStatus):
        """Update a rule's status."""
        if rule_id in self._rules:
            self._rules[rule_id].status = status

            if self.use_mongo and self._mongo_collection:
                self._mongo_collection.update_one(
                    {"rule_id": rule_id},
                    {"$set": {"status": status.value}}
                )
            else:
                self._save_to_json()

    def confirm_rule(self, rule_id: str):
        """Confirm a candidate rule, making it active."""
        self.update_rule_status(rule_id, RuleStatus.ACTIVE)
        logger.info(f"Confirmed rule: {rule_id}")

    def reject_rule(self, rule_id: str):
        """Reject a candidate rule."""
        self.update_rule_status(rule_id, RuleStatus.REJECTED)
        logger.info(f"Rejected rule: {rule_id}")

    def increment_support(self, rule_id: str):
        """Increment support count for a rule."""
        if rule_id in self._rules:
            self._rules[rule_id].support_count += 1

            # Auto-promote to active if enough support
            rule = self._rules[rule_id]
            if rule.status == RuleStatus.CANDIDATE and rule.support_count >= 3:
                rule.confidence = min(0.9, rule.confidence + 0.1)

            if self.use_mongo and self._mongo_collection:
                self._mongo_collection.update_one(
                    {"rule_id": rule_id},
                    {"$set": {
                        "support_count": rule.support_count,
                        "confidence": rule.confidence
                    }}
                )
            else:
                self._save_to_json()

    def find_matching_rules(self, knowledge: dict) -> List[Tuple[Rule, List[dict]]]:
        """
        Find all rules whose premises match the current knowledge.

        Returns list of (rule, bindings_list) tuples.
        """
        matches = []

        for rule in self.get_active_rules():
            bindings_list = rule.matches_premises(knowledge)
            if bindings_list:
                matches.append((rule, bindings_list))

        return matches

    def create_rule_from_pattern(self, premises: List[Tuple[str, str, str]],
                                  conclusion: Tuple[str, str, str],
                                  provenance: dict = None) -> Rule:
        """
        Create a rule from observed premises and conclusion.

        Generalizes concrete values to variables where appropriate.
        """
        # Find common subjects/objects to generalize
        subjects = set()
        objects = set()

        for subj, rel, obj in premises:
            subjects.add(subj)
            objects.add(obj)

        subj_c, rel_c, obj_c = conclusion
        subjects.add(subj_c)
        objects.add(obj_c)

        # Create variable mappings for repeated entities
        var_map = {}
        var_counter = 0

        def get_var(entity: str) -> str:
            nonlocal var_counter
            if entity not in var_map:
                # Only variablize if entity appears multiple times
                count = sum(1 for s, r, o in premises + [conclusion]
                           if s == entity or o == entity)
                if count > 1:
                    var_counter += 1
                    var_map[entity] = f"?X{var_counter}"
                else:
                    var_map[entity] = entity
            return var_map[entity]

        # Create premises
        rule_premises = []
        for subj, rel, obj in premises:
            rule_premises.append(RulePremise(
                subject_var=get_var(subj),
                relation=rel,
                object_var=get_var(obj)
            ))

        # Create conclusion
        rule_conclusion = RuleConclusion(
            subject_var=get_var(subj_c),
            relation=rel_c,
            object_var=get_var(obj_c)
        )

        # Create rule
        self._rule_counter += 1
        rule = Rule(
            rule_id=f"rule_{self._rule_counter}_{int(time.time())}",
            premises=rule_premises,
            conclusion=rule_conclusion,
            support_count=1,
            confidence=0.5,
            status=RuleStatus.CANDIDATE,
            provenance=[provenance] if provenance else []
        )

        return rule

    def learn_from_if_then(self, text: str) -> Optional[Rule]:
        """
        Learn a rule from explicit if-then statement.

        Example: "if X is a mammal then X is warm-blooded"
        """
        # Pattern: if <premises> then <conclusion>
        match = re.match(
            r"if\s+(.+?)\s+then\s+(.+)",
            text.lower().strip(),
            re.IGNORECASE
        )

        if not match:
            return None

        premise_text = match.group(1).strip()
        conclusion_text = match.group(2).strip()

        # Parse premises (split by "and")
        premise_parts = re.split(r'\s+and\s+', premise_text)
        premises = []

        for part in premise_parts:
            parsed = self._parse_simple_statement(part)
            if parsed:
                premises.append(RulePremise(
                    subject_var=parsed[0],
                    relation=parsed[1],
                    object_var=parsed[2]
                ))

        if not premises:
            return None

        # Parse conclusion
        conclusion_parsed = self._parse_simple_statement(conclusion_text)
        if not conclusion_parsed:
            return None

        conclusion = RuleConclusion(
            subject_var=conclusion_parsed[0],
            relation=conclusion_parsed[1],
            object_var=conclusion_parsed[2]
        )

        # Create and add rule
        self._rule_counter += 1
        rule = Rule(
            rule_id=f"rule_{self._rule_counter}_{int(time.time())}",
            premises=premises,
            conclusion=conclusion,
            support_count=1,
            confidence=0.7,  # Higher confidence for explicit rules
            status=RuleStatus.CANDIDATE,
            provenance=[{"source": "explicit", "text": text}]
        )

        self.add_rule(rule)
        return rule

    def _parse_simple_statement(self, text: str) -> Optional[Tuple[str, str, str]]:
        """
        Parse a simple statement into (subject, relation, object).

        Handles:
        - "X is Y" / "X is a Y"
        - "X has Y"
        - "X can Y"
        """
        text = text.strip()

        # Patterns with two capture groups: subject and object
        patterns = [
            (r'^(\w+)\s+is\s+(?:a\s+|an\s+)?(.+)$', 'is'),
            (r'^(\w+)\s+are\s+(.+)$', 'is'),
            (r'^(\w+)\s+has\s+(.+)$', 'has'),
            (r'^(\w+)\s+have\s+(.+)$', 'has'),
            (r'^(\w+)\s+can\s+(.+)$', 'can'),
            (r'^(\w+)\s+needs?\s+(.+)$', 'needs'),
            (r'^(\w+)\s+eats?\s+(.+)$', 'eats'),
            (r'^(\w+)\s+lives?\s+in\s+(.+)$', 'lives_in'),
            (r'^(\w+)\s+live\s+in\s+(.+)$', 'lives_in'),
            (r'^(\w+)\s+causes?\s+(.+)$', 'causes'),
            (r'^(\w+)\s+cause\s+(.+)$', 'causes'),
            (r'^(\w+)\s+produces?\s+(.+)$', 'produces'),
            (r'^(\w+)\s+contains?\s+(.+)$', 'contains'),
            (r'^(\w+)\s+requires?\s+(.+)$', 'requires'),
        ]

        for pattern, rel in patterns:
            match = re.match(pattern, text, re.IGNORECASE)
            if match:
                subj = match.group(1).strip()
                obj = match.group(2).strip()

                # Convert single letters (X, Y, x, y) to variables
                if len(subj) == 1 and subj.isalpha():
                    subj = f"?{subj.upper()}"
                if len(obj) == 1 and obj.isalpha():
                    obj = f"?{obj.upper()}"

                return (subj, rel, obj)

        return None

    def get_stats(self) -> dict:
        """Get rule memory statistics."""
        return {
            "total_rules": len(self._rules),
            "active_rules": len(self.get_active_rules()),
            "candidate_rules": len(self.get_candidate_rules()),
            "rejected_rules": len(self.get_all_rules(RuleStatus.REJECTED)),
            "suspended_rules": len(self.get_all_rules(RuleStatus.SUSPENDED))
        }


class RuleEngine:
    """
    Forward chaining rule engine.

    Fires matching rules to derive new facts.
    """

    def __init__(self, loom, rule_memory: RuleMemory):
        """
        Initialize the rule engine.

        Args:
            loom: The Loom instance
            rule_memory: The RuleMemory instance
        """
        self.loom = loom
        self.rule_memory = rule_memory
        self._fired_this_cycle: set = set()

    def run_forward_chain(self, max_iterations: int = 10) -> List[dict]:
        """
        Run forward chaining until no new facts are derived.

        Returns list of derived facts.
        """
        derived_facts = []
        self._fired_this_cycle = set()

        for iteration in range(max_iterations):
            new_facts = self._forward_chain_step()

            if not new_facts:
                break

            derived_facts.extend(new_facts)
            logger.info(f"Forward chain iteration {iteration + 1}: {len(new_facts)} new facts")

        return derived_facts

    def _forward_chain_step(self) -> List[dict]:
        """Execute one step of forward chaining."""
        new_facts = []

        # Get current knowledge
        knowledge = self.loom.knowledge

        # Find matching rules
        matches = self.rule_memory.find_matching_rules(knowledge)

        for rule, bindings_list in matches:
            for bindings in bindings_list:
                # Get conclusion with bindings applied
                subj, rel, obj = rule.apply_conclusion(bindings)

                # Skip if we already have this fact
                existing = self.loom.get(subj, rel) or []
                if obj in existing:
                    continue

                # Skip if we fired this exact derivation this cycle
                fact_key = (subj, rel, obj, rule.rule_id)
                if fact_key in self._fired_this_cycle:
                    continue

                self._fired_this_cycle.add(fact_key)

                # Add the derived fact
                provenance = {
                    "source_type": "rule",
                    "rule_id": rule.rule_id,
                    "bindings": bindings,
                    "premises": [str(p) for p in rule.premises],
                    "timestamp": time.time()
                }

                self.loom.add_fact(
                    subj, rel, obj,
                    confidence="medium",
                    provenance=provenance
                )

                # Update rule stats
                rule.fire_count += 1
                rule.last_fired = time.time()

                new_facts.append({
                    "subject": subj,
                    "relation": rel,
                    "object": obj,
                    "rule_id": rule.rule_id,
                    "confidence": rule.confidence
                })

                logger.info(f"Rule {rule.rule_id} derived: {subj} {rel} {obj}")

        return new_facts

    def check_rule_applicability(self, rule: Rule) -> List[dict]:
        """
        Check where a rule could apply without actually firing it.

        Returns list of potential derivations.
        """
        potential = []
        knowledge = self.loom.knowledge

        bindings_list = rule.matches_premises(knowledge)

        for bindings in bindings_list:
            subj, rel, obj = rule.apply_conclusion(bindings)

            existing = self.loom.get(subj, rel) or []
            if obj not in existing:
                potential.append({
                    "subject": subj,
                    "relation": rel,
                    "object": obj,
                    "bindings": bindings,
                    "already_known": False
                })
            else:
                potential.append({
                    "subject": subj,
                    "relation": rel,
                    "object": obj,
                    "bindings": bindings,
                    "already_known": True
                })

        return potential
