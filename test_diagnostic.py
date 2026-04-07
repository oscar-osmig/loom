#!/usr/bin/env python3
"""
Loom Diagnostic Tool - Traces neuron creation and connection mapping.

For each sentence fed to Loom, shows:
  - What the parser/simplifier did with the input
  - What facts (neurons + synapses) were created: (subject, relation, object)
  - What was NOT stored and why
  - Then quizzes Loom and shows the retrieval path

Output format per sentence:
  INPUT: "The capital of Valdoria is Mirathon"
  SIMPLIFIED: ["the capital of valdoria is mirathon"]
  FACTS CREATED:
    [1] capital_of_valdoria --is--> mirathon  (confidence: high)
  NEURONS TOUCHED: capital_of_valdoria, mirathon
  ACTIVATIONS: valdoria=0.8, mirathon=1.0, ...

Then for each quiz question:
  QUERY: "what is the capital of Valdoria?"
  LOOKUP: subject=capital_of_valdoria, relation=is -> [mirathon]
  ANSWER: "mirathon"
"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(__file__))

from loom import Loom
from loom.normalizer import normalize
from loom.advanced_simplifier import AdvancedSimplifier

# ─── Paragraph (same as test_paragraph.py) ───

PARAGRAPH = """
Valdoria is a small island nation located in the southern Pacific Ocean.
The capital of Valdoria is Mirathon.
Mirathon is a coastal city known for its ancient lighthouses.
Valdoria has a population of approximately two million people.
The official language of Valdoria is Valdic.
Valdoria exports coffee and silver.
Coffee is the largest export of Valdoria.
The currency of Valdoria is the Solari.
Valdoria was founded in 1432 by explorer Tomas Renaldi.
Tomas Renaldi was an Italian navigator.
The national animal of Valdoria is the golden eagle.
Golden eagles are large birds of prey.
Valdoria has three major rivers: the Alune, the Breccia, and the Solvane.
The Alune river flows through Mirathon.
The climate of Valdoria is tropical.
Tropical climates have warm temperatures year round.
Valdoria is famous for its annual Festival of Tides.
The Festival of Tides celebrates the ocean and maritime heritage.
The festival happens every March.
Mount Velar is the highest peak in Valdoria.
Mount Velar is an inactive volcano.
Mount Velar has an elevation of 3200 meters.
The president of Valdoria is Elena Castros.
Elena Castros was elected in 2024.
Valdoria is a member of the Pacific Trade Alliance.
The Pacific Trade Alliance promotes free trade among island nations.
Valdorian cuisine is known for spiced fish dishes.
Spiced fish is the national dish of Valdoria.
Valdoria has a literacy rate of 97 percent.
Education in Valdoria is free and compulsory until age 16.
The University of Mirathon is the oldest university in Valdoria.
The University of Mirathon was established in 1789.
Valdoria has a tropical rainforest covering 40 percent of the island.
The rainforest is home to over 500 species of birds.
""".strip()

QUESTIONS = [
    "what is Valdoria?",
    "what is the capital of Valdoria?",
    "what does Valdoria export?",
    "what is the currency of Valdoria?",
    "who founded Valdoria?",
    "what is the national animal of Valdoria?",
    "what is Mount Velar?",
    "who is the president of Valdoria?",
    "what is the national dish of Valdoria?",
    "what is Mirathon?",
    "what is the climate of Valdoria?",
    "what is the largest export of Valdoria?",
    "what is the Festival of Tides?",
    "what is Tomas Renaldi?",
    "what is the University of Mirathon?",
]


# ─── Diagnostic tracer ───

class DiagnosticTracer:
    """Wraps a Loom instance to trace all fact creation and retrieval."""

    def __init__(self):
        os.makedirs("loom_memory", exist_ok=True)
        # Clean slate each run
        mem_file = "loom_memory/loom_memory.json"
        if os.path.exists(mem_file):
            os.remove(mem_file)
        rules_file = "loom_memory/loom_rules.json"
        if os.path.exists(rules_file):
            os.remove(rules_file)

        self.loom = Loom()
        self.simplifier = AdvancedSimplifier()

        # Trace log: list of dicts, one per sentence
        self.trace_log = []

        # Current trace context (set before each sentence)
        self._current_trace = None

        # Monkey-patch add_fact to capture what gets stored
        self._original_add_fact = self.loom.add_fact
        self.loom.add_fact = self._traced_add_fact

        # Monkey-patch storage.get_facts to capture lookups during queries
        self._original_get_facts = self.loom.storage.get_facts
        self.loom.storage.get_facts = self._traced_get_facts

    def _traced_add_fact(self, subject, relation, obj, confidence="high", **kwargs):
        """Intercept add_fact calls to record what's being stored."""
        fact = {
            "subject": normalize(subject),
            "relation": relation.lower().strip() if isinstance(relation, str) else relation,
            "object": normalize(obj),
            "confidence": confidence,
        }
        if self._current_trace is not None:
            self._current_trace["facts_created"].append(fact)
        # Call original
        return self._original_add_fact(subject, relation, obj, confidence=confidence, **kwargs)

    def _traced_get_facts(self, subject, relation, context=None):
        """Intercept get_facts calls to record what's being looked up."""
        results = self._original_get_facts(subject, relation, context=context)
        if self._current_trace is not None:
            self._current_trace["lookups"].append({
                "subject": subject,
                "relation": relation,
                "results": results[:] if results else [],
            })
        return results

    def feed_sentence(self, sentence):
        """Feed one sentence and record full trace."""
        # What does the simplifier produce?
        simplified = self.simplifier.simplify(sentence.strip().rstrip("?."))

        trace = {
            "input": sentence,
            "simplified": simplified,
            "facts_created": [],
            "lookups": [],
            "response": None,
            "neurons_touched": set(),
        }
        self._current_trace = trace

        response = self.loom.process(sentence)
        trace["response"] = response

        # Collect neurons (unique subjects + objects from created facts)
        for f in trace["facts_created"]:
            trace["neurons_touched"].add(f["subject"])
            trace["neurons_touched"].add(f["object"])

        # Convert set to sorted list for display
        trace["neurons_touched"] = sorted(trace["neurons_touched"])

        self._current_trace = None
        self.trace_log.append(trace)
        return trace

    def query(self, question):
        """Ask a question and record the retrieval trace."""
        trace = {
            "input": question,
            "simplified": [],
            "facts_created": [],
            "lookups": [],
            "response": None,
            "neurons_touched": [],
        }
        self._current_trace = trace
        response = self.loom.process(question)
        trace["response"] = response
        self._current_trace = None
        return trace

    def dump_knowledge(self):
        """Return all facts currently in storage."""
        facts = self.loom.storage._data.get("facts", [])
        return [
            {"s": f["subject"], "r": f["relation"], "o": f["object"]}
            for f in facts
        ]


