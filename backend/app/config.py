import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent

DATA_DIR = REPO_ROOT / "data"
PROJECTS_DIR = DATA_DIR / "projects"
GENERATED_SCRIPTS_DIR = BACKEND_DIR / "generated_scripts"

# Defaults to the interpreter running this backend (i.e. the venv with
# playwright/requests installed), so generated scripts have the same packages
# available without requiring a separate PATH-level "python" to be configured.
PYTHON_EXECUTABLE = os.environ.get("AUTOMATION_PYTHON", sys.executable)


def ensure_dirs() -> None:
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    GENERATED_SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)


def project_dir(project_id: str) -> Path:
    return PROJECTS_DIR / project_id


def workflows_dir(project_id: str) -> Path:
    return project_dir(project_id) / "workflows"


def runs_dir(project_id: str) -> Path:
    return project_dir(project_id) / "runs"


def temp_files_dir(project_id: str, workflow_id: str) -> Path:
    """Where Save Files/Get File/Upload File nodes read and write — computed at
    codegen time (this function runs in the backend process) and baked into the
    generated script as an absolute path literal, since the script itself doesn't
    import app.config (it's a standalone process, see app/execution/runner.py)."""
    return project_dir(project_id) / "temp_files" / workflow_id


def cookies_dir(project_id: str, workflow_id: str) -> Path:
    """Where Save Cookies/Load Cookies nodes read and write by default (no credential
    selected) — deliberately NOT nested under a per-run _PROCESS_ID folder like
    temp_files_dir above: cookies are meant to persist ACROSS runs (log in once, skip
    the login flow on every run after), the opposite goal of temp_files' per-execution
    isolation."""
    return project_dir(project_id) / "cookies" / workflow_id


def cookies_dir_for_credential(project_id: str, credential_id: str) -> Path:
    """Where Login/Microsoft Login always persist their session, and where Save
    Cookies/Load Cookies persist it too when a credential is selected — keyed by the
    CREDENTIAL rather than by one workflow, so every workflow in the project that uses
    the same login credential shares the same cookie jar: log in once in workflow A,
    and workflow B's Load Cookies (or its own Login node) picks up the same session
    without logging in again."""
    return project_dir(project_id) / "cookies" / "by-credential" / credential_id
