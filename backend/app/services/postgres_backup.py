"""Raw SQL against a user-supplied Postgres connection string — the only place in
this backend that talks to a relational database (every other store in
app/storage/ is flat-file JSON, see app/storage/*.py). Deliberately plain SQL via
psycopg, no ORM: the entire job here is "dump a nested JSON object into a row, read
it back verbatim later," which never needs a query more complex than "everything in
this table" — see the plan's callout on staying minimal for the app's first (and
only) database dependency.

Every function that touches Postgres wraps psycopg errors into BackupError, which
callers (app/api/backup.py) turn into a clean 422 — same error-surfacing convention
as CodegenError (app/codegen/context.py) and ReconstructionError
(app/services/workflow_reconstructor.py).
"""

from datetime import datetime

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.models.backup import BackupCounts

TABLE_PREFIX = "automation_"

_SCHEMA_STATEMENTS = [
    f"""
    CREATE TABLE IF NOT EXISTS {TABLE_PREFIX}projects (
        id          text PRIMARY KEY,
        name        text NOT NULL,
        created_at  timestamptz NOT NULL,
        updated_at  timestamptz NOT NULL
    )
    """,
    f"""
    CREATE TABLE IF NOT EXISTS {TABLE_PREFIX}folders (
        id          text PRIMARY KEY,
        project_id  text NOT NULL,
        name        text NOT NULL,
        parent_id   text,
        created_at  timestamptz NOT NULL,
        updated_at  timestamptz NOT NULL
    )
    """,
    f"CREATE INDEX IF NOT EXISTS {TABLE_PREFIX}folders_project_id_idx ON {TABLE_PREFIX}folders (project_id)",
    f"""
    CREATE TABLE IF NOT EXISTS {TABLE_PREFIX}workflows (
        id          text PRIMARY KEY,
        project_id  text NOT NULL,
        name        text NOT NULL,
        created_at  timestamptz NOT NULL,
        updated_at  timestamptz NOT NULL,
        published   boolean NOT NULL DEFAULT false,
        folder_id   text,
        start_node_id text,
        nodes       jsonb NOT NULL DEFAULT '[]',
        edges       jsonb NOT NULL DEFAULT '[]'
    )
    """,
    # ALTER ... ADD COLUMN IF NOT EXISTS covers a table created by an earlier version
    # of this schema (CREATE TABLE IF NOT EXISTS above is a no-op once the table
    # already exists) — the only "migration" this feature needs, see the plan's
    # callout on staying minimal rather than adding a migrations framework.
    f"ALTER TABLE {TABLE_PREFIX}workflows ADD COLUMN IF NOT EXISTS start_node_id text",
    f"CREATE INDEX IF NOT EXISTS {TABLE_PREFIX}workflows_project_id_idx ON {TABLE_PREFIX}workflows (project_id)",
    f"""
    CREATE TABLE IF NOT EXISTS {TABLE_PREFIX}credentials (
        id          text PRIMARY KEY,
        project_id  text NOT NULL,
        name        text NOT NULL,
        type        text NOT NULL,
        value       text NOT NULL,
        created_at  timestamptz NOT NULL,
        updated_at  timestamptz NOT NULL
    )
    """,
    f"CREATE INDEX IF NOT EXISTS {TABLE_PREFIX}credentials_project_id_idx ON {TABLE_PREFIX}credentials (project_id)",
    f"""
    CREATE TABLE IF NOT EXISTS {TABLE_PREFIX}runs (
        id           text PRIMARY KEY,
        workflow_id  text NOT NULL,
        started_at   timestamptz NOT NULL,
        finished_at  timestamptz,
        status       text NOT NULL,
        exit_code    int,
        script_path  text NOT NULL,
        log_lines    jsonb NOT NULL DEFAULT '[]'
    )
    """,
    f"CREATE INDEX IF NOT EXISTS {TABLE_PREFIX}runs_workflow_id_idx ON {TABLE_PREFIX}runs (workflow_id)",
]


class BackupError(Exception):
    """Connection, DDL, or query failure — surfaced as a 422 with a readable message."""


