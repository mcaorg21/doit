"""Tests for the MCP list_credentials tool (backend/app/mcp/server.py) and the
credential-aware add_node downgrade fix (workflow_reconstructor.py::
downgrade_node_if_missing_credential) — an MCP client used to have no way to supply
a real credentialId, so add_node unconditionally downgraded ANY node type with a
credentialType-tagged param (e.g. microsoft_login) to an 'unknown' placeholder, even
if a valid id happened to be passed. Now list_credentials lets the client look up a
real id by name/type, and add_node only downgrades when the field is actually
missing or points at a credential that doesn't exist in this project.
"""

import asyncio

import pytest

from app.mcp.server import add_node, list_credentials
from app.models.credential import CredentialCreate
from app.models.project import ProjectCreate
from app.models.workflow import WorkflowCreate
from app.services.workflow_reconstructor import build_node_catalog, downgrade_node_if_missing_credential
from app.storage import credential_store, project_store, workflow_store


@pytest.fixture()
def project():
    p = project_store.create_project(ProjectCreate(name="__test_mcp_credentials_project__"))
    yield p
    project_store.delete_project(p.id)


@pytest.fixture()
def workflow(project):
    return workflow_store.create_workflow(project.id, WorkflowCreate(name="mcp credentials test"))


@pytest.fixture()
def login_credential(project):
    return credential_store.create_credential(
        project.id, CredentialCreate(name="Microsoft PAN", type="login", value="alice:s3cret")
    )


# --- list_credentials -----------------------------------------------------------


def test_list_credentials_never_exposes_the_secret_value(project, login_credential):
    result = list_credentials(project.id)
    assert result == [{"id": login_credential.id, "name": "Microsoft PAN", "type": "login"}]
    assert "value" not in result[0]
    assert "s3cret" not in str(result)


def test_list_credentials_empty_project():
    p = project_store.create_project(ProjectCreate(name="__test_mcp_credentials_empty__"))
    try:
        assert list_credentials(p.id) == []
    finally:
        project_store.delete_project(p.id)


def test_list_credentials_unknown_project_raises():
    with pytest.raises(ValueError):
        list_credentials("proj_does_not_exist")


# --- downgrade_node_if_missing_credential (direct unit tests) -------------------


def _ms_login_node(**params):
    from app.models.workflow import Position, WFNode

    return WFNode(id="n1", type="microsoft_login", position=Position(x=0, y=0), params=params)


def test_downgrade_skipped_when_credential_id_is_valid(project, login_credential):
    catalog = build_node_catalog()
    node = _ms_login_node(url="https://example.com", credentialId=login_credential.id)
    note = downgrade_node_if_missing_credential(node, catalog, project.id)
    assert note is None
    assert node.type == "microsoft_login"


def test_downgrade_happens_when_credential_id_missing(project):
    catalog = build_node_catalog()
    node = _ms_login_node(url="https://example.com")
    note = downgrade_node_if_missing_credential(node, catalog, project.id)
    assert note is not None
    assert node.type == "unknown"
    assert "login" in node.params["sourceHint"]


def test_downgrade_happens_when_credential_id_does_not_exist(project):
    catalog = build_node_catalog()
    node = _ms_login_node(url="https://example.com", credentialId="cred_totally_made_up")
    note = downgrade_node_if_missing_credential(node, catalog, project.id)
    assert note is not None
    assert node.type == "unknown"


def test_downgrade_without_project_id_falls_back_to_old_missing_only_check():
    # No project_id passed (e.g. a caller that can't look anything up) — can't
    # validate existence, so only checks presence, same as the pre-fix behavior.
    catalog = build_node_catalog()
    node = _ms_login_node(url="https://example.com", credentialId="cred_totally_made_up")
    note = downgrade_node_if_missing_credential(node, catalog, None)
    assert note is None
    assert node.type == "microsoft_login"


# --- add_node end-to-end ----------------------------------------------------------


def test_add_node_keeps_real_type_with_a_valid_credential(project, workflow, login_credential):
    result = asyncio.run(
        add_node(
            project.id,
            workflow.id,
            "microsoft_login",
            params={"url": "https://example.com", "credentialId": login_credential.id},
        )
    )
    assert result.node.type == "microsoft_login"
    assert result.downgraded is False
    assert result.needsHumanAttention is False


def test_add_node_downgrades_without_a_credential(project, workflow):
    result = asyncio.run(add_node(project.id, workflow.id, "microsoft_login", params={"url": "https://example.com"}))
    assert result.node.type == "unknown"
    assert result.downgraded is True
    assert result.needsHumanAttention is True
