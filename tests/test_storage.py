"""Storage-init resilience tests.

A conflicting or unique-violating secondary index on an existing database must
never crash MongoStorage construction — that would 500 every request. These
tests simulate the real-MongoDB failure (which mongomock doesn't raise on its
own) and assert the Loom still builds and serves.
"""
import mongomock
import pytest
from pymongo.errors import OperationFailure


def test_ensure_indexes_survives_conflicting_index(monkeypatch):
    import loom.storage.mongo as mongo_module
    monkeypatch.setattr(mongo_module, "PYMONGO_AVAILABLE", True)
    monkeypatch.setattr(mongo_module, "MongoClient", mongomock.MongoClient)

    original = mongomock.collection.Collection.create_index

    def conflicting(self, keys, **kwargs):
        # Mimic MongoDB rejecting a same-key index under a new name.
        if self.name == "loom_instances" and kwargs.get("name") == "idx_loom_instance_name":
            raise OperationFailure("Index already exists with a different name: instance_name_1")
        return original(self, keys, **kwargs)

    monkeypatch.setattr(mongomock.collection.Collection, "create_index", conflicting)

    from loom.brain import Loom
    lm = Loom(name="idxtest", database_name="loom_test")  # must not raise
    lm.inference.stop()
    lm.add_fact("dogs", "is", "mammals")
    assert "mammals" in (lm.get("dogs", "is") or [])


def test_ensure_indexes_survives_unique_violation(monkeypatch):
    import loom.storage.mongo as mongo_module
    monkeypatch.setattr(mongo_module, "PYMONGO_AVAILABLE", True)
    monkeypatch.setattr(mongo_module, "MongoClient", mongomock.MongoClient)

    original = mongomock.collection.Collection.create_index

    def dup_violation(self, keys, **kwargs):
        # Mimic a unique index failing because the collection already has dupes.
        if self.name == "user_stats" and kwargs.get("unique"):
            raise OperationFailure("E11000 duplicate key error building unique index")
        return original(self, keys, **kwargs)

    monkeypatch.setattr(mongomock.collection.Collection, "create_index", dup_violation)

    from loom.brain import Loom
    lm = Loom(name="idxtest2", database_name="loom_test")  # must not raise
    lm.inference.stop()
