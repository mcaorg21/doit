"""Tests for the Credentials modal's cookie-status endpoints
(backend/app/api/credentials.py: GET/DELETE .../credentials/{id}/cookies) — lets the
frontend show, next to a "login"-type credential, whether a Login/Microsoft Login (or
Save Cookies/Load Cookies pointed at it) has a saved session, and clear it.
"""

import json

import pytest
from fastapi.testclient import TestClient

from app.config import cookies_dir_for_credential
from app.main import app
from app.models.credential import CredentialCreate
from app.models.project import ProjectCreate
from app.storage import credential_store, project_store

client = TestClient(app)


@pytest.fixture()
def project():
    p = project_store.create_project(ProjectCreate(name="__test_cred_cookies_status_project__"))
    yield p
    project_store.delete_project(p.id)


@pytest.fixture()
def credential(project):
    c = credential_store.create_credential(
        project.id, CredentialCreate(name="test login", type="login", value="alice:secret123")
    )
    yield c
    # project teardown already removes it, but keep symmetry with other test files


def test_no_saved_session_yet(project, credential):
    resp = client.get(f"/api/projects/{project.id}/credentials/{credential.id}/cookies")
    assert resp.status_code == 200
    assert resp.json() == {"exists": False, "count": None, "savedAt": None}


def test_reports_saved_session(project, credential):
    d = cookies_dir_for_credential(project.id, credential.id)
    d.mkdir(parents=True, exist_ok=True)
    (d / "cookies.json").write_text(
        json.dumps([{"name": "a", "value": "1"}, {"name": "b", "value": "2"}]), encoding="utf-8"
    )

    resp = client.get(f"/api/projects/{project.id}/credentials/{credential.id}/cookies")
    assert resp.status_code == 200
    body = resp.json()
    assert body["exists"] is True
    assert body["count"] == 2
    assert body["savedAt"] is not None


def test_unknown_credential_404s():
    resp = client.get("/api/projects/__no_such_project__/credentials/__no_such_cred__/cookies")
    assert resp.status_code == 404


def test_delete_clears_saved_session(project, credential):
    d = cookies_dir_for_credential(project.id, credential.id)
    d.mkdir(parents=True, exist_ok=True)
    (d / "cookies.json").write_text("[]", encoding="utf-8")

    resp = client.delete(f"/api/projects/{project.id}/credentials/{credential.id}/cookies")
    assert resp.status_code == 204

    resp = client.get(f"/api/projects/{project.id}/credentials/{credential.id}/cookies")
    assert resp.json()["exists"] is False


def test_delete_is_a_no_op_when_nothing_saved(project, credential):
    resp = client.delete(f"/api/projects/{project.id}/credentials/{credential.id}/cookies")
    assert resp.status_code == 204
