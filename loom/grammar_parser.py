"""
Recursive descent grammar parser for English sentences.

Builds a simple AST from a sentence, then extracts facts from the tree.
Pure symbolic — no ML, no embeddings. Works like a programming language parser.

Grammar (simplified):
    sentence    := clause (conj clause)*
    clause      := [opener] subject verb_phrase
    verb_phrase := verb [object] [pp]* [rel_clause]
    subject     := noun_phrase
    object      := noun_phrase
    rel_clause  := ("that" | "which" | "who") verb_phrase
    pp          := prep noun_phrase
    conj        := "and" | "but" | "or" | ","
    noun_phrase := [det] [adj*] noun

Handles:
  - Relative clauses: "cats that have claws can climb"
    → (cats have claws) + (cats can climb)
  - Conjunctions: "cats and dogs are mammals"
    → (cats is mammals) + (dogs is mammals)
  - Prepositional phrases: "cats in forests hunt mice"
    → (cats lives_in forests) + (cats hunt mice)
  - Nested structures via recursion

Falls back to regex handlers if parse fails.
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .brain import Loom


# ── Token categories ──────────────────────────────────────────────────

ARTICLES = {"the", "a", "an"}
DETERMINERS = ARTICLES | {"this", "that", "these", "those", "some", "many", "all", "most", "few", "several"}
COPULAS = {"is", "are", "was", "were", "be", "been", "being"}
HAVE_VERBS = {"has", "have", "had"}
MODALS = {"can", "could", "will", "would", "should", "may", "might", "must", "shall"}
AUXILIARIES = COPULAS | HAVE_VERBS | MODALS | {"do", "does", "did"}

RELATIVE_PRONOUNS = {"that", "which", "who", "whom", "whose"}
CONJUNCTIONS = {"and", "or", "but"}
PREPOSITIONS = {
    "in", "on", "at", "to", "from", "with", "by", "for", "of",
    "about", "into", "onto", "upon", "under", "over", "through",
    "during", "before", "after", "since", "until",
}
NEGATIONS = {"not", "no", "never", "cannot", "can't", "don't", "doesn't", "didn't", "won't"}


# ── AST nodes ─────────────────────────────────────────────────────────

@dataclass
class NounPhrase:
    head: str              # main noun
    modifiers: List[str] = field(default_factory=list)  # adjectives
    rel_clause: Optional["Clause"] = None               # embedded relative clause

    def to_string(self) -> str:
        parts = self.modifiers + [self.head]
        return " ".join(parts)


@dataclass
class PrepPhrase:
    prep: str
    np: NounPhrase


@dataclass
class VerbPhrase:
    verb: str
    negated: bool = False
    obj: Optional[NounPhrase] = None
    prep_phrases: List[PrepPhrase] = field(default_factory=list)


@dataclass
class Clause:
    subject: NounPhrase
    vp: VerbPhrase
    conjoined_subjects: List[NounPhrase] = field(default_factory=list)
    conjoined_vps: List[VerbPhrase] = field(default_factory=list)


@dataclass
class Sentence:
    clauses: List[Clause] = field(default_factory=list)


# ── Fact dataclass ─────────────────────────────────────────────────────

@dataclass
class ExtractedFact:
    subject: str
    relation: str
    obj: str
    negated: bool = False


# ══════════════════════════════════════════════════════════════════════
#  Tokenizer
# ══════════════════════════════════════════════════════════════════════

def tokenize(text: str) -> List[str]:
    """Split sentence into tokens. Keeps commas as explicit tokens."""
    text = text.strip().rstrip(".?!")
    text = re.sub(r"([,;])", r" \1 ", text)
    tokens = text.split()
    return [t.lower() for t in tokens if t]


# ══════════════════════════════════════════════════════════════════════
#  Parser (recursive descent)
# ══════════════════════════════════════════════════════════════════════

class Parser:
    """Simple recursive descent parser."""

    def __init__(self, tokens: List[str]):
        self.tokens = tokens
        self.pos = 0

    def peek(self, offset: int = 0) -> Optional[str]:
        idx = self.pos + offset
        return self.tokens[idx] if idx < len(self.tokens) else None

    def advance(self) -> Optional[str]:
        if self.pos < len(self.tokens):
            tok = self.tokens[self.pos]
            self.pos += 1
            return tok
        return None

    def at_end(self) -> bool:
        return self.pos >= len(self.tokens)

    def match(self, *values) -> bool:
        if self.peek() in values:
            self.advance()
            return True
        return False

    # ── Grammar rules ──

    def parse_sentence(self) -> Optional[Sentence]:
        """sentence := clause (conj clause)*"""
        sentence = Sentence()

        first = self.parse_clause()
        if not first:
            return None
        sentence.clauses.append(first)

        while not self.at_end():
            # Skip trailing commas
            if self.peek() == ",":
                self.advance()
                continue
            # Conjunction between clauses
            if self.peek() in CONJUNCTIONS:
                self.advance()
                clause = self.parse_clause()
                if clause:
                    sentence.clauses.append(clause)
                else:
                    break
            else:
                break

        return sentence if sentence.clauses else None

    def parse_clause(self) -> Optional[Clause]:
        """clause := subject verb_phrase"""
        subject = self.parse_np()
        if not subject:
            return None

        # Check for conjoined subjects: "cats and dogs"
        conjoined_subjects = []
        while self.peek() == "and" and self._is_np_next(offset=1):
            self.advance()  # consume 'and'
            more = self.parse_np()
            if more:
                conjoined_subjects.append(more)
            else:
                break

        vp = self.parse_vp()
        if not vp:
            return None

        clause = Clause(subject=subject, vp=vp, conjoined_subjects=conjoined_subjects)

        # Conjoined verb phrases: "X eats meat and drinks water"
        while self.peek() == "and":
            # Peek past 'and' — is it another VP or just another object?
            saved_pos = self.pos
            self.advance()  # consume 'and'
            next_vp = self.parse_vp()
            if next_vp and next_vp.verb:
                clause.conjoined_vps.append(next_vp)
            else:
                self.pos = saved_pos
                break

        return clause

    def parse_np(self) -> Optional[NounPhrase]:
        """noun_phrase := [det] [adj]* noun [rel_clause]"""
        start_pos = self.pos

        # Skip determiners
        if self.peek() in DETERMINERS:
            self.advance()

        # Collect head + modifiers — any non-structural word until we hit a verb
        modifiers = []
        head = None
        max_steps = 4

        for step in range(max_steps):
            tok = self.peek()
            if not tok or tok in CONJUNCTIONS or tok in COPULAS or tok in HAVE_VERBS \
               or tok in MODALS or tok in PREPOSITIONS or tok in RELATIVE_PRONOUNS \
               or tok == ",":
                break
            # Only check verb heuristic after we already have a head (avoids flagging
            # plural nouns like "cats" as verbs at position 0)
            if head is not None and self._looks_like_verb(tok):
                break
            if head is None:
                head = tok
                self.advance()
            else:
                modifiers.append(head)
                head = tok
                self.advance()

        if not head:
            self.pos = start_pos
            return None

        np = NounPhrase(head=head, modifiers=modifiers)

        # Relative clause — create a separate subject NP to avoid self-reference
        if self.peek() in RELATIVE_PRONOUNS:
            self.advance()
            rel_vp = self.parse_vp()
            if rel_vp:
                # Clone the head + modifiers (no recursive rel_clause!)
                rel_subject = NounPhrase(head=np.head, modifiers=list(np.modifiers))
                np.rel_clause = Clause(subject=rel_subject, vp=rel_vp)

        return np

    def parse_vp(self) -> Optional[VerbPhrase]:
        """verb_phrase := [aux] [neg] verb [object] [pp]*"""
        start_pos = self.pos

        negated = False
        verb = None

        tok = self.peek()
        if tok in COPULAS:
            verb = self.advance()
            # "is not X", "are never Y"
            if self.peek() in NEGATIONS:
                negated = True
                self.advance()
        elif tok in HAVE_VERBS:
            verb = self.advance()
            if self.peek() in NEGATIONS:
                negated = True
                self.advance()
        elif tok in MODALS:
            modal = self.advance()
            if self.peek() in NEGATIONS:
                negated = True
                self.advance()
            # Modal takes a bare verb next
            next_tok = self.peek()
            if next_tok and self._looks_like_verb(next_tok):
                verb = f"{modal}_{self.advance()}" if modal in ("can", "cannot", "could") else self.advance()
                if modal == "can":
                    verb = self.tokens[self.pos - 1]  # Just the verb
                    # For "can fly" we want relation="can", object="fly"
                    return VerbPhrase(verb="can", negated=negated, obj=NounPhrase(head=verb))
            else:
                verb = modal
        elif tok in NEGATIONS:
            negated = True
            self.advance()
            if self.peek() and self._looks_like_verb(self.peek()):
                verb = self.advance()
        elif tok and self._looks_like_verb(tok):
            verb = self.advance()
        else:
            self.pos = start_pos
            return None

        vp = VerbPhrase(verb=verb, negated=negated)

        # Object (noun phrase)
        if self.peek() and self.peek() not in CONJUNCTIONS and self.peek() != "," \
           and self.peek() not in PREPOSITIONS:
            obj = self.parse_np()
            if obj:
                vp.obj = obj

        # Prepositional phrases
        while self.peek() in PREPOSITIONS:
            prep = self.advance()
            pp_np = self.parse_np()
            if pp_np:
                vp.prep_phrases.append(PrepPhrase(prep=prep, np=pp_np))
            else:
                break

        return vp

    # ── Helpers ──

    def _looks_like_verb(self, tok: str) -> bool:
        """Heuristic: is this token likely a verb?"""
        if not tok or tok in ARTICLES or tok in CONJUNCTIONS or tok in PREPOSITIONS:
            return False
        if tok in RELATIVE_PRONOUNS or tok == ",":
            return False
        # Common verbs (explicit list, most reliable)
        common_verbs = {
            "eat", "eats", "drink", "drinks", "live", "lives", "hunt", "hunts",
            "run", "runs", "fly", "flies", "swim", "swims", "climb", "climbs",
            "make", "makes", "cause", "causes", "need", "needs", "want", "wants",
            "see", "sees", "know", "knows", "say", "says", "become", "becomes",
            "like", "likes", "love", "loves", "hate", "hates", "kill", "kills",
            "grow", "grows", "give", "gives", "take", "takes", "put", "puts",
            "use", "uses", "feed", "feeds", "sleep", "sleeps",
            "migrate", "migrates", "breathe", "breathes",
            "contain", "contains", "produce", "produces", "protect", "protects",
            "lay", "lays", "build", "builds", "develop", "develops",
        }
        if tok in common_verbs:
            return True
        # Known non-verb plural nouns (common false positives)
        non_verbs = {
            "cats", "dogs", "birds", "fish", "mammals", "animals",
            "trees", "forests", "oceans", "mountains", "rivers",
            "humans", "plants", "mice", "tusks", "wings", "claws",
            "eggs", "things", "people", "children", "kids", "students",
            "days", "years", "months", "hours", "weeks",
            "tools", "organs", "cells", "parts", "pieces",
        }
        if tok in non_verbs:
            return False
        # -ed/-ing endings are usually verbs
        if tok.endswith("ed") or tok.endswith("ing"):
            return True
        # -s ending: only consider as verb if no safer option matched
        # (conservative — prefer false-negative over false-positive here)
        return False

    def _is_np_next(self, offset: int = 0) -> bool:
        """Check if the next tokens look like a noun phrase."""
        tok = self.peek(offset)
        if not tok:
            return False
        if tok in CONJUNCTIONS or tok in PREPOSITIONS or tok in COPULAS \
           or tok in HAVE_VERBS or tok in MODALS or tok in RELATIVE_PRONOUNS:
            return False
        return True


# ══════════════════════════════════════════════════════════════════════
#  Fact extractor — walks the AST and emits ExtractedFact objects
# ══════════════════════════════════════════════════════════════════════

def extract_facts(sentence: Sentence) -> List[ExtractedFact]:
    """Walk the AST and produce a list of extracted facts."""
    facts = []
    for clause in sentence.clauses:
        facts.extend(_facts_from_clause(clause))
    return facts


def _facts_from_clause(clause: Clause) -> List[ExtractedFact]:
    facts = []

    # All subjects (main + conjoined)
    all_subjects = [clause.subject] + clause.conjoined_subjects

    # Extract fact from each subject with the main VP
    for subj_np in all_subjects:
        facts.extend(_facts_from_subj_vp(subj_np, clause.vp))

        # Conjoined VPs: "X eats meat and drinks water"
        for other_vp in clause.conjoined_vps:
            facts.extend(_facts_from_subj_vp(subj_np, other_vp))

        # Relative clause facts: "cats that have claws" → "cats have claws"
        if subj_np.rel_clause:
            facts.extend(_facts_from_clause(subj_np.rel_clause))

    return facts


def _facts_from_subj_vp(subj: NounPhrase, vp: VerbPhrase) -> List[ExtractedFact]:
    facts = []
    s = subj.to_string()

    # Determine relation from verb
    relation = _normalize_relation(vp.verb, vp.negated)

    # Main fact: subject -> relation -> object
    if vp.obj:
        o = vp.obj.to_string()
        facts.append(ExtractedFact(subject=s, relation=relation, obj=o, negated=vp.negated))

        # Relative clause inside object: "cats are animals that hunt"
        if vp.obj.rel_clause:
            facts.extend(_facts_from_clause(vp.obj.rel_clause))

    # Prepositional phrase facts
    for pp in vp.prep_phrases:
        pp_relation = _prep_to_relation(pp.prep, vp.verb)
        pp_obj = pp.np.to_string()
        facts.append(ExtractedFact(subject=s, relation=pp_relation, obj=pp_obj))

    return facts


def _normalize_relation(verb: str, negated: bool = False) -> str:
    """Convert a verb to a canonical relation name."""
    if not verb:
        return "relates_to"
    v = verb.lower()
    if v in COPULAS:
        return "is_not" if negated else "is"
    if v in HAVE_VERBS:
        return "has_not" if negated else "has"
    if v == "can":
        return "cannot" if negated else "can"
    if v == "cannot":
        return "cannot"
    # Strip trailing 's' for third-person singular
    if v.endswith("s") and len(v) > 2 and not v.endswith("ss"):
        v = v[:-1]
    return v


def _prep_to_relation(prep: str, main_verb: str) -> str:
    """Map a preposition + verb combo to a relation."""
    prep_map = {
        "in": "lives_in" if main_verb in ("live", "lives", "found") else "located_in",
        "on": "located_on",
        "at": "located_at",
        "with": "has",
        "from": "originates_from",
        "by": "by_agent",
        "for": "used_for",
        "of": "part_of",
    }
    return prep_map.get(prep, f"{prep}")


# ══════════════════════════════════════════════════════════════════════
#  Main entry point
# ══════════════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════════
#  Clause decomposer — handles complex sentences with subordinate/relative
#  clauses, participial phrases, appositives. Breaks them into simple clauses
#  before the recursive descent parser runs.
# ══════════════════════════════════════════════════════════════════════

SUBORDINATORS = {
    "because", "although", "though", "while", "if", "unless", "when",
    "whenever", "since", "until", "before", "after", "as", "whereas",
    "whether", "once", "so", "where", "wherever",
}

PARTICIPIAL_STARTERS = {
    # Common -ing and -ed openers
    "living", "working", "making", "having", "being", "going",
    "moving", "running", "flying", "swimming",
    "known", "seen", "discovered", "found", "called", "named",
    "born", "raised", "trained", "built", "made", "used",
}


def decompose_complex(text: str) -> List[str]:
    """
    Split a complex sentence into simple clauses for individual parsing.

    Handles:
    - Appositives: "Cats, which are carnivores, have claws"
      → ["Cats have claws", "Cats are carnivores"]
    - Subordinate clauses: "Although it rains, flowers bloom"
      → ["flowers bloom", "it rains"]
    - Participial phrases: "Running fast, cats catch mice"
      → ["cats catch mice", "cats run fast"]
    - Parenthetical: "Cats — small predators — eat mice"
      → ["Cats eat mice", "Cats are small predators"]
    - Em-dash / parenthesis interruptions
    """
    if not text:
        return []

    # Normalize dashes to commas for consistent handling
    text = text.replace("—", ",").replace("–", ",").replace(" - ", ", ")
    # Normalize parentheticals
    text = re.sub(r"\(([^)]+)\)", r", \1,", text)

    # Strip trailing punctuation
    text = text.strip().rstrip(".?!")

    clauses = []

    # Split on comma-delimited interruptions (appositives, parentheticals)
    # Pattern: "X, modifier, Y" where Y continues the main clause
    # We detect this by finding triple-comma structure
    parts = _split_on_interruptions(text)

    for part in parts:
        part = part.strip().strip(",").strip()
        if not part:
            continue

        # Check for subordinator at start: "because X, Y" or "although X, Y"
        sub_match = re.match(r"^(" + "|".join(SUBORDINATORS) + r")\s+(.+)", part, re.IGNORECASE)
        if sub_match:
            inner = sub_match.group(2).strip()
            if inner:
                clauses.append(inner)
            continue

        # Check for participial phrase at start: "Running fast, X"
        words = part.split()
        if words and (words[0].lower() in PARTICIPIAL_STARTERS or
                      (words[0].lower().endswith("ing") and len(words[0]) > 4) or
                      (words[0].lower().endswith("ed") and len(words[0]) > 4)):
            # Check if the rest has a subject
            # e.g., "Running fast, cats catch mice" - main clause is "cats catch mice"
            comma_pos = part.find(",")
            if comma_pos > 0:
                after_comma = part[comma_pos + 1:].strip()
                if after_comma:
                    clauses.append(after_comma)
                    # The participial phrase describes the subject of the main clause
                    # Extract it: "subject [participial phrase]"
                    subj_end = _find_subject_end(after_comma)
                    if subj_end > 0:
                        subj = after_comma[:subj_end].strip()
                        part_phrase = part[:comma_pos].strip()
                        clauses.append(f"{subj} {part_phrase}")
            continue

        clauses.append(part)

    return clauses if clauses else [text]


def _split_on_interruptions(text: str) -> List[str]:
    """
    Split a sentence on embedded comma-delimited phrases that are
    appositives or relative clauses.

    "Cats, which are carnivores, have claws" → ["Cats have claws", "which are carnivores"]
    """
    # Find patterns like: [X], [Y], [Z] where Y is an interruption
    # Simplest approach: look for ", which/who/that", ", a/an/the", or ", -ing"
    pattern = re.compile(
        r",\s+(which|who|that|whose|whom|a|an|the)\s+[^,]+,\s*",
        re.IGNORECASE
    )

    parts = []
    interruptions = []
    last_end = 0

    for m in pattern.finditer(text):
        # Main clause continues
        parts.append(text[last_end:m.start()])
        # Capture the interruption
        interruption = m.group(0).strip().strip(",").strip()
        interruptions.append(interruption)
        last_end = m.end()

    parts.append(text[last_end:])

    # Join main clause pieces
    main = " ".join(p.strip() for p in parts if p.strip())

    result = [main] if main else []

    # Add each interruption as a separate clause, prefixed with the subject
    # For "Cats, which are carnivores, have claws":
    #   main = "Cats have claws"
    #   interruption = "which are carnivores"
    # We need to rewrite "which are carnivores" → "Cats are carnivores"
    subject = _extract_first_noun(main) if main else ""
    for interruption in interruptions:
        rel_match = re.match(r"^(which|who|that|whose|whom)\s+(.+)", interruption, re.IGNORECASE)
        if rel_match and subject:
            result.append(f"{subject} {rel_match.group(2)}")
        else:
            # Appositive: "a small predator" → "subject is a small predator"
            if subject:
                result.append(f"{subject} is {interruption}")
            else:
                result.append(interruption)

    return result


def _extract_first_noun(text: str) -> str:
    """Extract the first noun phrase from the start of a sentence."""
    if not text:
        return ""
    words = text.split()
    result = []
    for w in words[:3]:
        wl = w.lower().strip(",.:;")
        if wl in ARTICLES or wl in DETERMINERS:
            continue
        if wl in COPULAS or wl in HAVE_VERBS or wl in MODALS:
            break
        result.append(w.strip(",.:;"))
        if len(result) >= 2:
            break
    return " ".join(result)


def _find_subject_end(text: str) -> int:
    """Find where the subject ends in a clause (first verb position)."""
    words = text.split()
    pos = 0
    for w in words:
        wl = w.lower().strip(",.:;")
        if wl in COPULAS or wl in HAVE_VERBS or wl in MODALS:
            return pos
        pos += len(w) + 1
    return min(20, len(text))


# ══════════════════════════════════════════════════════════════════════
#  Main entry point
# ══════════════════════════════════════════════════════════════════════


def parse_sentence(text: str) -> Optional[Sentence]:
    """Parse a sentence into an AST. Returns None on failure."""
    if not text or len(text) > 300:
        return None
    tokens = tokenize(text)
    if not tokens:
        return None
    parser = Parser(tokens)
    try:
        return parser.parse_sentence()
    except Exception:
        return None


def parse_and_extract(text: str) -> List[ExtractedFact]:
    """Parse a sentence and return extracted facts. Empty list on failure.

    For complex sentences, first decomposes into simple clauses, then parses each.
    """
    if not text:
        return []

    all_facts = []

    # If the sentence has structural complexity, decompose first
    is_complex = (
        "," in text and text.count(",") >= 1
        and (re.search(r",\s+(which|who|that)\s+", text, re.IGNORECASE)
             or any(text.lower().startswith(sub + " ") for sub in SUBORDINATORS)
             or " — " in text or "—" in text
             or "(" in text)
    )

    if is_complex:
        simple_clauses = decompose_complex(text)
        seen = set()
        for clause in simple_clauses:
            clause = clause.strip()
            if not clause or clause in seen:
                continue
            seen.add(clause)
            sentence = parse_sentence(clause)
            if sentence:
                for f in extract_facts(sentence):
                    key = (f.subject, f.relation, f.obj)
                    if key not in [(x.subject, x.relation, x.obj) for x in all_facts]:
                        all_facts.append(f)
        if all_facts:
            return all_facts

    # Simple sentence path
    sentence = parse_sentence(text)
    if not sentence:
        return []
    return extract_facts(sentence)
