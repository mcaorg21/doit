"""Tests for the MCP ask_human_voice tool (backend/app/mcp/server.py) — the thin
wrapper around voice_prompts.ask that validates the workflow exists and publishes
the question over workflow_events so an open editor tab can show a mic prompt.
"""

import asyncio

import pytest

from app.execution import workflow_events
from app.mcp.server import ask_human_voice
from app.mcp import voice_prompts
from app.models.project import ProjectCreate
from app.models.workflow import WorkflowCreate
from app.storage import project_store, workflow_store


@pytest.fixture()
def project():
    p = project_store.create_project(ProjectCreate(name="__test_ask_human_voice_project__"))
    yield p
    project_store.delete_project(p.id)


@pytest.fixture()
def workflow(project):
    return workflow_store.create_workflow(project.id, WorkflowCreate(name="ask human voice test"))


def test_raises_for_unknown_workflow(project):
    with pytest.raises(ValueError):
        asyncio.run(ask_human_voice(project.id, "no_such_workflow", "E agora?", timeout_seconds=1))


def test_publishes_question_and_returns_the_answer(project, workflow):
    async def scenario():
        queue = workflow_events.subscribe(workflow.id)
        try:
            async def answer_soon():
                event = await queue.get()
                assert event["type"] == "voice_question_asked"
                assert event["question"] == "E agora?"
                voice_prompts.answer(workflow.id, event["questionId"], "clica no botao de login")

            asyncio.create_task(answer_soon())
            result = await ask_human_voice(project.id, workflow.id, "E agora?", timeout_seconds=5)
            assert result == "clica no botao de login"
        finally:
            workflow_events.unsubscribe(workflow.id, queue)

    asyncio.run(scenario())


def test_timeout_publishes_timeout_event(project, workflow):
    async def scenario():
        queue = workflow_events.subscribe(workflow.id)
        try:
            with pytest.raises(TimeoutError):
                await ask_human_voice(project.id, workflow.id, "E agora?", timeout_seconds=0.1)
            asked = await asyncio.wait_for(queue.get(), timeout=1)
            timed_out = await asyncio.wait_for(queue.get(), timeout=1)
            assert asked["type"] == "voice_question_asked"
            assert timed_out["type"] == "voice_question_timeout"
            assert timed_out["questionId"] == asked["questionId"]
        finally:
            workflow_events.unsubscribe(workflow.id, queue)

    asyncio.run(scenario())
