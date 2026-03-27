"""
Loom Rule Engine - Logic-based rule learning and inference.

Based on research into:
- FOIL (First-Order Inductive Learner)
- Apriori association rule mining
- Forward chaining with quality gates
- Non-monotonic reasoning for exceptions

Key design principles:
1. Minimum support thresholds (rules must match 3+ examples)
2. Confidence calibration (multi-metric scoring)
3. Quality gates to prevent pollution
4. Exception handling for contradictions
"""

import time
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Tuple, Set, Optional, TYPE_CHECKING
from math import log2

if TYPE_CHECKING:
    from .brain import Loom

logger = logging.getLogger(__name__)


class RuleStatus(Enum):
    CANDIDATE = "candidate"      # Newly learned, needs validation
    ACTIVE = "active"            # Validated and in use
    SUSPENDED = "suspended"      # Temporarily disabled (high FP rate)
    REJECTED = "rejected"        # Permanently rejected


@dataclass
class RulePremise:
    """A single condition in a rule."""
    subject_var: str      # Variable like "?X" or constant like "dogs"
    relation: str         # Relation like "is", "has", "can"
    object_var: str       # Variable like "?Y" or constant like "mammals"

    def __hash__(self):
        return hash((self.subject_var, self.relation, self.object_var))

    def __eq__(self, other):
        return (self.subject_var == other.subject_var and
                self.relation == other.relation and
                self.object_var == other.object_var)


@dataclass
class RuleConclusion:
    """The conclusion of a rule."""
    subject_var: str
    relation: str
    object_var: str


@dataclass
class Rule:
    """A logical rule: IF premises THEN conclusion."""
    rule_id: str
    premises: List[RulePremise]
    conclusion: RuleConclusion

    # Quality metrics
    support_count: int = 0        # Number of examples supporting this rule
    confidence: float = 0.0       # P(conclusion | premises)
    lift: float = 1.0             # How much better than random

    # Lifecycle
    status: RuleStatus = RuleStatus.CANDIDATE
    created_at: float = field(default_factory=time.time)
    last_fired: Optional[float] = None
    fire_count: int = 0
    false_positive_count: int = 0

    # Metadata
    source: str = "learned"       # "learned", "explicit", "inherited"

    def __hash__(self):
        return hash(self.rule_id)


class RuleQualityGates:
    """Multi-stage quality gates to prevent low-quality rules."""

    # Minimum thresholds
    MIN_SUPPORT = 3
    MIN_CONFIDENCE = 0.6
    MIN_LIFT = 1.2
    MAX_FALSE_POSITIVE_RATE = 0.15
    MAX_PREMISES = 4

    @classmethod
    def check_all_gates(cls, rule: Rule, knowledge: Dict,
                        positive_count: int, negative_count: int) -> Tuple[bool, str]:
        """Run all quality gates. Returns (passed, reason)."""

        # Gate 1: Structural validity
        passed, reason = cls._check_structure(rule)
        if not passed:
            return False, f"Structure: {reason}"

        # Gate 2: Minimum support
        if positive_count < cls.MIN_SUPPORT:
            return False, f"Support too low: {positive_count} < {cls.MIN_SUPPORT}"

        # Gate 3: Confidence threshold
        total = positive_count + negative_count
        if total > 0:
            confidence = positive_count / total
            if confidence < cls.MIN_CONFIDENCE:
                return False, f"Confidence too low: {confidence:.2%} < {cls.MIN_CONFIDENCE:.0%}"

        # Gate 4: False positive rate
        if total > 0:
            fpr = negative_count / total
            if fpr > cls.MAX_FALSE_POSITIVE_RATE:
                return False, f"FP rate too high: {fpr:.2%}"

        # Gate 5: Not trivial (conclusion doesn't always hold)
        base_rate = cls._conclusion_base_rate(rule, knowledge)
        if base_rate > 0.8:
            return False, f"Trivial rule: conclusion base rate {base_rate:.0%}"

        return True, "OK"

    @classmethod
    def _check_structure(cls, rule: Rule) -> Tuple[bool, str]:
        """Check rule has valid structure."""
        if not rule.premises:
            return False, "No premises"

        if len(rule.premises) > cls.MAX_PREMISES:
            return False, f"Too many premises: {len(rule.premises)}"

        # Variables in conclusion must appear in premises
        conclusion_vars = set()
        if rule.conclusion.subject_var.startswith("?"):
            conclusion_vars.add(rule.conclusion.subject_var)
        if rule.conclusion.object_var.startswith("?"):
            conclusion_vars.add(rule.conclusion.object_var)

        premise_vars = set()
        for p in rule.premises:
            if p.subject_var.startswith("?"):
                premise_vars.add(p.subject_var)
            if p.object_var.startswith("?"):
                premise_vars.add(p.object_var)

        unbound = conclusion_vars - premise_vars
        if unbound:
            return False, f"Unbound variables: {unbound}"

        return True, "OK"

    @classmethod
    def _conclusion_base_rate(cls, rule: Rule, knowledge: Dict) -> float:
        """What % of entities satisfy conclusion regardless of premises?"""
        if not knowledge:
            return 0.0

        matches = 0
        total = len(knowledge)

        for entity, relations in knowledge.items():
            if rule.conclusion.relation in relations:
                if not rule.conclusion.object_var.startswith("?"):
                    if rule.conclusion.object_var in relations[rule.conclusion.relation]:
                        matches += 1
                else:
                    if relations[rule.conclusion.relation]:
                        matches += 1

        return matches / total if total > 0 else 0.0


