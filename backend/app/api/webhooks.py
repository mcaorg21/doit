from fastapi import APIRouter, Request

from app.execution import webhook_registry

router = APIRouter(tags=["webhooks"])


@router.api_route("/api/webhooks/{path:path}", methods=["GET", "POST"])
async def call_webhook(path: str, request: Request):
    return await webhook_registry.trigger(request.method, path)
