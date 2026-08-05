import asyncio
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Subprocess execution (used to run generated scripts) requires the Proactor
# event loop on Windows — the default Selector loop raises NotImplementedError
# from create_subprocess_exec.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from app.config import ensure_dirs
import app.nodes  # noqa: F401  (populates NODE_REGISTRY on import)
from app.api import codegen, node_types, projects, runs, webhooks, workflows
from app.execution import scheduler, webhook_registry

app = FastAPI(title="Auto-mation")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5183"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    ensure_dirs()
    scheduler.start_scheduler()  # also does its own initial sync
    webhook_registry.sync_all()


@app.on_event("shutdown")
def on_shutdown():
    scheduler.stop_scheduler()


app.include_router(projects.router)
app.include_router(workflows.router)
app.include_router(node_types.router)
app.include_router(codegen.router)
app.include_router(runs.router)
app.include_router(webhooks.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
