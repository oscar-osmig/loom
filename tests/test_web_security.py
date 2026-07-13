"""Web API authorization tests.

The security guarantee is that privileged actions require a *verified* Google
ID token — a forged `email` field in the request body/query grants nothing.
google-auth isn't needed here: without a valid token `verified_email()` returns
None, so every gate fails closed. The allow-path is covered by stubbing the
verifier to stand in for a validated token."""
import os

import mongomock
import pytest


@pytest.fixture
def client(monkeypatch):
    os.environ["ADMIN_EMAIL"] = "admin@example.com"
    os.environ["google_client_id"] = "test-client-id"
    import loom.storage.mongo as mongo_module
    monkeypatch.setattr(mongo_module, "PYMONGO_AVAILABLE", True)
    monkeypatch.setattr(mongo_module, "MongoClient", mongomock.MongoClient)
    import web_app
    # Fresh pool so instances don't leak between tests.
    web_app.pool = web_app.LoomPool(database_name="loom_test")
    return web_app, web_app.app.test_client()


def _chat(client, msg, forged_email="admin@example.com", token=None):
    _, c = client
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    body = {"message": msg, "user": "someone"}
    if forged_email:
        body["email"] = forged_email
    return c.post("/api/chat", json=body, headers=headers)


def test_forget_all_denied_with_forged_email(client):
    r = _chat(client, "/forget-all")
    assert "Permission denied" in r.get_json()["response"]


def test_style_command_denied(client):
    assert "Permission denied" in _chat(client, "/style").get_json()["response"]


def test_load_command_denied_without_admin(client):
    r = _chat(client, "/load ../../etc/passwd")
    assert "Permission denied" in r.get_json()["response"]


def test_load_all_denied(client):
    assert "Permission denied" in _chat(client, "/load-all").get_json()["response"]


def test_create_instance_requires_token(client):
    _, c = client
    r = c.post("/api/instances", json={"display_name": "Mine", "email": "x@y.com"})
    assert r.status_code == 401


def test_delete_instance_requires_token(client):
    _, c = client
    r = c.delete("/api/instances", json={"instance_name": "user:x@y.com:mine", "email": "x@y.com"})
    assert r.status_code == 401


def test_style_endpoint_denied(client):
    _, c = client
    assert c.get("/api/style?email=admin@example.com").status_code == 403


def test_help_works_for_anonymous(client):
    r = _chat(client, "/help", forged_email=None)
    assert r.status_code == 200 and r.get_json()["type"] == "help"


def test_max_content_length_configured(client):
    web_app, _ = client
    assert web_app.app.config["MAX_CONTENT_LENGTH"] == 16 * 1024 * 1024


def test_admin_allowed_with_verified_token(client, monkeypatch):
    web_app, c = client
    # Stand in for a cryptographically verified admin token.
    monkeypatch.setattr(web_app, "verified_email", lambda: "admin@example.com")
    r = c.post("/api/chat", json={"message": "/style", "user": "a"},
               headers={"Authorization": "Bearer x"})
    assert r.get_json()["type"] == "style"
    r = c.post("/api/instances", json={"display_name": "Mine"},
               headers={"Authorization": "Bearer x"})
    assert r.status_code == 201
    assert r.get_json()["instance_name"] == "user:admin@example.com:mine"