def connect(connection_string: str) -> psycopg.Connection:
    try:
        return psycopg.connect(connection_string, row_factory=dict_row, connect_timeout=10)
    except psycopg.Error as exc:
        raise BackupError(f"Couldn't connect to Postgres: {exc}") from exc


def test_connection(connection_string: str) -> None:
    with connect(connection_string) as conn:
        try:
            conn.execute("SELECT 1")
        except psycopg.Error as exc:
            raise BackupError(f"Postgres connection test failed: {exc}") from exc


def ensure_schema(conn: psycopg.Connection) -> None:
    try:
        with conn.transaction():
            for stmt in _SCHEMA_STATEMENTS:
                conn.execute(stmt)
    except psycopg.Error as exc:
        raise BackupError(f"Couldn't create backup tables: {exc}") from exc


def _upsert(conn: psycopg.Connection, sql: str, rows: list[dict]) -> None:
    if not rows:
        return
    try:
        with conn.cursor() as cur:
            cur.executemany(sql, rows)
    except psycopg.Error as exc:
        raise BackupError(f"Couldn't write to Postgres: {exc}") from exc


def upsert_projects(conn: psycopg.Connection, rows: list[dict]) -> None:
    _upsert(
        conn,
        f"""
        INSERT INTO {TABLE_PREFIX}projects (id, name, created_at, updated_at)
        VALUES (%(id)s, %(name)s, %(createdAt)s, %(updatedAt)s)
        ON CONFLICT (id) DO UPDATE SET
            name = EXCLUDED.name,
            updated_at = EXCLUDED.updated_at
        """,
        rows,
    )


def upsert_folders(conn: psycopg.Connection, rows: list[dict]) -> None:
    _upsert(
        conn,
        f"""
        INSERT INTO {TABLE_PREFIX}folders (id, project_id, name, parent_id, created_at, updated_at)
        VALUES (%(id)s, %(projectId)s, %(name)s, %(parentId)s, %(createdAt)s, %(updatedAt)s)
        ON CONFLICT (id) DO UPDATE SET
            project_id = EXCLUDED.project_id,
            name = EXCLUDED.name,
            parent_id = EXCLUDED.parent_id,
            updated_at = EXCLUDED.updated_at
        """,
        rows,
    )


def upsert_workflows(conn: psycopg.Connection, rows: list[dict]) -> None:
    shaped = [
        {**r, "nodes": Jsonb(r["nodes"]), "edges": Jsonb(r["edges"])}
        for r in rows
    ]
    _upsert(
        conn,
        f"""
        INSERT INTO {TABLE_PREFIX}workflows
            (id, project_id, name, created_at, updated_at, published, folder_id, start_node_id, nodes, edges)
        VALUES
            (%(id)s, %(projectId)s, %(name)s, %(createdAt)s, %(updatedAt)s, %(published)s, %(folderId)s,
             %(startNodeId)s, %(nodes)s, %(edges)s)
        ON CONFLICT (id) DO UPDATE SET
            project_id = EXCLUDED.project_id,
            name = EXCLUDED.name,
            updated_at = EXCLUDED.updated_at,
            published = EXCLUDED.published,
            folder_id = EXCLUDED.folder_id,
            start_node_id = EXCLUDED.start_node_id,
            nodes = EXCLUDED.nodes,
            edges = EXCLUDED.edges
        """,
        shaped,
    )


def upsert_credentials(conn: psycopg.Connection, rows: list[dict]) -> None:
    _upsert(
        conn,
        f"""
        INSERT INTO {TABLE_PREFIX}credentials (id, project_id, name, type, value, created_at, updated_at)
        VALUES (%(id)s, %(projectId)s, %(name)s, %(type)s, %(value)s, %(createdAt)s, %(updatedAt)s)
        ON CONFLICT (id) DO UPDATE SET
            project_id = EXCLUDED.project_id,
            name = EXCLUDED.name,
            type = EXCLUDED.type,
            value = EXCLUDED.value,
            updated_at = EXCLUDED.updated_at
        """,
        rows,
    )


