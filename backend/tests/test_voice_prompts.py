"""Tests for the blocking ask/answer mechanism behind the MCP ask_human_voice tool
(backend/app/mcp/voice_prompts.py) — pure asyncio, no Playwright/live session needed.
"""

import asyncio

import pytest

from app.mcp import voice_prompts

WORKFLOW_ID = "__test_voice_prompts_workflow__"


@pytest.fixture(autouse=True)
def _clear_pending():
    voice_prompts._pending.pop(WORKFLOW_ID, None)
    yield
    voice_prompts._pending.pop(WORKFLOW_ID, None)


def test_ask_blocks_until_answered_and_returns_the_answer():
    async def scenario():
        async def answer_soon():
            await asyncio.sleep(0.05)
            vq = voice_prompts._pending[WORKFLOW_ID]
            ok = voice_prompts.answer(WORKFLOW_ID, vq.id, "abre o navegador e vai pro google")
            assert ok

        asyncio.create_task(answer_soon())
        result = await voice_prompts.ask(WORKFLOW_ID, "E agora?", timeout_seconds=5)
        assert result == "abre o navegador e vai pro google"
        assert WORKFLOW_ID not in voice_prompts._pending

    asyncio.run(scenario())


def test_ask_times_out_when_nobody_answers():
    async def scenario():
        with pytest.raises(TimeoutError, match="No answer received"):
            await voice_prompts.ask(WORKFLOW_ID, "E agora?", timeout_seconds=0.1)
        assert WORKFLOW_ID not in voice_prompts._pending

    asyncio.run(scenario())


def test_answer_with_wrong_question_id_returns_false():
    async def scenario():
        task = asyncio.create_task(voice_prompts.ask(WORKFLOW_ID, "E agora?", timeout_seconds=1))
        await asyncio.sleep(0.02)
        assert voice_prompts.answer(WORKFLOW_ID, "wrong-id", "resposta") is False
        assert voice_prompts.answer(WORKFLOW_ID, voice_prompts._pending[WORKFLOW_ID].id, "resposta certa") is True
        assert await task == "resposta certa"

    asyncio.run(scenario())


def test_answer_with_no_pending_question_returns_false():
    assert voice_prompts.answer(WORKFLOW_ID, "any-id", "resposta") is False


def test_second_ask_while_pending_raises():
    async def scenario():
        task = asyncio.create_task(voice_prompts.ask(WORKFLOW_ID, "first?", timeout_seconds=1))
        await asyncio.sleep(0.02)
        with pytest.raises(ValueError, match="Already a pending"):
            await voice_prompts.ask(WORKFLOW_ID, "second?", timeout_seconds=1)

        vq = voice_prompts._pending[WORKFLOW_ID]
        voice_prompts.answer(WORKFLOW_ID, vq.id, "ok")
        await task

    asyncio.run(scenario())
