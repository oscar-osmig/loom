"""
Loom Storage Module.

Provides storage backends for the knowledge graph:
- MongoStorage: MongoDB-based storage for production use
- JSONFallbackStorage: JSON file-based storage for development/fallback

Usage:
    from loom.storage import get_storage, MongoStorage, JSONFallbackStorage

    # Automatic selection with fallback
    storage = get_storage(use_mongo=True)

    # Or explicitly choose backend
    storage = MongoStorage(connection_string="mongodb://localhost:27017")
    storage = JSONFallbackStorage(memory_file="my_data.json")
"""

import logging

from .mongo import MongoStorage, PYMONGO_AVAILABLE
from .json_fallback import JSONFallbackStorage

logger = logging.getLogger(__name__)

__all__ = ['MongoStorage', 'JSONFallbackStorage', 'get_storage', 'PYMONGO_AVAILABLE']


def get_storage(use_mongo: bool = True, **kwargs):
    """
    Factory function to get appropriate storage backend.
    Falls back to JSON if MongoDB is not available.

    Args:
        use_mongo: Whether to try using MongoDB (default True)
        **kwargs: Arguments passed to the storage backend
            - connection_string: MongoDB connection URI
            - database_name: Name of the database to use
            - instance_name: Name of this Loom instance
            - memory_file: Path to JSON file for fallback storage

    Returns:
        Storage backend instance (MongoStorage or JSONFallbackStorage)
    """
    memory_file = kwargs.pop("memory_file", "loom_memory.json")

    if use_mongo and PYMONGO_AVAILABLE:
        try:
            return MongoStorage(**kwargs)
        except Exception as e:
            logger.warning(f"MongoDB not available, falling back to JSON: {e}")
            return JSONFallbackStorage(memory_file)
    else:
        if use_mongo and not PYMONGO_AVAILABLE:
            logger.info("pymongo not installed, using JSON storage. Install with: pip install pymongo")
        return JSONFallbackStorage(memory_file)
