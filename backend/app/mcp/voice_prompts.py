"""In-memory registry of pending "ask the human" voice questions — the blocking
round-trip behind the MCP ask_human_voice tool (app/mcp/server.py). An agent calling
that tool publishes a question onto the same workflow_events channel the editor
already listens to (/ws/workflows/{id}), then awaits an asyncio.Event; the browser
tab shows a mic prompt, the human answers, and the REST endpoint in
app/api/workflows.py resolves that Event with the transcribed text — unblocking the
tool call. Only one question can be pending per workflow at a time, matching how the
agent actually uses it: it awaits the answer before deciding what to do next, so a
second concurrent question would only ever indicate a bug, not a legitimate need.
"""

import asyncio
import uuid

from app.execution import workflow_events


class VoiceQuestion:
    def __init__(self, question: str):
        self.id = uuid.uuid4().hex[:8]
        self.question = question
        self.answer: str | None = None
        self.event = asyncio.Event()


_pending: dict[str, VoiceQuestion] = {}


async def ask(workflow_id: str, question: str, timeout_seconds: float) -> str:
    if workflow_id in _pending:
        raise ValueError(
            "Already a pending voice question for this workflow — wait for it to resolve before asking another."
        )
    vq = VoiceQuestion(question)
    _pending[workflow_id] = vq
    workflow_events.publish(workflow_id, {"type": "voice_question_asked", "questionId": vq.id, "question": question})
    try:
        await asyncio.wait_for(vq.event.wait(), timeout=timeout_seconds)
    except asyncio.TimeoutError:
        workflow_events.publish(workflow_id, {"type": "voice_question_timeout", "questionId": vq.id})
        raise TimeoutError(
            f"No answer received within {timeout_seconds:.0f}s — is the workflow open in a browser tab? "
            "Try asking again, or ask directly in this terminal as a fallback."
        ) from None
    finally:
        _pending.pop(workflow_id, None)
    return vq.answer or ""


def answer(workflow_id: str, question_id: str, answer_text: str) -> bool:
    vq = _pending.get(workflow_id)
    if vq is None or vq.id != question_id:
        return False
    vq.answer = answer_text
    vq.event.set()
    return True
