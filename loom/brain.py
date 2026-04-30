"""
Loom - Core knowledge storage and management.
Weaves threads of knowledge into a connected tapestry.

Enhanced with:
- Confidence levels (high/medium/low)
- Fact retraction and correction
- Constraints (conditions on facts)
- Procedural knowledge (sequences)
- Conflict detection
- MongoDB storage backend (with JSON fallback)
- Spreading activation network (Collins & Loftus model)
- Hebbian connection strengthening
- Text chunking for paragraph processing
- Transitive inheritance (category chains)
- Faceted classification (property-based groupings)
- Automatic connection discovery
"""

from typing import Dict, Tuple

from .normalizer import normalize, prettify_cause, prettify_effect
from .inference import InferenceEngine
from .parser import Parser
from .visualizer import visualize_graph, visualize_node, visualize_compact
from .context import ConversationContext
from .storage import get_storage, MongoStorage
from .activation import ActivationNetwork
from .chunker import TextChunker
from .training import TrainingMixin
from .discovery import DiscoveryMixin, ConnectionDiscoveryEngine
from .processing import HebbianMixin, ProcessingMixin
from .frames import FrameManager
from .curiosity import QuestionGenerator, CuriosityNodeManager
from .speech import SpeechProcessor, ASRBackend
from .rules import RuleMemory, RuleEngine, Rule, RuleStatus
from .style_learner import StyleLearner

# Confidence levels
CONFIDENCE_HIGH = "high"      # Directly stated by user
CONFIDENCE_MEDIUM = "medium"  # Inferred from patterns
CONFIDENCE_LOW = "low"        # Weak inference or old

# Relations that should trigger inheritance propagation
INHERITABLE_RELATIONS = ["is", "is_a", "type_of", "kind_of"]

# Import context detection functions
from .context_detection import detect_context, detect_temporal, detect_scope


def confidence_for_source(source_type: str) -> str:
    """
    Get default confidence level based on source type.
    User-stated facts get high confidence.
    Inferred/inherited facts get medium confidence.
    """
    if source_type in ("user", "clarification"):
        return CONFIDENCE_HIGH
    elif source_type in ("inference", "inheritance"):
        return CONFIDENCE_MEDIUM
    else:
        return CONFIDENCE_LOW


def consolidate_confidence(current: str, new: str) -> str:
    """
    Consolidate confidence when a fact is mentioned again.
    Repeated mentions strengthen confidence (like memory consolidation).

    Rules:
    - low + any = medium (fact confirmed once)
    - medium + any = high (fact confirmed twice)
    - high + any = high (already max)
    """
    # Priority order
    levels = {CONFIDENCE_LOW: 1, CONFIDENCE_MEDIUM: 2, CONFIDENCE_HIGH: 3}

    current_level = levels.get(current, 1)
    new_level = levels.get(new, 1)

    # Take the higher of the two, plus one level for consolidation
    combined = max(current_level, new_level) + 1

    # Cap at high
    if combined >= 3:
        return CONFIDENCE_HIGH
    elif combined == 2:
        return CONFIDENCE_MEDIUM
    else:
        return CONFIDENCE_LOW


