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


class CodegenError(Exception):
    """Raised when the workflow graph can't be turned into a valid script."""
