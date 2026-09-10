import asyncio
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Subprocess execution (used to run generated scripts) requires the Proactor
# event loop on Windows — the default Selector loop raises NotImplementedError
# from create_subprocess_exec.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from app.config import ensure_dirs
import app.nodes  # noqa: F401  (populates NODE_REGISTRY on import)
from app.api import backup, codegen, credentials, folders, launch, llm_import, node_types, projects, runs, webhooks, workflows
from app.execution import scheduler, webhook_registry
from app.mcp.server import mcp

# app.mount()-ing mcp.streamable_http_app() below does NOT get its own ASGI lifespan
# run automatically just by being mounted (confirmed empirically: without this, every
# MCP request 500s with "Task group is not initialized. Make sure to use run()." — a
# mounted sub-app's lifespan isn't forwarded by Starlette here) — its session manager
# needs an explicit, process-lifetime-long `async with` block, so on_event-style
# startup/shutdown (which can't host a long-lived context manager) had to become this.
mcp_http_app = mcp.streamable_http_app()


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_dirs()
    scheduler.start_scheduler()  # also does its own initial sync
    webhook_registry.sync_all()
    async with mcp.session_manager.run():
        yield
    scheduler.stop_scheduler()


app = FastAPI(title="Auto-mation", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5183"],
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(projects.router)
app.include_router(folders.router)
app.include_router(credentials.router)
app.include_router(workflows.router)
app.include_router(node_types.router)
app.include_router(codegen.router)
app.include_router(runs.router)
app.include_router(webhooks.router)
app.include_router(llm_import.router)
app.include_router(backup.router)
app.include_router(launch.router)
app.include_router(workflows.ws_router)

app.mount("/mcp", mcp_http_app)


@app.get("/api/health")
def health():
    return {"status": "ok"}