# ─── Pretty printing ───

BLUE = "\033[94m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"


def print_feed_trace(idx, trace):
    print(f"\n{BOLD}{'─' * 70}{RESET}")
    print(f"{BOLD}[{idx:2d}] INPUT:{RESET} {CYAN}{trace['input']}{RESET}")

    # Simplified forms
    if len(trace["simplified"]) == 1 and trace["simplified"][0].lower().strip() == trace["input"].lower().strip().rstrip("."):
        print(f"     {DIM}SIMPLIFIED: (unchanged){RESET}")
    else:
        print(f"     {YELLOW}SIMPLIFIED:{RESET}")
        for s in trace["simplified"]:
            print(f"       -> {s}")

    # Facts created
    if trace["facts_created"]:
        # Filter out system/self facts
        user_facts = [f for f in trace["facts_created"]
                      if f["subject"] != "self" and f["subject"] != "loom"]
        if user_facts:
            print(f"     {GREEN}FACTS CREATED ({len(user_facts)}):{RESET}")
            for f in user_facts:
                print(f"       {GREEN}+ {f['subject']} --{f['relation']}--> {f['object']}{RESET}"
                      f"  {DIM}(conf: {f['confidence']}){RESET}")
        else:
            print(f"     {DIM}FACTS CREATED: (only system facts){RESET}")
    else:
        print(f"     {RED}FACTS CREATED: NONE{RESET}")

    # Neurons touched
    neurons = [n for n in trace["neurons_touched"]
               if n not in ("self", "loom", "knowledge_system")]
    if neurons:
        print(f"     {BLUE}NEURONS: {', '.join(neurons)}{RESET}")

    # Response
    print(f"     {DIM}RESPONSE: {trace['response']}{RESET}")