class LogicalRuleEngine:
    """
    Clean rule learning engine with quality controls.

    Features:
    - FOIL-style rule learning from examples
    - Apriori-style pattern mining
    - Quality gates to prevent pollution
    - Forward chaining with proper binding
    - Exception handling
    """

    def __init__(self, loom: "Loom"):
        self.loom = loom
        self.rules: Dict[str, Rule] = {}
        self.exceptions: Dict[str, List[RulePremise]] = {}  # conclusion -> exceptions

        # Statistics
        self.stats = {
            "rules_learned": 0,
            "rules_rejected": 0,
            "rules_fired": 0,
            "facts_inferred": 0
        }

        # Rule counter for IDs
        self._rule_counter = 0

    def learn_from_if_then(self, text: str) -> Optional[Rule]:
        """
        Learn rule from explicit if-then statement.

        Examples:
        - "if X is mammal then X has fur"
        - "if something is a bird then it can fly"
        """
        text_lower = text.lower().strip()

        # Parse if-then structure
        if " then " not in text_lower:
            return None

        if_part, then_part = text_lower.split(" then ", 1)
        if_part = if_part.replace("if ", "").strip()
        then_part = then_part.strip()

        # Parse premise
        premise = self._parse_condition(if_part, "?X")
        if not premise:
            return None

        # Parse conclusion
        conclusion = self._parse_conclusion(then_part, "?X")
        if not conclusion:
            return None

        # Create rule
        self._rule_counter += 1
        rule = Rule(
            rule_id=f"explicit_{self._rule_counter}",
            premises=[premise],
            conclusion=conclusion,
            support_count=1,
            confidence=0.9,  # High confidence for explicit rules
            source="explicit",
            status=RuleStatus.ACTIVE  # Explicit rules are immediately active
        )

        # Validate
        passed, reason = RuleQualityGates._check_structure(rule)
        if not passed:
            if self.loom.verbose:
                print(f"       [rule rejected: {reason}]")
            return None

        self.rules[rule.rule_id] = rule
        self.stats["rules_learned"] += 1

        return rule

    def _parse_condition(self, text: str, var: str) -> Optional[RulePremise]:
        """Parse a condition like 'X is mammal' into a RulePremise."""
        # Handle patterns like "X is Y", "something is a Y"
        patterns = [
            (r"(\w+) is (?:a |an )?(\w+)", "is"),
            (r"(\w+) has (\w+)", "has"),
            (r"(\w+) can (\w+)", "can"),
            (r"something is (?:a |an )?(\w+)", "is"),
        ]

        import re
        for pattern, relation in patterns:
            match = re.match(pattern, text)
            if match:
                groups = match.groups()
                if len(groups) == 2:
                    subj, obj = groups
                    # Normalize variable names
                    if subj.lower() in ("x", "something", "it", "they"):
                        subj = var
                    return RulePremise(subj, relation, obj)
                elif len(groups) == 1:
                    return RulePremise(var, relation, groups[0])

        return None

    def _parse_conclusion(self, text: str, var: str) -> Optional[RuleConclusion]:
        """Parse conclusion like 'X has fur'."""
        import re

        patterns = [
            (r"(\w+) is (?:a |an )?(\w+)", "is"),
            (r"(\w+) has (\w+)", "has"),
            (r"(\w+) can (\w+)", "can"),
            (r"it has (\w+)", "has"),
            (r"it can (\w+)", "can"),
            (r"it is (?:a |an )?(\w+)", "is"),
        ]

        for pattern, relation in patterns:
            match = re.match(pattern, text)
            if match:
                groups = match.groups()
                if len(groups) == 2:
                    subj, obj = groups
                    if subj.lower() in ("x", "something", "it", "they"):
                        subj = var
                    return RuleConclusion(subj, relation, obj)
                elif len(groups) == 1:
                    return RuleConclusion(var, relation, groups[0])

        return None

    def learn_rules_from_patterns(self) -> List[Rule]:
        """
        Learn rules from patterns in knowledge base.
        Uses Apriori-style mining with FOIL-style refinement.
        """
        learned = []

        # Find category-property associations
        category_properties = self._find_category_property_associations()

        for (category, relation, value), (support, confidence) in category_properties.items():
            # Apply quality gates
            if support < RuleQualityGates.MIN_SUPPORT:
                continue
            if confidence < RuleQualityGates.MIN_CONFIDENCE:
                continue

            # Create rule: if ?X is category then ?X relation value
            self._rule_counter += 1
            rule = Rule(
                rule_id=f"pattern_{self._rule_counter}",
                premises=[RulePremise("?X", "is", category)],
                conclusion=RuleConclusion("?X", relation, value),
                support_count=support,
                confidence=confidence,
                source="learned",
                status=RuleStatus.CANDIDATE
            )

            self.rules[rule.rule_id] = rule
            learned.append(rule)
            self.stats["rules_learned"] += 1

        return learned

    def _find_category_property_associations(self) -> Dict[Tuple, Tuple[int, float]]:
        """
        Find associations: category -> property.

        Returns: {(category, relation, value): (support, confidence)}
        """
        associations = {}

        # Build category membership
        category_members: Dict[str, Set[str]] = defaultdict(set)
        for entity, relations in self.loom.knowledge.items():
            for category in relations.get("is", []):
                category_members[category].add(entity)

        # For each category with enough members
        for category, members in category_members.items():
            if len(members) < RuleQualityGates.MIN_SUPPORT:
                continue

            # Count property occurrences
            property_counts: Dict[Tuple[str, str], int] = defaultdict(int)

            for member in members:
                member_rels = self.loom.knowledge.get(member, {})
                for rel in ["has", "can", "eats", "lives_in", "has_property"]:
                    for val in member_rels.get(rel, []):
                        property_counts[(rel, val)] += 1

            # Calculate confidence for each property
            for (rel, val), count in property_counts.items():
                confidence = count / len(members)
                if confidence >= RuleQualityGates.MIN_CONFIDENCE:
                    associations[(category, rel, val)] = (count, confidence)

        return associations

    def forward_chain(self, max_iterations: int = 10) -> List[Tuple[str, str, str]]:
        """
        Apply rules to infer new facts using forward chaining.

        Returns list of newly inferred (subject, relation, object) tuples.
        """
        inferred = []
        active_rules = [r for r in self.rules.values()
                       if r.status == RuleStatus.ACTIVE]

        for _ in range(max_iterations):
            new_facts = []

            for rule in active_rules:
                # Find all valid bindings for premises
                bindings_list = self._find_bindings(rule)

                for bindings in bindings_list:
                    # Apply bindings to conclusion
                    subj = bindings.get(rule.conclusion.subject_var,
                                       rule.conclusion.subject_var)
                    obj = bindings.get(rule.conclusion.object_var,
                                      rule.conclusion.object_var)
                    rel = rule.conclusion.relation

                    # Check if fact already exists
                    existing = self.loom.get(subj, rel) or []
                    if obj not in existing:
                        # Check for exceptions
                        if self._has_exception(subj, rel, obj):
                            continue

                        new_facts.append((subj, rel, obj))
                        rule.fire_count += 1
                        rule.last_fired = time.time()

            if not new_facts:
                break  # Fixed point reached

            # Add new facts with lower confidence
            for subj, rel, obj in new_facts:
                self.loom.add_fact(subj, rel, obj, confidence="medium",
                                  _propagate=False)
                inferred.append((subj, rel, obj))
                self.stats["facts_inferred"] += 1

        return inferred

    def _find_bindings(self, rule: Rule) -> List[Dict[str, str]]:
        """Find all variable bindings that satisfy rule premises."""
        if not rule.premises:
            return [{}]

        # Start with first premise
        bindings_list = self._match_premise(rule.premises[0], {})

        # Join with remaining premises
        for premise in rule.premises[1:]:
            new_bindings = []
            for bindings in bindings_list:
                extended = self._match_premise(premise, bindings)
                new_bindings.extend(extended)
            bindings_list = new_bindings

        return bindings_list

    def _match_premise(self, premise: RulePremise,
                       current_bindings: Dict[str, str]) -> List[Dict[str, str]]:
        """Find bindings that satisfy a single premise."""
        results = []

        for entity, relations in self.loom.knowledge.items():
            # Check subject binding
            if premise.subject_var.startswith("?"):
                if premise.subject_var in current_bindings:
                    if current_bindings[premise.subject_var] != entity:
                        continue
                subj_binding = entity
            else:
                if premise.subject_var != entity:
                    continue
                subj_binding = None

            # Check relation exists
            if premise.relation not in relations:
                continue

            # Check object binding
            for obj in relations[premise.relation]:
                if premise.object_var.startswith("?"):
                    if premise.object_var in current_bindings:
                        if current_bindings[premise.object_var] != obj:
                            continue
                    obj_binding = obj
                else:
                    if premise.object_var != obj:
                        continue
                    obj_binding = None

                # Create new bindings
                new_bindings = current_bindings.copy()
                if subj_binding and premise.subject_var.startswith("?"):
                    new_bindings[premise.subject_var] = subj_binding
                if obj_binding and premise.object_var.startswith("?"):
                    new_bindings[premise.object_var] = obj_binding

                results.append(new_bindings)

        return results

    def add_exception(self, conclusion_relation: str,
                      exception_condition: RulePremise):
        """Add an exception to rules with given conclusion."""
        key = conclusion_relation
        if key not in self.exceptions:
            self.exceptions[key] = []
        self.exceptions[key].append(exception_condition)

    def _has_exception(self, subject: str, relation: str, obj: str) -> bool:
        """Check if an exception applies to this conclusion."""
        exceptions = self.exceptions.get(relation, [])

        for exc in exceptions:
            # Check if subject matches exception condition
            subj_rels = self.loom.knowledge.get(subject, {})
            if exc.relation in subj_rels:
                if exc.object_var in subj_rels[exc.relation]:
                    return True

        return False

    def learn_exception_from_contradiction(self, subject: str,
                                           expected_relation: str,
                                           expected_value: str,
                                           actual_relation: str,
                                           actual_value: str):
        """
        Learn an exception when we encounter a contradiction.

        Example: Expected penguin can fly, but actual is penguin cannot fly.
        Learn: exception to "can fly" if "is penguin" or similar distinguishing property.
        """
        # Find distinguishing property of this subject
        subj_rels = self.loom.knowledge.get(subject, {})

        # Look for specific category or property
        for rel in ["is", "has", "has_property"]:
            for val in subj_rels.get(rel, []):
                # Create exception condition
                exception = RulePremise("?X", rel, val)
                self.add_exception(expected_relation, exception)

                if self.loom.verbose:
                    print(f"       [learned exception: {expected_relation} blocked if {rel} {val}]")
                return

    def cleanup_rules(self):
        """Remove low-quality rules to prevent pollution."""
        to_remove = []

        for rule_id, rule in self.rules.items():
            # Remove candidates that never got validated
            if rule.status == RuleStatus.CANDIDATE:
                age = time.time() - rule.created_at
                if age > 300 and rule.fire_count == 0:  # 5 min old, never fired
                    to_remove.append(rule_id)
                    continue

            # Suspend rules with high false positive rate
            if rule.fire_count > 0:
                fpr = rule.false_positive_count / rule.fire_count
                if fpr > RuleQualityGates.MAX_FALSE_POSITIVE_RATE:
                    rule.status = RuleStatus.SUSPENDED

        for rule_id in to_remove:
            del self.rules[rule_id]
            self.stats["rules_rejected"] += 1

    def get_active_rules(self) -> List[Rule]:
        """Get all active rules."""
        return [r for r in self.rules.values() if r.status == RuleStatus.ACTIVE]

    def get_statistics(self) -> Dict:
        """Get engine statistics."""
        return {
            **self.stats,
            "total_rules": len(self.rules),
            "active_rules": len(self.get_active_rules()),
            "candidate_rules": len([r for r in self.rules.values()
                                   if r.status == RuleStatus.CANDIDATE]),
            "exceptions": sum(len(v) for v in self.exceptions.values())
        }
