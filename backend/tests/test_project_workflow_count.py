"""Tests for ProjectSummary.workflowCount (backend/app/storage/project_store.py::
list_projects_with_counts) — lets the projects list page offer a one-click delete
only for projects that are actually empty.
"""

import pytest

from app.models.project import ProjectCreate
from app.models.workflow import WorkflowCreate
from app.storage import project_store, workflow_store


@pytest.fixture()
def project():
    p = project_store.create_project(ProjectCreate(name="__test_project_count_project__"))
    yield p
    project_store.delete_project(p.id)


def test_new_project_has_zero_workflow_count(project):
    summaries = project_store.list_projects_with_counts()
    entry = next(s for s in summaries if s.id == project.id)
    assert entry.workflowCount == 0


def test_count_reflects_created_workflows(project):
    workflow_store.create_workflow(project.id, WorkflowCreate(name="a"))
    workflow_store.create_workflow(project.id, WorkflowCreate(name="b"))

    summaries = project_store.list_projects_with_counts()
    entry = next(s for s in summaries if s.id == project.id)
    assert entry.workflowCount == 2


def test_count_ignores_the_workflow_notes_md_sibling_file(project):
    """A workflow's .md notes file lives in the same folder as its .json (see
    workflow_store.py) — the count must only see the real workflow .json files, not
    be doubled by their notes siblings."""
    wf = workflow_store.create_workflow(project.id, WorkflowCreate(name="a"))
    workflow_store.set_workflow_notes(project.id, wf.id, "some guidance")

    summaries = project_store.list_projects_with_counts()
    entry = next(s for s in summaries if s.id == project.id)
    assert entry.workflowCount == 1


def test_count_decreases_after_deleting_a_workflow(project):
    wf = workflow_store.create_workflow(project.id, WorkflowCreate(name="a"))
    workflow_store.delete_workflow(project.id, wf.id)

    summaries = project_store.list_projects_with_counts()
    entry = next(s for s in summaries if s.id == project.id)
    assert entry.workflowCount == 0