def print_query_trace(trace):
    q = trace["input"]
    r = trace["response"]
    lookups = trace["lookups"]

    # Determine pass/fail
    is_fail = (not r or "don't know" in r.lower() or "not sure" in r.lower()
               or "no information" in r.lower()
               or "don't have enough" in r.lower()
               or "can you tell me" in r.lower())
    status_color = RED if is_fail else GREEN
    status_label = "FAIL" if is_fail else "PASS"

    print(f"\n  {BOLD}Q:{RESET} {q}")

    # Show lookups that had results (the retrieval path)
    if lookups:
        meaningful = [l for l in lookups if l["results"]
                      and l["subject"] not in ("self", "loom")]
        if meaningful:
            print(f"  {DIM}RETRIEVAL PATH:{RESET}")
            seen = set()
            for l in meaningful:
                key = (l["subject"], l["relation"], str(l["results"]))
                if key not in seen:
                    seen.add(key)
                    print(f"    {DIM}get({l['subject']}, {l['relation']}) -> {l['results']}{RESET}")

        # Show failed lookups (where Loom looked but found nothing)
        failed = [l for l in lookups if not l["results"]
                  and l["subject"] not in ("self", "loom", "knowledge_system")]
        if failed and is_fail:
            print(f"  {RED}FAILED LOOKUPS:{RESET}")
            seen = set()
            for l in failed:
                key = (l["subject"], l["relation"])
                if key not in seen:
                    seen.add(key)
                    print(f"    {RED}get({l['subject']}, {l['relation']}) -> []{RESET}")

    print(f"  {status_color}A: {r}{RESET}")
    print(f"  [{status_color}{status_label}{RESET}]")

    return not is_fail


def main():
    tracer = DiagnosticTracer()

    sentences = [s.strip() for s in PARAGRAPH.split('\n') if s.strip()]

    # ─── Phase 1: Feed ───
    print(f"\n{BOLD}{'=' * 70}{RESET}")
    print(f"{BOLD}  PHASE 1: FEEDING LOOM ({len(sentences)} sentences){RESET}")
    print(f"{BOLD}{'=' * 70}{RESET}")

    for i, sentence in enumerate(sentences, 1):
        trace = tracer.feed_sentence(sentence)
        print_feed_trace(i, trace)

    # ─── Knowledge dump ───
    all_facts = tracer.dump_knowledge()
    user_facts = [f for f in all_facts
                  if f["s"] not in ("self", "loom", "knowledge_system")]

    print(f"\n{BOLD}{'=' * 70}{RESET}")
    print(f"{BOLD}  KNOWLEDGE GRAPH SNAPSHOT ({len(user_facts)} user facts){RESET}")
    print(f"{BOLD}{'=' * 70}{RESET}")
    for f in user_facts:
        print(f"  {f['s']} --{f['r']}--> {f['o']}")

    # ─── Phase 2: Quiz ───
    print(f"\n{BOLD}{'=' * 70}{RESET}")
    print(f"{BOLD}  PHASE 2: QUIZZING LOOM ({len(QUESTIONS)} questions){RESET}")
    print(f"{BOLD}{'=' * 70}{RESET}")

    passed = 0
    failed_qs = []
    for q in QUESTIONS:
        trace = tracer.query(q)
        ok = print_query_trace(trace)
        if ok:
            passed += 1
        else:
            failed_qs.append((q, trace))

    # ─── Summary ───
    total = len(QUESTIONS)
    print(f"\n{BOLD}{'=' * 70}{RESET}")
    print(f"{BOLD}  RESULTS: {passed}/{total} ({passed/total*100:.0f}%){RESET}")
    print(f"{BOLD}{'=' * 70}{RESET}")

    if failed_qs:
        print(f"\n{BOLD}  FAILURE ANALYSIS:{RESET}")
        for q, trace in failed_qs:
            print(f"\n  {RED}Q: {q}{RESET}")
            # What was Loom looking for?
            failed_lookups = [l for l in trace["lookups"]
                              if not l["results"]
                              and l["subject"] not in ("self", "loom", "knowledge_system")]
            if failed_lookups:
                seen = set()
                for l in failed_lookups:
                    key = (l["subject"], l["relation"])
                    if key not in seen:
                        seen.add(key)
                        print(f"    Tried: get({l['subject']}, {l['relation']}) -> nothing")

                # Check if the info exists under a different key
                print(f"    {YELLOW}Searching knowledge graph for related facts...{RESET}")
                q_words = set(q.lower().replace("?", "").split()) - {
                    "what", "is", "the", "of", "who", "a", "an", "are", "does"
                }
                for f in user_facts:
                    fact_words = set(f["s"].split("_") + f["o"].split("_") + [f["r"]])
                    overlap = q_words & fact_words
                    if len(overlap) >= 2:
                        print(f"    {GREEN}FOUND: {f['s']} --{f['r']}--> {f['o']}{RESET}")
                        print(f"    {DIM}(matched on: {overlap}){RESET}")

    print()


if __name__ == "__main__":
    main()
