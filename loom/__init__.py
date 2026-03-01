"""
Loom - A symbolic knowledge system that weaves connections like neural threads.

Enhanced with:
- Spreading activation (Collins & Loftus model)
- Hebbian connection strengthening
- Text chunking for paragraphs
- Improved coreference resolution
"""

from .brain import Loom
from .cli import run_cli
from .activation import ActivationNetwork
from .chunker import TextChunker

__version__ = "0.6"
__all__ = ["Loom", "run_cli", "ActivationNetwork", "TextChunker"]
