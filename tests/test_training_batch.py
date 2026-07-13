"""Training endpoints use the bulk path and land facts + inference."""
import io
import os
import time

import mongomock
import pytest


@pytest.fixture
def client(monkeypatch):
    os.environ["google_client_id"] = "cid"
    import loom.storage.mongo as mongo_module
    monkeypatch.setattr(mongo_module, "PYMONGO_AVAILABLE", True)
    monkeypatch.setattr(mongo_module, "MongoClient", mongomock.MongoClient)
    import web_app
    web_app.pool = web_app.LoomPool(database_name="loom_test")
    return web_app, web_app.app.test_client()


PAYLOAD = (
    '[{"subject":"dogs","relation":"is","object":"mammals"},'
    '{"subject":"mammals","relation":"is","object":"vertebrates"},'
    '{"subject":"vertebrates","relation":"is","object":"animals"},'
    '{"subject":"mammals","relation":"has","object":"fur"}]'
)


def test_pasted_json_trains(client):
    web_app, c = client
    r = c.post("/api/chat", json={"message": PAYLOAD, "user": "t"})
    assert r.status_code == 200
    assert "Loaded 4 facts" in r.get_json()["response"]
    lm = web_app.pool.get("loom")
    assert "mammals" in (lm.get("dogs", "is") or [])
    # transitive chain resolves (immediately or shortly after via the daemon)
    for _ in range(20):
        if "animals" in (lm.get("dogs", "is") or []):
            break
        time.sleep(0.5)
    assert "animals" in (lm.get("dogs", "is") or [])


def test_uploaded_json_file_trains(client):
    web_app, c = client
    data = {"files": (io.BytesIO(PAYLOAD.encode()), "p.json"), "user": "t", "instance": "loom"}
    r = c.post("/api/upload-training-batch", data=data, content_type="multipart/form-data")
    assert r.status_code == 200
    assert r.get_json()["total_loaded"] == 4


def test_uploaded_txt_file_trains(client):
    web_app, c = client
    txt = "wolves | is | mammals\nowls | is | birds\n# a comment\n"
    data = {"files": (io.BytesIO(txt.encode()), "t.txt"), "user": "t", "instance": "loom"}
    r = c.post("/api/upload-training-batch", data=data, content_type="multipart/form-data")
    assert r.status_code == 200
    assert r.get_json()["total_loaded"] == 2
