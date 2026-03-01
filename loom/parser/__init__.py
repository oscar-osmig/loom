"""
Parser module for Loom.
Handles natural language input and extracts structured knowledge threads.
Learns from any conversation pattern using discourse analysis.

Enhanced with:
- Correction patterns (no, wrong, actually)
- Refinement patterns (only when, except, but not if)
- Procedural patterns (first, then, finally)
- Clarification logic
"""

from .base import Parser

__all__ = ["Parser"]