class Loom(TrainingMixin, DiscoveryMixin, HebbianMixin, ProcessingMixin):
    """
    The main knowledge system.
    Stores facts as a directed graph and manages inference.
    """

    def __init__(self, name: str = "loom", verbose: bool = False,
                 mongo_uri: str = None, database_name: str = "loom",
                 # Legacy params kept for backwards compat — ignored
                 use_mongo: bool = True, memory_file: str = None):
        self.name = name
        self.verbose = verbose  # Show debug output when True

        # Initialize MongoDB storage
        storage_kwargs = dict(
            database_name=database_name,
            instance_name=name,
        )
        if mongo_uri:
            storage_kwargs["connection_string"] = mongo_uri
        self.storage = get_storage(**storage_kwargs)
        self.use_mongo = True

        # In-memory cache for fast access (synced with storage)
        self._knowledge_cache = None
        self._cache_dirty = True

        # Current input context (set by parser during processing)
        self._input_context = None
        self._input_properties = None
        self._session_speaker_id = None  # Set by web app, persists across parse calls

        # Runtime state (not persisted)
        self.conflicts = []  # Current session conflicts
        self.pending = {}  # Open questions
        self.recent = []  # Recent facts for background processing

        # Speech processing state
        self._speech_processor = None
        self._current_speech_provenance = None

        # Conversation context pool — one ConversationContext per conversation_id
        # Default context used when no conversation_id is set
        self._context_pool: Dict[str, ConversationContext] = {}
        self._default_context = ConversationContext(conversation_id="_default")
        self._current_conversation_id: str = "_default"
        self._context_pool["_default"] = self._default_context

        # Spreading activation network (Collins & Loftus model)
        # Increased priming window (30s) and slower decay for better concept retention
        self.activation = ActivationNetwork(
            decay_rate=0.12,
            spread_factor=0.5,
            priming_window=30.0,
            topic_priming_window=120.0  # 2 minutes for topic concepts
        )

        # Connection weights for Hebbian strengthening
        # Key: (subject, relation, object) -> weight
        self.connection_weights: Dict[Tuple[str, str, str], float] = {}

        # Track last activation time for each connection (for decay)
        self.connection_times: Dict[Tuple[str, str, str], float] = {}

        # Text chunker for paragraph processing
        self.chunker = TextChunker()

        # Initialize with self-knowledge
        self.add_fact("self", "name_is", self.name, _save=True)

        # Initialize default Loom knowledge (about itself)
        self._init_loom_knowledge()

        # Create parser and inference engine
        self.parser = Parser(self)
        self.inference = InferenceEngine(self)
        self.inference.start()

        # Curiosity engine for active questioning
        self.curiosity = QuestionGenerator(self)

        # Curiosity node manager for unknown concepts
        self.curiosity_nodes = CuriosityNodeManager(self)

        # Rule memory and forward chaining engine
        self.rule_memory = RuleMemory(
            self,
            use_mongo=self.use_mongo,
            storage_path="loom_memory/loom_rules.json"
        )
        self.rule_engine = RuleEngine(self, self.rule_memory)

        # Connection discovery engine for background pattern learning
        self.discovery_engine = ConnectionDiscoveryEngine(self)

        # Frame-based knowledge layer for attribute slots and emergent categorization
        self.frame_manager = FrameManager(self)
        self.frame_manager.hydrate_from_knowledge()

        # Style learner: extracts writing patterns from user input + feedback
        self.style_learner = StyleLearner(self)

    def _init_loom_knowledge(self):
        """Initialize default knowledge about Loom itself."""
        # Only add if loom doesn't already have core facts
        existing = self.storage.get_facts("loom", "is")
        if existing:
            return  # Already has knowledge

        # System context and properties for Loom's self-knowledge
        sys_props = {
            "temporal": "always",
            "scope": "universal",
            "source_type": "system"
        }

        # What Loom is
        self.storage.add_fact("loom", "is", "knowledge_system", "high",
                              context="system", properties=sys_props)

        # What Loom does
        self.storage.add_fact("loom", "can", "learn_from_conversation", "high",
                              context="system", properties=sys_props)
        self.storage.add_fact("loom", "can", "remember_facts", "high",
                              context="system", properties=sys_props)
        self.storage.add_fact("loom", "can", "answer_questions", "high",
                              context="system", properties=sys_props)
        self.storage.add_fact("loom", "can", "connect_concepts", "high",
                              context="system", properties=sys_props)
        self.storage.add_fact("loom", "can", "make_inferences", "high",
                              context="system", properties=sys_props)

        # How Loom works (high-level)
        self.storage.add_fact("loom", "uses", "neurons_and_synapses", "high",
                              context="system", properties=sys_props)
        self.storage.add_fact("loom", "learns_through", "natural_language", "high",
                              context="system", properties=sys_props)

        # Commands users can use
        self.storage.add_fact("loom", "has_command", "show", "high",
                              context="system", properties=sys_props)
        self.storage.add_fact("loom", "has_command", "help", "high",
                              context="system", properties=sys_props)
        self.storage.add_fact("loom", "has_command", "neuron", "high",
                              context="system", properties=sys_props)
        self.storage.add_fact("loom", "has_command", "train", "high",
                              context="system", properties=sys_props)
        self.storage.add_fact("loom", "has_command", "forget", "high",
                              context="system", properties=sys_props)

        # Invalidate cache after adding
        self._invalidate_cache()

    @property
    def knowledge(self) -> dict:
        """Get knowledge graph (cached from storage)."""
        if self._cache_dirty or self._knowledge_cache is None:
            self._knowledge_cache = self.storage.get_all_knowledge()
            self._cache_dirty = False
        return self._knowledge_cache

    def _invalidate_cache(self):
        """Mark cache as needing refresh."""
        self._cache_dirty = True

    # ── Per-conversation context pool ──────────────────────────────────

    @property
    def context(self) -> "ConversationContext":
        """Return the context for the current conversation."""
        return self._context_pool[self._current_conversation_id]

    @context.setter
    def context(self, value: "ConversationContext"):
        """Assign a context directly (used for backward compat)."""
        self._context_pool[self._current_conversation_id] = value

    def set_conversation(self, conversation_id: str) -> None:
        """
        Switch to a specific conversation's context.
        Creates/restores a ConversationContext for this conversation.
        Evicts old contexts and saves them to MongoDB.
        """
        import time
        if not conversation_id:
            conversation_id = "_default"

        if conversation_id not in self._context_pool:
            # Try to restore from MongoDB first
            ctx = None
            try:
                doc = self.storage.db.conversations.find_one({
                    "instance": self.storage.instance_name,
                    "conversation_id": conversation_id,
                })
                if doc and doc.get("snapshot"):
                    ctx = ConversationContext.from_snapshot(doc["snapshot"])
            except Exception:
                pass

            if not ctx:
                ctx = ConversationContext(conversation_id=conversation_id)
            ctx.set_knowledge_ref(self.knowledge)
            self._context_pool[conversation_id] = ctx

        self._context_pool[conversation_id].last_active = time.time()
        self._current_conversation_id = conversation_id

        # Opportunistic eviction: save + drop contexts idle > 2 hours
        now = time.time()
        stale_cutoff = now - 2 * 3600
        for cid in list(self._context_pool.keys()):
            if cid == "_default" or cid == conversation_id:
                continue
            if self._context_pool[cid].last_active < stale_cutoff:
                self._save_conversation(cid)
                del self._context_pool[cid]

    def _save_conversation(self, conversation_id: str) -> None:
        """Persist a conversation context to MongoDB."""
        ctx = self._context_pool.get(conversation_id)
        if not ctx or conversation_id == "_default":
            return
        try:
            self.storage.db.conversations.update_one(
                {"instance": self.storage.instance_name, "conversation_id": conversation_id},
                {"$set": {
                    "snapshot": ctx.to_snapshot(),
                    "updated_at": __import__('datetime').datetime.now(
                        __import__('datetime').timezone.utc).isoformat(),
                }},
                upsert=True,
            )
        except Exception:
            pass

    def _is_valid_entity(self, name: str) -> bool:
        """Check if an entity name is valid (not polluted/malformed)."""
        if not name or len(name) < 2:
            return False

        name_lower = name.lower().strip()
        words = name_lower.replace("_", " ").split()

        # Reject names with repeated words (pollution indicator)
        if len(words) > 1 and len(words) != len(set(words)):
            return False

        # Reject very long names (likely malformed)
        if len(name) > 50:
            return False

        # Reject names with periods or commas (sentence fragments)
        if "." in name or "," in name:
            return False

        # Reject names that look like sentences (too many words)
        if len(words) > 4:
            return False

        # Reject names starting with bad patterns (malformed parsing)
        bad_starts = [
            # Conjunctions
            "and_", "or_", "but_", "because_", "so_", "yet_",
            # Articles
            "the_", "a_", "an_",
            # Relative pronouns
            "that_", "which_", "who_", "whom_", "whose_",
            # Question words
            "when_", "where_", "how_", "why_", "what_",
            # Prepositions
            "by_", "for_", "with_", "from_", "to_", "in_", "on_", "at_",
            "of_", "about_", "into_", "onto_", "upon_",
            # Adverbs (indicate sentence fragments)
            "highly_", "very_", "really_", "sometimes_", "often_",
            "always_", "never_", "usually_", "also_", "just_",
            "only_", "even_", "still_", "already_",
            # Verbs that indicate sentence fragments
            "is_", "are_", "was_", "were_", "be_", "been_", "being_",
            "has_", "have_", "had_", "do_", "does_", "did_",
            "can_", "could_", "will_", "would_", "should_", "may_", "might_",
        ]
        for bad in bad_starts:
            if name_lower.startswith(bad):
                return False

        # Reject names ending with bad patterns (incomplete parsing)
        bad_ends = [
            "_and", "_or", "_but", "_the", "_a", "_an",
            "_is", "_are", "_was", "_were", "_be",
            "_has", "_have", "_had", "_do", "_does",
            "_can", "_will", "_would", "_should",
            "_to", "_for", "_with", "_from", "_in", "_on", "_at",
            "_that", "_which", "_who",
        ]
        for bad in bad_ends:
            if name_lower.endswith(bad):
                return False

        # Reject pure pronouns
        if name_lower in ["they", "them", "it", "he", "she", "we", "i", "you", "your",
                          "this", "that", "these", "those", "its", "their"]:
            return False

        # Reject if contains verb patterns indicating sentence fragments
        # e.g., "shark_possess_incredible" contains "possess" which is a verb
        sentence_verbs = [
            "_possess_", "_possesses_", "_contain_", "_contains_",
            "_include_", "_includes_", "_provide_", "_provides_",
            "_cause_", "_causes_", "_create_", "_creates_",
            "_exist_", "_exists_", "_form_", "_forms_",
            "_call_", "_calls_", "_called_",
            "_kill_", "_kills_", "_support_", "_supports_",
        ]
        for verb in sentence_verbs:
            if verb in name_lower:
                return False

        # Reject if first word is an adverb or modifier that doesn't make sense alone
        bad_first_words = [
            "highly", "very", "really", "sometimes", "often", "always",
            "never", "usually", "incredibly", "extremely", "mostly",
            "probably", "possibly", "actually", "basically", "generally",
            "typically", "commonly", "rarely", "frequently", "occasionally",
            "primarily", "mainly", "largely", "mostly", "particularly",
        ]
        if words and words[0] in bad_first_words:
            return False

        # Reject if last word is a verb or auxiliary
        bad_last_words = [
            "is", "are", "was", "were", "be", "been", "being",
            "has", "have", "had", "do", "does", "did",
            "can", "could", "will", "would", "should", "may", "might",
            "believe", "believes", "think", "thinks", "know", "knows",
            "say", "says", "said", "make", "makes", "made",
        ]
        if words and words[-1] in bad_last_words:
            return False

        # Reject single auxiliary/modal words
        single_word_rejects = [
            "will", "would", "could", "should", "may", "might", "must",
            "shall", "can", "do", "does", "did", "has", "have", "had",
            "is", "are", "was", "were", "be", "been", "being",
            "the", "a", "an", "and", "or", "but", "so", "yet",
        ]
        if len(words) == 1 and words[0] in single_word_rejects:
            return False

        # Reject compound patterns that indicate sentence fragments
        # e.g., "scientist_believe", "black_hole_region_spacetime"
        if len(words) >= 2:
            # Check for verb as second-to-last or last word in compounds
            verbs_in_compound = [
                "believe", "believes", "think", "thinks", "say", "says",
                "make", "makes", "know", "knows", "see", "sees",
                "show", "shows", "prove", "proves", "suggest", "suggests",
                "indicate", "indicates", "reveal", "reveals",
                "composed", "formed", "named", "called",
            ]
            for verb in verbs_in_compound:
                if verb in words:
                    return False

        return True

    def _is_junk_neuron(self, entity: str, relations: dict) -> bool:
        """
        Check if a neuron is junk and should be cleaned up.
        Junk neurons have only reverse relations and no useful information.
        """
        if not relations:
            return True

        # Relations that indicate the neuron is just a reverse link
        reverse_only_rels = {
            'eaten_by', 'belongs_to', 'helped_by', 'needed_by',
            'has_instance', 'home_of', 'includes', 'requires',
            'drunk_by', 'built_by', 'caused_by', 'created_by'
        }

        # Check if ALL relations are reverse-only
        all_reverse = all(r in reverse_only_rels for r in relations.keys())

        # Check total connections
        total_connections = sum(len(v) for v in relations.values())

        # It's junk if it's reverse-only with very few connections
        if all_reverse and total_connections <= 2:
            return True

        # Check for property-like names (adjective_noun patterns)
        words = entity.replace("_", " ").split()
        if len(words) >= 2 and total_connections <= 1:
            # Likely a property value like "blue_blood", "sharp_teeth"
            return True

        return False

    def cleanup_junk_neurons(self) -> int:
        """
        Remove junk neurons from the knowledge graph.
        Returns the number of neurons removed.
        """
        removed = 0
        to_remove = []

        for entity, relations in self.knowledge.items():
            if entity == 'self':
                continue
            if self._is_junk_neuron(entity, relations):
                to_remove.append(entity)

        for entity in to_remove:
            # Remove all facts involving this entity
            self.storage.remove_entity(entity)
            removed += 1
            if self.verbose:
                print(f"       [cleaned up junk neuron: {entity}]")

        if removed > 0:
            self._invalidate_cache()

        return removed

    def add_fact(self, subject: str, relation: str, obj: str,
                 confidence: str = None, _save: bool = True,
                 _propagate: bool = True, provenance: dict = None,
                 context: str = None, properties: dict = None):
        """
        Add a fact to the knowledge graph with Quad + Properties schema.

        Args:
            subject: The subject of the fact
            relation: The relation type
            obj: The object of the fact
            confidence: Confidence level (high/medium/low) - moved to properties
            _save: Whether to persist to storage
            _propagate: Whether to propagate inheritance
            provenance: Legacy provenance dict (converted to properties)
            context: Context for the fact (general, domestic, scientific, etc.)
            properties: Full properties dict with temporal, scope, conditions, etc.

        If confidence is not specified, it is determined by the source type:
        - user/clarification: high confidence
        - inference/inheritance: medium confidence
        - speech: based on ASR confidence
        - system/unknown: low confidence
        """
        from .resolver import resolve_to_existing_neuron

        # Build context dict for contextual resolution
        resolution_context = None
        if hasattr(self, 'context') and self.context:
            resolution_context = {
                "last_subject": getattr(self.context, 'last_subject', None),
                "last_object": getattr(self.context, 'last_object', None),
                "topics": getattr(self.context, '_topic_concepts', []) if hasattr(self.context, '_topic_concepts') else []
            }

        # Resolve subject and object to existing neurons if possible
        s, s_resolution = resolve_to_existing_neuron(subject, self.knowledge, resolution_context)
        r = relation.lower().strip()
        o, o_resolution = resolve_to_existing_neuron(obj, self.knowledge, resolution_context)

        # Log resolution if verbose and resolution happened
        if self.verbose:
            if s_resolution != "new" and s_resolution != "exact":
                print(f"       [resolved: '{subject}' -> '{s}' ({s_resolution})]")
            if o_resolution != "new" and o_resolution != "exact":
                print(f"       [resolved: '{obj}' -> '{o}' ({o_resolution})]")

        # Intercept possibility statements: "can be X", "could be X", etc.
        # These have malformed objects like "be orange" that fail validation.
        # Route to frame manager as potential attributes instead of storing
        # junk triples in the knowledge graph.
        if r in ("can", "could", "may", "might") and (
                o.startswith("be ") or o.startswith("be_")):
            if hasattr(self, 'frame_manager'):
                self.frame_manager._handle_can_relation(s, o)
            return

        # Validate entity names to prevent pollution
        if not self._is_valid_entity(s) or not self._is_valid_entity(o):
            if self.verbose:
                print(f"       [rejected invalid entity: {s} or {o}]")
            return

        # Use speech provenance if available and no explicit provenance given
        if provenance is None and self._current_speech_provenance is not None:
            provenance = self._current_speech_provenance.copy()

        # Determine confidence from provenance if not explicitly provided
        if confidence is None:
            if provenance and "source_type" in provenance:
                source_type = provenance["source_type"]
                if source_type == "speech":
                    # Use ASR confidence if available
                    asr_conf = provenance.get("confidence", 0.8)
                    if asr_conf >= 0.9:
                        confidence = CONFIDENCE_HIGH
                    elif asr_conf >= 0.7:
                        confidence = CONFIDENCE_MEDIUM
                    else:
                        confidence = CONFIDENCE_LOW
                else:
                    confidence = confidence_for_source(source_type)
            else:
                # Check structural extraction confidence hint (hedging)
                if (self._input_properties and
                        self._input_properties.get("confidence_hint") == "low"):
                    confidence = CONFIDENCE_LOW
                else:
                    confidence = CONFIDENCE_HIGH  # Default: user-stated

        # Check for conflicts before adding
        if _save:
            conflict = self._check_conflict(s, r, o)
            if conflict:
                self.conflicts.append(conflict)
                self.storage.add_conflict(conflict)
                if self.verbose:
                    print(f"       [conflict detected: {conflict}]")

        # Check if fact already exists - if so, consolidate (strengthen confidence)
        existing = self.get(s, r) or []
        if o in existing:
            # Fact already exists - consolidate by strengthening
            current_confidence = self.get_confidence(s, r, o)
            new_confidence = self._consolidate_confidence(current_confidence, confidence)
            if new_confidence != current_confidence:
                self.update_confidence(s, r, o, new_confidence)
                if self.verbose:
                    print(f"       [consolidated: {s} ~> {r} ~> {o} ({current_confidence} → {new_confidence})]")
            # Also strengthen Hebbian weight on repeated mention
            if hasattr(self, 'strengthen_connection'):
                self.strengthen_connection(s, r, o, amount=0.3)
            # Notify frame manager of consolidation (may promote potential->confirmed)
            if hasattr(self, 'frame_manager'):
                self.frame_manager.on_fact_added(s, r, o, new_confidence)
            return  # Don't add duplicate

        # Use input context as fallback if no explicit context provided
        ctx = context
        if ctx is None and self._input_context:
            ctx = self._input_context

        # Build properties from provided values or legacy provenance
        props = properties.copy() if properties else {}
        if self._input_properties and not properties:
            props.update(self._input_properties)
        props["confidence"] = confidence
        if provenance:
            props["source_type"] = provenance.get("source_type", "user")
            props["premises"] = provenance.get("premises", [])
            props["rule_id"] = provenance.get("rule_id")
            props["speaker_id"] = provenance.get("speaker_id")
            props["derivation_id"] = provenance.get("derivation_id")

        # Ensure speaker_id from session
        if self._session_speaker_id and not props.get("speaker_id"):
            props["speaker_id"] = self._session_speaker_id

        # Add to storage with context and properties
        added = self.storage.add_fact(s, r, o, confidence,
                                       context=ctx, properties=props)

        if added:
            self._invalidate_cache()
            self.recent.append((s, r, o))

            if self.verbose:
                print(f"       [woven: {s} ~> {r} ~> {o} ({confidence})]")

            # Update frame system
            if hasattr(self, 'frame_manager'):
                self.frame_manager.on_fact_added(s, r, o, confidence)

            # Run immediate inference for important relations
            if _save and hasattr(self, 'inference'):
                self.inference.process_immediate(s, r, o)

            # Propagate inheritance for "is" relations
            if _propagate and r in INHERITABLE_RELATIONS:
                self._propagate_inheritance(s, o, confidence)
                # Track reverse: object has instance subject
                self._add_instance(o, s)

            # Update facets for location-based groupings
            if _propagate and r == "lives_in":
                self._update_location_facet(s, o)

        # Bidirectional link for colors
        if r == "color":
            self.add_fact(obj, "is_color_of", subject, confidence, _save, _propagate=False)

    def add_facts_batch(self, facts: list, speaker_id: str = None) -> dict:
        """
        Batch-add facts using pandas for normalization, deduplication, and
        conflict detection, then bulk-insert into MongoDB.

        Args:
            facts: List of tuples (subject, relation, object) or dicts with those keys.
            speaker_id: Optional speaker ID to tag all facts.

        Returns:
            dict with keys: inserted, duplicates, conflicts, invalid, total
        """
        import pandas as pd
        from datetime import datetime, timezone
        from .models import SourceType

        if not facts:
            return {"inserted": 0, "duplicates": 0, "conflicts": 0, "invalid": 0, "total": 0}

        # --- Build DataFrame ---
        rows = []
        for f in facts:
            if isinstance(f, (list, tuple)) and len(f) >= 3:
                rows.append({"subject": str(f[0]), "relation": str(f[1]), "object": str(f[2])})
            elif isinstance(f, dict) and "subject" in f and "relation" in f and "object" in f:
                rows.append({"subject": str(f["subject"]), "relation": str(f["relation"]), "object": str(f["object"])})
        if not rows:
            return {"inserted": 0, "duplicates": 0, "conflicts": 0, "invalid": 0, "total": len(facts)}

        df = pd.DataFrame(rows)
        total = len(df)

        # --- Vectorized normalization ---
        df["subject"] = df["subject"].apply(normalize)
        df["object"] = df["object"].apply(normalize)
        df["relation"] = df["relation"].str.lower().str.strip()

        # --- Validate entities ---
        valid_mask = df["subject"].apply(self._is_valid_entity) & df["object"].apply(self._is_valid_entity)
        invalid_count = int((~valid_mask).sum())
        df = df[valid_mask].copy()

        # --- Deduplicate within batch ---
        before_dedup = len(df)
        df = df.drop_duplicates(subset=["subject", "relation", "object"])
        batch_dupes = before_dedup - len(df)

        # --- Within-batch conflict detection (fast, no DB lookups) ---
        conflict_pairs = set()
        neg_map = {"is": "is_not", "can": "cannot", "has": "has_not"}
        for pos, neg in neg_map.items():
            pos_df = df[df["relation"] == pos][["subject", "object"]].rename(columns={"object": "pos_obj"})
            neg_df = df[df["relation"] == neg][["subject", "object"]].rename(columns={"object": "neg_obj"})
            if not pos_df.empty and not neg_df.empty:
                merged = pos_df.merge(neg_df, on="subject")
                matches = merged[merged["pos_obj"] == merged["neg_obj"]]
                for _, row in matches.iterrows():
                    conflict_pairs.add((row["subject"], row["pos_obj"]))
        conflict_count = len(conflict_pairs)

        # --- Build MongoDB documents ---
        now = datetime.now(timezone.utc).isoformat()
        docs = []
        for _, row in df.iterrows():
            props = {
                "confidence": "high",
                "temporal": "always",
                "scope": "universal",
                "conditions": [],
                "source_type": "user",
                "created_at": now,
                "premises": [],
                "rule_id": None,
                "speaker_id": speaker_id or getattr(self, '_session_speaker_id', None),
                "derivation_id": None,
            }
            docs.append({
                "instance": self.storage.instance_name,
                "subject": row["subject"],
                "relation": row["relation"],
                "object": row["object"],
                "context": "general",
                "properties": props,
            })

        # --- Bulk insert ---
        inserted = self.storage.add_facts_bulk(docs) if docs else 0
        db_dupes = len(docs) - inserted

        # --- Post-batch processing ---
        self._invalidate_cache()

        # Strengthen connections for all inserted facts
        for _, row in df.iterrows():
            key = (row["subject"], row["relation"], row["object"])
            self.connection_weights[key] = self.connection_weights.get(key, 1.0) + 0.1

        # Queue all for background inference (single pass)
        for _, row in df.iterrows():
            self.recent.append((row["subject"], row["relation"], row["object"]))

        # Light activation for batch — just mark concepts as recently seen
        # Full spreading activation happens in the background inference loop
        try:
            for concept in df["subject"].unique()[:50]:
                self.activation.activate(concept, amount=0.3)
        except Exception:
            pass

        if self.verbose:
            print(f"  [batch] {inserted} inserted, {batch_dupes + db_dupes} duplicates, "
                  f"{conflict_count} conflicts, {invalid_count} invalid / {total} total")

        return {
            "inserted": inserted,
            "duplicates": batch_dupes + db_dupes,
            "conflicts": conflict_count,
            "invalid": invalid_count,
            "total": total,
        }

    def retract_fact(self, subject: str, relation: str, obj: str,
                     cascade: bool = True):
        """
        Remove a fact from the knowledge graph.

        Args:
            subject: The subject of the fact
            relation: The relation type
            obj: The object of the fact
            cascade: If True (default), also retract dependent inferred facts

        Returns:
            dict with 'retracted' (bool) and 'cascade_count' (int)
        """
        s = normalize(subject)
        r = relation.lower().strip()
        o = normalize(obj)

        result = self.storage.retract_fact(s, r, o, cascade=cascade)

        if result["retracted"]:
            self._invalidate_cache()
            if self.verbose:
                print(f"       [unwoven: {s} ~> {r} ~> {o}]")
                if result["cascade_count"] > 0:
                    print(f"       [cascaded: {result['cascade_count']} dependent facts also retracted]")

        return result

    def add_constraint(self, subject: str, relation: str, obj: str, condition: str):
        """Add a constraint/condition to a fact."""
        s = normalize(subject)
        r = relation.lower().strip()
        o = normalize(obj)
        c = normalize(condition)

        self.storage.add_constraint(s, r, o, c)
        if self.verbose:
            print(f"       [constraint: {s} ~> {r} ~> {o} ONLY IF {c}]")

    def get_constraints(self, subject: str, relation: str, obj: str) -> list:
        """Get constraints for a fact."""
        s = normalize(subject)
        r = relation.lower().strip()
        o = normalize(obj)
        return self.storage.get_constraints(s, r, o)

    def add_procedure(self, name: str, steps: list):
        """Add a procedural sequence."""
        n = normalize(name)
        self.storage.add_procedure(n, steps)
        if self.verbose:
            print(f"       [procedure: {n} with {len(steps)} steps]")

    def get_procedure(self, name: str) -> list:
        """Get steps for a procedure."""
        return self.storage.get_procedure(normalize(name))

    def _check_conflict(self, subject: str, relation: str, obj: str) -> dict | None:
        """Check if new fact conflicts with existing knowledge."""
        # Check for direct contradiction (is vs is_not)
        if relation == "is":
            negations = self.get(subject, "is_not") or []
            if obj in negations:
                return {
                    "type": "contradiction",
                    "fact1": f"{subject} is {obj}",
                    "fact2": f"{subject} is_not {obj}"
                }
        elif relation == "is_not":
            positives = self.get(subject, "is") or []
            if obj in positives:
                return {
                    "type": "contradiction",
                    "fact1": f"{subject} is_not {obj}",
                    "fact2": f"{subject} is {obj}"
                }

        # Check for can vs cannot
        if relation == "can":
            cannots = self.get(subject, "cannot") or []
            if obj in cannots:
                return {
                    "type": "contradiction",
                    "fact1": f"{subject} can {obj}",
                    "fact2": f"{subject} cannot {obj}"
                }
        elif relation == "cannot":
            cans = self.get(subject, "can") or []
            if obj in cans:
                return {
                    "type": "contradiction",
                    "fact1": f"{subject} cannot {obj}",
                    "fact2": f"{subject} can {obj}"
                }

        return None

    def get_confidence(self, subject: str, relation: str, obj: str) -> str:
        """Get confidence level for a fact."""
        s = normalize(subject)
        r = relation.lower().strip()
        o = normalize(obj)
        return self.storage.get_confidence(s, r, o)

    def update_confidence(self, subject: str, relation: str, obj: str, confidence: str):
        """Update confidence level for a fact."""
        s = normalize(subject)
        r = relation.lower().strip()
        o = normalize(obj)
        self.storage.update_confidence(s, r, o, confidence)

    def _consolidate_confidence(self, current: str, new: str) -> str:
        """Consolidate confidence when a fact is repeated."""
        return consolidate_confidence(current, new)

    def get(self, subject: str, relation: str, context: str = None,
            temporal: str = None) -> list | None:
        """
        Get targets for a subject-relation pair, optionally filtered by context and temporal scope.

        Args:
            subject: The entity to query
            relation: The relation type
            context: Optional context filter
            temporal: Optional temporal filter ("always", "currently", "past", "future", "sometimes")
                     If None, returns all facts regardless of temporal scope.
                     If "currently", returns "always" and "currently" scoped facts.

        Returns:
            List of target values or None if not found
        """
        # If no temporal filter, use the simple query
        if temporal is None:
            results = self.storage.get_facts(normalize(subject), relation.lower().strip(),
                                              context=context)
            return results if results else None

        # Get facts with properties to filter by temporal
        full_facts = self.storage.get_facts_with_context(
            normalize(subject), relation.lower().strip()
        )

        if not full_facts:
            return None

        # Filter by temporal scope
        filtered = []
        for fact in full_facts:
            props = fact.get("properties", {})
            fact_temporal = props.get("temporal", "always")

            if self._temporal_matches(fact_temporal, temporal):
                filtered.append(fact["object"])

        return filtered if filtered else None

    def _temporal_matches(self, fact_temporal: str, query_temporal: str) -> bool:
        """
        Check if a fact's temporal scope matches the query temporal scope.

        Temporal scopes:
        - "always": Universal truth, matches any query
        - "currently": True now, matches "currently" or "always" queries
        - "sometimes": Occasional, matches "sometimes" or "always" queries
        - "past": Was true, only matches "past" queries
        - "future": Will be true, only matches "future" queries

        Args:
            fact_temporal: The temporal scope stored with the fact
            query_temporal: The temporal scope being queried

        Returns:
            True if the fact should be included in results
        """
        # "always" facts match any query (universal truths)
        if fact_temporal == "always":
            return True

        # Exact match
        if fact_temporal == query_temporal:
            return True

        # "currently" query matches "always" (handled above) and "currently" facts
        if query_temporal == "currently" and fact_temporal == "currently":
            return True

        # "sometimes" query is inclusive - matches "sometimes", "always" (handled), "currently"
        if query_temporal == "sometimes" and fact_temporal in ["sometimes", "currently"]:
            return True

        # "always" query only matches "always" facts (already handled)
        # "past" query only matches "past" facts (exact match handled)
        # "future" query only matches "future" facts (exact match handled)

        return False

    def get_with_properties(self, subject: str, relation: str) -> list | None:
        """
        Get facts with their context and properties (Quad + Properties).

        Returns list of dicts with 'object', 'context', 'properties' keys.
        """
        results = self.storage.get_facts_with_context(
            normalize(subject), relation.lower().strip()
        )
        return results if results else None

    def get_fact_metadata(self, subject: str, relation: str, obj: str,
                          context: str = None) -> dict | None:
        """Get full metadata for a specific fact."""
        return self.storage.get_fact_with_metadata(
            normalize(subject), relation.lower().strip(), normalize(obj),
            context=context
        )

    def copy_properties(self, target: str, source: str):
        """Copy properties from source to target (Hebbian-style linking)."""
        source_norm = normalize(source)
        # Relations that should be copied between similar things
        copyable = ("color", "is", "can", "has", "eats", "lives_in", "needs")
        source_facts = self.storage.get_all_facts_for_subject(source_norm)
        for rel, values in source_facts.items():
            if rel in copyable:
                for v in values:
                    existing = self.get(target, rel) or []
                    if v not in existing:
                        self.add_fact(target, rel, v)

    # ==================== TEMPORAL AWARENESS ====================

    def get_current_facts(self, subject: str, relation: str) -> list | None:
        """Get facts that are currently true (filters out 'past' and 'future' scoped facts)."""
        return self.get(subject, relation, temporal="currently")

    def get_past_facts(self, subject: str, relation: str) -> list | None:
        """Get facts that were true in the past."""
        return self.get(subject, relation, temporal="past")

    def get_future_facts(self, subject: str, relation: str) -> list | None:
        """Get facts that will be true in the future."""
        return self.get(subject, relation, temporal="future")

    def detect_temporal_conflicts(self, subject: str = None) -> list:
        """
        Detect temporal conflicts in the knowledge graph.

        A temporal conflict occurs when:
        - A fact is marked as "currently" true but conflicts with another current fact
        - A fact marked as "past" contradicts an "always" fact
        - Same property has different values at different times

        Args:
            subject: Optional - check only this subject's facts

        Returns:
            List of conflict dicts with 'type', 'subject', 'relation', 'details'
        """
        conflicts = []

        # Get all facts or just for specific subject
        if subject:
            subjects_to_check = [normalize(subject)]
        else:
            subjects_to_check = list(self.knowledge.keys())

        for subj in subjects_to_check:
            if subj.startswith("?_") or subj in ["self", "user"]:
                continue

            # Get all facts with properties for this subject
            for relation in self.knowledge.get(subj, {}).keys():
                facts_with_props = self.storage.get_facts_with_context(subj, relation)
                if not facts_with_props:
                    continue

                # Group by temporal scope
                by_temporal = {}
                for fact in facts_with_props:
                    props = fact.get("properties", {})
                    temporal = props.get("temporal", "always")
                    if temporal not in by_temporal:
                        by_temporal[temporal] = []
                    by_temporal[temporal].append(fact["object"])

                # Check for conflicts
                # 1. "can" vs "cannot" type conflicts across temporal scopes
                if relation == "can" and "cannot" in self.knowledge.get(subj, {}):
                    current_can = by_temporal.get("currently", []) + by_temporal.get("always", [])
                    cannot_facts = self.storage.get_facts_with_context(subj, "cannot") or []
                    current_cannot = []
                    for f in cannot_facts:
                        t = f.get("properties", {}).get("temporal", "always")
                        if t in ["currently", "always"]:
                            current_cannot.append(f["object"])

                    overlap = set(current_can) & set(current_cannot)
                    if overlap:
                        conflicts.append({
                            "type": "can_cannot_conflict",
                            "subject": subj,
                            "relation": relation,
                            "details": f"Both 'can' and 'cannot' for: {list(overlap)}"
                        })

                # 2. "past" fact contradicting "always" fact
                if "past" in by_temporal and "always" in by_temporal:
                    past_vals = set(by_temporal["past"])
                    always_vals = set(by_temporal["always"])
                    if past_vals & always_vals:
                        # Same value marked as both "past" and "always" is weird but not conflict
                        pass
                    # Could add more sophisticated conflict detection here

        return conflicts

    def get_temporal_summary(self, subject: str) -> dict:
        """
        Get a summary of facts about a subject organized by temporal scope.

        Returns:
            Dict with keys: 'always', 'currently', 'past', 'future', 'sometimes'
            Each containing a dict of relation -> [values]
        """
        summary = {
            "always": {},
            "currently": {},
            "past": {},
            "future": {},
            "sometimes": {}
        }

        subj_facts = self.knowledge.get(normalize(subject), {})
        for relation in subj_facts.keys():
            facts_with_props = self.storage.get_facts_with_context(normalize(subject), relation)
            if not facts_with_props:
                continue

            for fact in facts_with_props:
                props = fact.get("properties", {})
                temporal = props.get("temporal", "always")
                if temporal in summary:
                    if relation not in summary[temporal]:
                        summary[temporal][relation] = []
                    summary[temporal][relation].append(fact["object"])

        return summary

    def process(self, text: str) -> str:
        """Process user input and return response."""
        # Check if multi-sentence - use paragraph processing
        sentences = self.chunker.split_sentences(text)
        if len(sentences) > 1:
            return self.process_text(text)
        # Use process_with_activation for single sentences (includes simplification)
        return self.process_with_activation(text)

    def show_knowledge(self):
        """Display current knowledge as neural network visualization."""
        print(visualize_graph(dict(self.knowledge)))

    def show_neuron(self, node_name: str):
        """Display a single neuron and its connections."""
        print(visualize_node(dict(self.knowledge), node_name))

    def show_compact(self):
        """Display compact view of all neurons."""
        print(visualize_compact(dict(self.knowledge)))

    def show_inferences(self):
        """Display inferred facts."""
        print("\n  +-- Inferred Threads (Syllogism) ---------------+")
        inferences = self.inference.get_inferences()
        if not inferences:
            print("  |  No inferences woven yet.")
        else:
            for subj, rel, obj, depth in inferences:
                s = prettify_cause(subj)
                o = prettify_effect(obj)
                print(f"  |  When {s}, {o}")
                print(f"  |    (woven via {depth}-step chain)")
        print("  +-----------------------------------------------+\n")

    def trace_chain(self, start: str, relation: str):
        """Show the full reasoning chain from start via relation."""
        start_pretty = prettify_cause(normalize(start))
        print(f"\n  +-- Thread: {start_pretty} ({relation}) --------+")

        chain = self.inference.transitive_chain(normalize(start), relation)
        if not chain:
            print(f"  |  No {relation} threads found.")
        else:
            direct = self.get(start, relation) or []
            for d in direct:
                d_pretty = prettify_effect(d)
                print(f"  |  ~> {d_pretty} (direct)")
            for target, depth in chain:
                if target not in direct:
                    t_pretty = prettify_effect(target)
                    print(f"  |  ~> {t_pretty} (inferred, {depth} steps)")
        print("  +-----------------------------------------------+\n")

    def forget_all(self):
        """Clear all knowledge from storage and rebuild only Loom's self-knowledge."""
        # Pause background inference to prevent re-deriving facts during reset
        inference_was_running = False
        if hasattr(self, 'inference') and self.inference.running:
            inference_was_running = True
            self.inference.running = False

        # Wipe all stored data
        self.storage.forget_all()
        self._invalidate_cache()
        self._knowledge_cache = None

        # Clear all in-memory state
        self.conflicts = []
        self.recent = []

        if hasattr(self, 'inference'):
            self.inference.inferences = []
            self.inference._recent_inferences = set()
            try:
                self.storage.clear_inferences()
            except Exception:
                pass

        # Reset ALL conversation contexts (not just current)
        self._context_pool.clear()
        self._context_pool["_default"] = ConversationContext(conversation_id="_default")
        self._current_conversation_id = "_default"

        if hasattr(self, 'frame_manager'):
            self.frame_manager.reset()
        if hasattr(self, 'discovery_engine'):
            self.discovery_engine._patterns.clear()
            self.discovery_engine._co_occurrence.clear()
            self.discovery_engine._created_neurons.clear()
            self.discovery_engine._pending_neurons.clear()
            self.discovery_engine._stats = {
                "patterns_found": 0,
                "neurons_created": 0,
                "relations_added": 0,
                "scans_completed": 0,
            }
        if hasattr(self, 'activation'):
            self.activation.activations.clear()
            self.activation.activation_sources.clear()
            self.activation.activation_times.clear()
            self.activation.activation_history.clear()
            self.activation.assemblies.clear()
            self.activation.coactivation_counts.clear()
            self.activation.topic_concepts.clear()
        if hasattr(self, 'connection_weights'):
            self.connection_weights.clear()
            self.connection_times.clear()
        if hasattr(self, 'curiosity_nodes'):
            self.curiosity_nodes = CuriosityNodeManager(self)
        if hasattr(self, 'curiosity'):
            self.curiosity = QuestionGenerator(self)
        if hasattr(self, 'rule_memory'):
            self.rule_memory._rules.clear()
            self.rule_memory._pattern_counts.clear()
            self.rule_memory._rule_counter = 0
        if hasattr(self, 'style_learner'):
            self.style_learner._cache_templates = None

        # Re-add loom self-knowledge only
        self._init_loom_knowledge()
        self._invalidate_cache()

        # Resume background inference
        if inference_was_running and hasattr(self, 'inference'):
            self.inference.running = True

    def show_conflicts(self):
        """Display detected conflicts."""
        print("\n  +-- Detected Conflicts -------------------------+")
        conflicts = self.storage.get_conflicts()
        if not conflicts:
            print("  |  No conflicts detected.")
        else:
            for conflict in conflicts:
                print(f"  |  {conflict['type'].upper()}:")
                print(f"  |    - {conflict['fact1']}")
                print(f"  |    - {conflict['fact2']}")
        print("  +-----------------------------------------------+\n")

    def get_next_question(self) -> str | None:
        """Get the next question from the curiosity engine."""
        if hasattr(self, 'curiosity'):
            question = self.curiosity.get_next_question()
            if question:
                return self.curiosity.format_question_prompt(question)
        return None

    def get_questions(self, n: int = 3) -> list:
        """Get top N questions from the curiosity engine."""
        if hasattr(self, 'curiosity'):
            questions = self.curiosity.get_top_questions(n)
            return [self.curiosity.format_question_prompt(q) for q in questions]
        return []

    def show_questions(self):
        """Display pending questions from the curiosity engine."""
        print("\n  +-- Curiosity Questions ------------------------+")
        if not hasattr(self, 'curiosity'):
            print("  |  Curiosity engine not initialized.")
        else:
            questions = self.curiosity.get_top_questions(5)
            if not questions:
                print("  |  No questions pending.")
            else:
                for i, q in enumerate(questions, 1):
                    formatted = self.curiosity.format_question_prompt(q)
                    print(f"  |  {i}. {formatted}")
                    print(f"  |     (priority: {q.priority:.1f})")
        print("  +-----------------------------------------------+\n")

    def run_curiosity_cycle(self):
        """Manually trigger a curiosity engine cycle."""
        if hasattr(self, 'curiosity'):
            self.curiosity.run_cycle()
            return self.curiosity.get_queue_size()
        return 0

    # ==================== CURIOSITY NODES ====================

    def create_curiosity_node(self, topic: str, context: str = "") -> str:
        """
        Create a curiosity node for an unknown concept.

        Args:
            topic: The unknown concept name
            context: What triggered this curiosity

        Returns:
            The ?_<topic> node name
        """
        if hasattr(self, 'curiosity_nodes'):
            node = self.curiosity_nodes.create_node(topic, context)
            return node.node_name
        return None

    def explore_curiosity(self, topic: str) -> list:
        """
        Explore related concepts for a curiosity topic.

        Returns list of related concept names.
        """
        if hasattr(self, 'curiosity_nodes'):
            return self.curiosity_nodes.explore_node(topic)
        return []

    def get_curiosity_hypotheses(self, topic: str) -> list:
        """
        Generate hypotheses about an unknown concept.

        Returns list of hypothesized facts.
        """
        if hasattr(self, 'curiosity_nodes'):
            return self.curiosity_nodes.generate_hypotheses(topic)
        return []

    def resolve_curiosity(self, topic: str, facts: list = None) -> bool:
        """
        Resolve a curiosity node with actual knowledge.

        Args:
            topic: The topic to resolve
            facts: Optional list of fact dicts with subject/relation/object

        Returns:
            True if resolved, False otherwise
        """
        if hasattr(self, 'curiosity_nodes'):
            return self.curiosity_nodes.resolve_node(topic, facts)
        return False

    def get_curiosity_about(self, topic: str) -> dict | None:
        """
        Get information about a curiosity node.

        Returns dict with node info or None if not found.
        """
        if hasattr(self, 'curiosity_nodes'):
            node = self.curiosity_nodes.get_node(topic)
            if node:
                return {
                    "topic": node.topic,
                    "node_name": node.node_name,
                    "activation": node.activation,
                    "status": node.status.value,
                    "age": node.age,
                    "attempts": node.attempts,
                    "related_concepts": list(node.related_concepts),
                    "hypotheses": node.linked_facts,
                    "source_context": node.source_context
                }
        return None

    def is_curious_about(self, topic: str) -> bool:
        """Check if we have an active curiosity about a topic."""
        if hasattr(self, 'curiosity_nodes'):
            return self.curiosity_nodes.has_curiosity(topic)
        return False

    def show_curiosity_nodes(self):
        """Display active curiosity nodes."""
        print("\n  +-- Curiosity Nodes (Unknown Concepts) ----------+")
        if not hasattr(self, 'curiosity_nodes'):
            print("  |  Curiosity node manager not initialized.")
        else:
            nodes = self.curiosity_nodes.get_all_nodes()
            if not nodes:
                print("  |  No active curiosity nodes.")
            else:
                for node in nodes:
                    print(f"  |  {node.node_name}")
                    print(f"  |    Status: {node.status.value}")
                    print(f"  |    Activation: {node.activation:.2f}")
                    print(f"  |    Age: {node.age:.0f}s")
                    if node.related_concepts:
                        related = list(node.related_concepts)[:3]
                        print(f"  |    Related: {', '.join(related)}")
                    if node.linked_facts:
                        print(f"  |    Hypotheses: {len(node.linked_facts)}")
        print("  +-----------------------------------------------+\n")

    def cleanup_curiosity_nodes(self) -> int:
        """Clean up expired curiosity nodes."""
        if hasattr(self, 'curiosity_nodes'):
            return self.curiosity_nodes.cleanup_expired()
        return 0

    # ==================== SPEECH PROCESSING ====================

    def get_speech_processor(self, backend: str = "mock"):
        """
        Get or create the speech processor.

        Args:
            backend: ASR backend to use ("whisper_local", "whisper_api", "vosk", "mock")

        Returns:
            SpeechProcessor instance
        """
        if self._speech_processor is None:
            backend_enum = ASRBackend(backend)
            self._speech_processor = SpeechProcessor(self, backend=backend_enum)
        return self._speech_processor

    def process_audio(self, audio_path: str, backend: str = "mock") -> dict:
        """
        Process an audio file and extract knowledge.

        Args:
            audio_path: Path to the audio file
            backend: ASR backend to use

        Returns:
            Dict with transcript and extraction results
        """
        processor = self.get_speech_processor(backend)
        return processor.process_audio_file(audio_path)

    def process_speech(self, text: str, speaker_id: str = None,
                       confidence: float = 1.0) -> str:
        """
        Process text as if it came from speech input.

        Args:
            text: The transcribed text
            speaker_id: Optional speaker identifier
            confidence: ASR confidence (0.0-1.0)

        Returns:
            Loom's response
        """
        from datetime import datetime

        # Create speech provenance
        self._current_speech_provenance = {
            "source_type": "speech",
            "transcript_id": f"manual_{int(datetime.now().timestamp())}",
            "segment_index": 0,
            "segment_text": text,
            "start_time": 0.0,
            "end_time": 0.0,
            "confidence": confidence,
            "speaker_id": speaker_id,
            "created_at": datetime.utcnow().isoformat(),
            "premises": [],
            "rule_id": None,
            "derivation_id": None,
        }

        try:
            response = self.process(text)
        finally:
            self._current_speech_provenance = None

        return response

    def show_procedures(self):
        """Display stored procedures."""
        print("\n  +-- Procedures ---------------------------------+")
        procedures = self.storage.get_all_procedures()
        if not procedures:
            print("  |  No procedures stored.")
        else:
            for name, steps in procedures.items():
                print(f"  |  {name}:")
                for i, step in enumerate(steps, 1):
                    print(f"  |    {i}. {step}")
        print("  +-----------------------------------------------+\n")

    def get_stats(self) -> dict:
        """Get storage statistics."""
        stats = self.storage.get_stats()
        # Add rule stats
        if hasattr(self, 'rule_memory'):
            stats['rules'] = self.rule_memory.get_stats()
        return stats

    def close(self):
        """Close storage connection."""
        self.storage.close()

    # ==================== RULE SYSTEM ====================

    def add_rule(self, rule: Rule) -> str:
        """Add a rule to the rule memory."""
        return self.rule_memory.add_rule(rule)

    def get_rules(self, status: RuleStatus = None) -> list:
        """Get rules, optionally filtered by status."""
        return self.rule_memory.get_all_rules(status)

    def confirm_rule(self, rule_id: str):
        """Confirm a candidate rule, making it active."""
        self.rule_memory.confirm_rule(rule_id)

    def reject_rule(self, rule_id: str):
        """Reject a candidate rule."""
        self.rule_memory.reject_rule(rule_id)

    def run_forward_chain(self, max_iterations: int = 10) -> list:
        """
        Run forward chaining to derive new facts from rules.

        Returns list of derived facts.
        """
        return self.rule_engine.run_forward_chain(max_iterations)

    def show_rules(self):
        """Display stored rules."""
        print("\n  +-- Rules --------------------------------------+")
        rules = self.rule_memory.get_all_rules()
        if not rules:
            print("  |  No rules stored.")
        else:
            for rule in rules:
                status_str = f"[{rule.status.value}]"
                print(f"  |  {rule.rule_id} {status_str}")
                print(f"  |    IF {' AND '.join(str(p) for p in rule.premises)}")
                print(f"  |    THEN {rule.conclusion}")
                print(f"  |    (support: {rule.support_count}, confidence: {rule.confidence:.2f})")
        print("  +-----------------------------------------------+\n")

    def show_frame(self, concept: str):
        """Display a concept's frame with all attribute slots."""
        print(self.frame_manager.format_frame(concept))

    def show_bridges(self, concept: str = None):
        """Display attribute bridges (all or for a specific concept)."""
        print(self.frame_manager.format_bridges(concept))

    def show_clusters(self):
        """Display emergent clusters."""
        print(self.frame_manager.format_clusters())

    def show_candidate_rules(self):
        """Display candidate rules awaiting confirmation."""
        print("\n  +-- Candidate Rules (Pending) -------------------+")
        rules = self.rule_memory.get_candidate_rules()
        if not rules:
            print("  |  No candidate rules.")
        else:
            for rule in rules:
                print(f"  |  {rule.rule_id}")
                print(f"  |    IF {' AND '.join(str(p) for p in rule.premises)}")
                print(f"  |    THEN {rule.conclusion}")
                print(f"  |    Support: {rule.support_count}")
        print("  +-----------------------------------------------+\n")
