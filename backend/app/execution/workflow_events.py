"""In-memory pub/sub so the MCP server's workflow mutations (see app/mcp/server.py)
reach any editor tab that has that workflow open, live — the /ws/workflows/{id} route
in app/api/workflows.py is the consumer side. Unlike a run's log stream
(app/execution/run_manager.py), a workflow can have multiple simultaneous subscribers
(e.g. two open tabs) and there's no natural "done" event — a subscription just lasts
as long as the WebSocket connection does.
"""

import asyncio
from collections import defaultdict

_subscribers: dict[str, set[asyncio.Queue]] = defaultdict(set)


def subscribe(workflow_id: str) -> asyncio.Queue:
    queue: asyncio.Queue = asyncio.Queue()
    _subscribers[workflow_id].add(queue)
    return queue


def unsubscribe(workflow_id: str, queue: asyncio.Queue) -> None:
    _subscribers[workflow_id].discard(queue)
    if not _subscribers[workflow_id]:
        del _subscribers[workflow_id]


def publish(workflow_id: str, event: dict) -> None:
    for queue in _subscribers.get(workflow_id, ()):
        queue.put_nowait(event)
