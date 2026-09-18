"""Tests for get_node_catalog's structuralRules text (backend/app/mcp/server.py,
backend/app/services/workflow_reconstructor.py::_structural_rules) — this text used
to hardcode "if" as the only node type allowed two outgoing edges. That went stale
the moment a second branching node type (element_if) was registered: an MCP client
reading it would be told element_if's true/false outputs are invalid, even though
connect_nodes (_validate_new_edge) already accepted them fine. _structural_rules is
now computed from NODE_REGISTRY's own is_branch flag instead of a fixed string, so a
future branching node type shows up here automatically too.
"""

from app.mcp.server import get_node_catalog, mcp
from app.nodes.registry import NODE_REGISTRY
from app.services.workflow_reconstructor import _structural_rules


def test_structural_rules_lists_every_branch_type_from_the_registry():
    rules = _structural_rules()
    for node_type, spec in NODE_REGISTRY.items():
        if spec.is_branch:
            assert f'"{node_type}"' in rules, f"{node_type} is a branch node but missing from structural rules"


def test_structural_rules_no_longer_claims_if_is_the_only_branch_type():
    rules = _structural_rules()
    assert 'Only a node of type "if"' not in rules


def test_get_node_catalog_tool_exposes_element_if_as_a_branch_type():
    result = get_node_catalog()
    element_if = next(t for t in result.nodeTypes if t["type"] == "element_if")
    assert element_if["isBranch"] is True
    assert '"element_if"' in result.structuralRules


def test_server_instructions_tell_the_agent_to_ask_the_session_goal_upfront():
    # Regression for the standing rule: an MCP session should clarify its final
    # objective at the start (from `notes` or by asking the human) and keep
    # building toward that objective rather than stopping at the first working step.
    assert "final objective" in mcp.instructions
    assert "ASK the human" in mcp.instructions
