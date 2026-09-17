from dataclasses import dataclass
from typing import Any


@dataclass
class CodegenContext:
    node_id: str
    params: dict[str, Any]
    in_loop: bool
    project_id: str = ""
    """The workflow's project id — lets a node's codegen resolve a credentialId param
    to its actual secret value (see app/storage/credential_store.py) at codegen time,
    since credentials are stored per-project."""
    workflow_id: str = ""
    """The workflow's own id — lets a node's codegen compute a path under this
    workflow's own data/projects/<project_id>/temp_files/<workflow_id>/ folder (see
    app/config.py::temp_files_dir), e.g. Save Files/Get File/Upload File. Empty for
    the one caller that runs before a workflow has been saved (the LLM-import
    reconstruction's validate-only generate_script call) — harmless there since the
    resulting path is never actually written to at that point."""
    browser_var: str | None = None
    """Name of the currently-open browser/context variable ("browser" or "context"),
    set by Open Browser and cleared by Close Browser — lets Close Browser know which
    one to call .close() on without needing its own copy of that choice."""
    target_var: str = "page"
    """Name of the variable element-scoped actions (fill/click/hover/select/wait/
    element-present) operate on — "page" by default, or a frame_locator variable set
    by Switch Frame. Navigate always uses "page" directly since navigation isn't
    frame-scoped."""
    has_breakpoints: bool = False
    """Open Browser uses this to auto-open Chrome DevTools. Left False (the default)
    for every real run generate_script() produces — including "Run workflow" and a
    scheduled/webhook trigger — even when the workflow has a Pause node or a
    breakpoint on a connector; DevTools popping up uninvited wasn't wanted there. Only
    app/mcp/live_sessions.py's bootstrap sets this True, since a live/voice-guided
    build session is always paused waiting on the next MCP step, and a human is
    already watching that browser window to inspect elements."""
    node_label: str = ""
    """The node's title if the user set one, else its id — use this (not node_id)
    whenever referring to the node in a user-facing message, e.g. a CodegenError."""


class CodegenError(Exception):
    """Raised when the workflow graph can't be turned into a valid script."""
