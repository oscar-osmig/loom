"""
Loom Storage Module.

MongoDB-only storage backend for the knowledge graph.

Usage:
    from loom.storage import get_storage, MongoStorage

    storage = get_storage()
    storage = MongoStorage(connection_string="mongodb://...")
"""

import logging
import os

from .mongo import MongoStorage, PYMONGO_AVAILABLE

logger = logging.getLogger(__name__)

def _load_env():
    """Load .env file into os.environ if not already set."""
    import pathlib
    env_path = pathlib.Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if key and key not in os.environ:
            os.environ[key] = value

_load_env()

__all__ = ['MongoStorage', 'get_storage', 'PYMONGO_AVAILABLE']


def get_storage(**kwargs):
    """
    Get MongoDB storage backend.

    Args:
        **kwargs: Arguments passed to MongoStorage
            - connection_string: MongoDB connection URI (defaults to MONGO_URI env var)
            - database_name: Name of the database to use
            - instance_name: Name of this Loom instance

    Returns:
        MongoStorage instance
    """
    # Pop legacy kwargs that callers may still pass
    kwargs.pop("memory_file", None)
    kwargs.pop("use_mongo", None)

    # Use MONGO_URI from environment if no connection_string was explicitly provided
    if "connection_string" not in kwargs:
        env_uri = os.environ.get("MONGO_URI")
        if env_uri:
            kwargs["connection_string"] = env_uri

    if not PYMONGO_AVAILABLE:
        raise ImportError("pymongo is required. Install with: pip install pymongo")

    return MongoStorage(**kwargs)
