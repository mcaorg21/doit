from dataclasses import dataclass
from typing import Any


@dataclass
class CodegenContext:
    node_id: str
    params: dict[str, Any]
    in_loop: bool
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
    """True when the workflow has a Pause node or a breakpoint on any connector —
    Open Browser uses this to auto-open Chrome DevTools, since a debugging run is the
    one time you actually want it up without being asked each time."""
    node_label: str = ""
    """The node's title if the user set one, else its id — use this (not node_id)
    whenever referring to the node in a user-facing message, e.g. a CodegenError."""


class CodegenError(Exception):
    """Raised when the workflow graph can't be turned into a valid script."""
