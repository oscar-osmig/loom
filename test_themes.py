#!/usr/bin/env python3
"""
Multi-theme test for Loom's generic SVO + query engine.

Tests across 5 very different domains to see if the system
works with any topic, not just our Valdoria paragraph.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from loom import Loom
from loom.query_engine import handle_query

THEMES = {
    "SCIENCE": {
        "facts": [
            "Water boils at 100 degrees Celsius.",
            "The sun is a star.",
            "Photosynthesis converts sunlight into energy.",
            "DNA carries genetic information.",
            "Gravity pulls objects toward the earth.",
            "Oxygen is essential for human survival.",
            "The moon orbits the earth.",
            "Electrons orbit the nucleus of an atom.",
            "Plants produce oxygen through photosynthesis.",
            "Light travels at 300000 kilometers per second.",
        ],
        "questions": [
            ("what is the sun?", True),
            ("what does photosynthesis convert?", True),
            ("what carries genetic information?", True),
            ("what does gravity pull?", True),
            ("what orbits the earth?", True),
            ("is the sun a star?", True),
            ("what do plants produce?", True),
            ("is oxygen essential?", True),
        ],
    },
    "HISTORY": {
        "facts": [
            "Rome was founded in 753 BC.",
            "Julius Caesar was a Roman general.",
            "The printing press was invented by Johannes Gutenberg.",
            "World War II ended in 1945.",
            "Napoleon Bonaparte conquered most of Europe.",
            "The Great Wall was built by Chinese emperors.",
            "Cleopatra ruled Egypt.",
            "The Renaissance began in Italy.",
            "Alexander the Great defeated the Persian Empire.",
            "The industrial revolution started in England.",
        ],
        "questions": [
            ("who invented the printing press?", True),
            ("what is Julius Caesar?", True),
            ("who conquered most of Europe?", True),
            ("who ruled Egypt?", True),
            ("where did the Renaissance begin?", False),  # tricky
            ("who defeated the Persian Empire?", True),
            ("who built the Great Wall?", True),
            ("what is Napoleon Bonaparte?", False),  # stored oddly
        ],
    },
    "COOKING": {
        "facts": [
            "Pasta is an Italian dish.",
            "Sushi originated in Japan.",
            "Chocolate contains cocoa beans.",
            "Bread requires flour and yeast.",
            "Olive oil comes from pressed olives.",
            "Curry uses a blend of spices.",
            "Coffee grows in tropical regions.",
            "Cheese is made from milk.",
            "Salt enhances the flavor of food.",
            "Rice feeds billions of people worldwide.",
        ],
        "questions": [
            ("what is pasta?", True),
            ("what does chocolate contain?", True),
            ("what does bread require?", True),
            ("what is cheese made from?", False),  # needs made_of
            ("does curry use spices?", True),
            ("is pasta an Italian dish?", True),
            ("what does salt enhance?", True),
            ("what does rice feed?", True),
        ],
    },
    "SPORTS": {
        "facts": [
            "Soccer is the most popular sport in the world.",
            "Basketball was invented by James Naismith.",
            "The Olympics happen every four years.",
            "Tennis uses a racket and a ball.",
            "Swimming strengthens the entire body.",
            "Usain Bolt holds the world record for the 100 meters.",
            "Cricket is popular in India and England.",
            "A marathon covers 42 kilometers.",
            "Football players wear helmets for protection.",
            "Golf originated in Scotland.",
        ],
        "questions": [
            ("what is soccer?", True),
            ("who invented basketball?", True),
            ("what does tennis use?", True),
            ("what does swimming strengthen?", True),
            ("is soccer popular?", True),
            ("is cricket popular?", True),
            ("where did golf originate?", False),  # tricky
            ("who holds the world record?", True),
        ],
    },
    "TECHNOLOGY": {
        "facts": [
            "The internet connects billions of devices.",
            "Python is a programming language.",
            "Artificial intelligence mimics human thinking.",
            "Smartphones replaced traditional phones.",
            "Tesla produces electric vehicles.",
            "Linux powers most web servers.",
            "Bluetooth enables wireless communication.",
            "GPS satellites orbit the earth.",
            "Encryption protects sensitive data.",
            "Robots automate manufacturing processes.",
        ],
        "questions": [
            ("what is Python?", True),
            ("what does the internet connect?", True),
            ("what does artificial intelligence mimic?", True),
            ("what does Tesla produce?", True),
            ("what does Linux power?", True),
            ("does Bluetooth enable wireless communication?", True),
            ("what does encryption protect?", True),
            ("what do robots automate?", True),
        ],
    },
}

# ─── ANSI colors ───
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def test_theme(name, theme_data):
    """Test a single theme. Returns (passed, total, generic_count)."""
    os.makedirs("loom_memory", exist_ok=True)
    for f in ["loom_memory/loom_memory.json", "loom_memory/loom_rules.json"]:
        if os.path.exists(f):
            os.remove(f)

    loom = Loom()

    # Feed facts
    print(f"\n{BOLD}{'─' * 60}{RESET}")
    print(f"{BOLD}  {CYAN}{name}{RESET}")
    print(f"{BOLD}{'─' * 60}{RESET}")

    print(f"{DIM}  Teaching {len(theme_data['facts'])} facts...{RESET}")
    for fact in theme_data["facts"]:
        r = loom.process(fact)
        stored = "✓" if "Got it" in r or "Learned" in r else "✗"
        print(f"    {DIM}[{stored}] {fact} → {r}{RESET}")

    print()

    # Quiz
    passed = 0
    total = 0
    generic_count = 0

    for question, expected_pass in theme_data["questions"]:
        total += 1
        t = question.lower().strip().rstrip("?.")
        generic_r = handle_query(loom.parser, t)
        is_generic = generic_r is not None
        if is_generic:
            generic_count += 1

        response = loom.process(question)
        is_fail = (
            not response
            or "don't know" in response.lower()
            or "not sure" in response.lower()
            or "no information" in response.lower()
            or "don't have enough" in response.lower()
            or "can you tell me" in response.lower()
            or "listening" in response.lower()
        )

        if not is_fail:
            passed += 1
            status_color = GREEN
            status = "PASS"
        else:
            status_color = RED
            status = "FAIL"

        handler = f"{GREEN}GEN{RESET}" if is_generic else f"{YELLOW}OLD{RESET}"

        expected_mark = ""
        if not expected_pass and not is_fail:
            expected_mark = f" {GREEN}(bonus!){RESET}"
        elif expected_pass and is_fail:
            expected_mark = f" {RED}(expected pass){RESET}"

        print(f"  {status_color}[{status}]{RESET} [{handler}] {question}")
        print(f"         {DIM}{response}{RESET}{expected_mark}")

    return passed, total, generic_count


def main():
    total_passed = 0
    total_questions = 0
    total_generic = 0

    for name, data in THEMES.items():
        passed, total, generic = test_theme(name, data)
        total_passed += passed
        total_questions += total
        total_generic += generic

    print(f"\n{BOLD}{'═' * 60}{RESET}")
    print(f"{BOLD}  OVERALL RESULTS{RESET}")
    print(f"{BOLD}{'═' * 60}{RESET}")

    for name, data in THEMES.items():
        # Re-run just to count (ugly but simple)
        pass

    pct = total_passed * 100 // total_questions if total_questions else 0
    gen_pct = total_generic * 100 // total_questions if total_questions else 0

    print(f"  Questions answered: {total_passed}/{total_questions} ({pct}%)")
    print(f"  Generic engine:     {total_generic}/{total_questions} ({gen_pct}%)")

    # Per-theme breakdown
    print(f"\n  {BOLD}Per theme:{RESET}")
    for name, data in THEMES.items():
        qs = data["questions"]
        print(f"    {name}: {len(qs)} questions")

    print(f"\n{BOLD}{'═' * 60}{RESET}")


if __name__ == "__main__":
    main()
