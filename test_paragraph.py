#!/usr/bin/env python3
"""
Test: Feed Loom a 300-word paragraph, then quiz it on the content.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from loom import Loom

# --- 300-word paragraph about the fictional country of Valdoria ---
paragraph = """
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

def main():
    loom = Loom()

    print("=" * 60)
    print("PHASE 1: TEACHING LOOM THE PARAGRAPH")
    print("=" * 60)

    sentences = [s.strip() for s in paragraph.split('\n') if s.strip()]
    print(f"\nFeeding {len(sentences)} sentences...\n")

    for i, sentence in enumerate(sentences, 1):
        response = loom.process(sentence)
        print(f"  [{i:2d}] {sentence}")
        print(f"       -> {response}\n")

    print("\n" + "=" * 60)
    print("PHASE 2: QUIZZING LOOM")
    print("=" * 60)

    questions = [
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

    results = {"answered": 0, "failed": 0}

    for q in questions:
        response = loom.process(q)
        # Check if Loom gave a meaningful answer vs "I don't know"
        is_answer = response and "don't know" not in response.lower() and "not sure" not in response.lower() and "no information" not in response.lower()
        status = "PASS" if is_answer else "FAIL"
        if is_answer:
            results["answered"] += 1
        else:
            results["failed"] += 1

        print(f"\n  Q: {q}")
        print(f"  A: {response}")
        print(f"  [{status}]")

    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    total = results["answered"] + results["failed"]
    print(f"  Answered: {results['answered']}/{total}")
    print(f"  Failed:   {results['failed']}/{total}")
    pct = (results['answered'] / total * 100) if total else 0
    print(f"  Score:    {pct:.0f}%")
    print("=" * 60)


if __name__ == "__main__":
    main()