def upsert_runs(conn: psycopg.Connection, rows: list[dict]) -> None:
    shaped = [{**r, "logLines": Jsonb(r["logLines"])} for r in rows]
    _upsert(
        conn,
        f"""
        INSERT INTO {TABLE_PREFIX}runs
            (id, workflow_id, started_at, finished_at, status, exit_code, script_path, log_lines)
        VALUES
            (%(id)s, %(workflowId)s, %(startedAt)s, %(finishedAt)s, %(status)s, %(exitCode)s, %(scriptPath)s, %(logLines)s)
        ON CONFLICT (id) DO UPDATE SET
            workflow_id = EXCLUDED.workflow_id,
            started_at = EXCLUDED.started_at,
            finished_at = EXCLUDED.finished_at,
            status = EXCLUDED.status,
            exit_code = EXCLUDED.exit_code,
            script_path = EXCLUDED.script_path,
            log_lines = EXCLUDED.log_lines
        """,
        shaped,
    )


def _fetch_all(conn: psycopg.Connection, sql: str) -> list[dict]:
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            return cur.fetchall()
    except psycopg.Error as exc:
        raise BackupError(f"Couldn't read from Postgres: {exc}") from exc


def fetch_all_projects(conn: psycopg.Connection) -> list[dict]:
    return _fetch_all(
        conn,
        f"""SELECT id, name, created_at AS "createdAt", updated_at AS "updatedAt"
            FROM {TABLE_PREFIX}projects""",
    )


def fetch_all_folders(conn: psycopg.Connection) -> list[dict]:
    return _fetch_all(
        conn,
        f"""SELECT id, project_id AS "projectId", name, parent_id AS "parentId",
                   created_at AS "createdAt", updated_at AS "updatedAt"
            FROM {TABLE_PREFIX}folders""",
    )


def fetch_all_workflows(conn: psycopg.Connection) -> list[dict]:
    return _fetch_all(
        conn,
        f"""SELECT id, project_id AS "projectId", name,
                   created_at AS "createdAt", updated_at AS "updatedAt",
                   published, folder_id AS "folderId", start_node_id AS "startNodeId", nodes, edges
            FROM {TABLE_PREFIX}workflows""",
    )


def fetch_all_credentials(conn: psycopg.Connection) -> list[dict]:
    return _fetch_all(
        conn,
        f"""SELECT id, project_id AS "projectId", name, type, value,
                   created_at AS "createdAt", updated_at AS "updatedAt"
            FROM {TABLE_PREFIX}credentials""",
    )


def fetch_all_runs(conn: psycopg.Connection) -> list[dict]:
    return _fetch_all(
        conn,
        f"""SELECT id, workflow_id AS "workflowId", started_at AS "startedAt",
                   finished_at AS "finishedAt", status, exit_code AS "exitCode",
                   script_path AS "scriptPath", log_lines AS "logLines"
            FROM {TABLE_PREFIX}runs""",
    )


def count_rows(conn: psycopg.Connection) -> BackupCounts:
    def _count(table: str) -> int:
        row = _fetch_all(conn, f"SELECT count(*) AS n FROM {TABLE_PREFIX}{table}")
        return row[0]["n"] if row else 0

    return BackupCounts(
        projects=_count("projects"),
        folders=_count("folders"),
        workflows=_count("workflows"),
        credentials=_count("credentials"),
        runs=_count("runs"),
    )


def last_updated_at(conn: psycopg.Connection) -> dict[str, datetime | None]:
    def _max(table: str, column: str) -> datetime | None:
        row = _fetch_all(conn, f"SELECT max({column}) AS m FROM {TABLE_PREFIX}{table}")
        return row[0]["m"] if row else None

    return {
        "projects": _max("projects", "updated_at"),
        "folders": _max("folders", "updated_at"),
        "workflows": _max("workflows", "updated_at"),
        "credentials": _max("credentials", "updated_at"),
        "runs": _max("runs", "started_at"),
    }
