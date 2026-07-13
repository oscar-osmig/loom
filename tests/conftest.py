"""Shared pytest fixtures.

Loom normally talks to MongoDB. For tests we swap in mongomock so the suite
runs with no server (and no spaCy — the add_fact/inference paths don't need it).
"""
import time

import mongomock
import pytest

import loom.storage.mongo as mongo_module


@pytest.fixture(autouse=True)
def _patch_mongo(monkeypatch):
    """Route every MongoClient to an in-memory mongomock instance."""
    monkeypatch.setattr(mongo_module, "PYMONGO_AVAILABLE", True)
    monkeypatch.setattr(mongo_module, "MongoClient", mongomock.MongoClient)
    yield


@pytest.fixture
def loom():
    """A fresh Loom with the background daemon stopped for determinism."""
    from loom.brain import Loom

    lm = Loom(name="test", database_name="loom_test")
    lm.inference.stop()
    time.sleep(0.02)
    yield lm
    lm.inference.stop()
