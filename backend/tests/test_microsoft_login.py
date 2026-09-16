import json
import shutil

import pytest
from playwright.sync_api import sync_playwright

from app.codegen.context import CodegenContext
from app.codegen.engine import HEADER
from app.config import cookies_dir_for_credential
from app.models.credential import CredentialCreate
from app.models.project import ProjectCreate
from app.nodes.microsoft_login import codegen_microsoft_login
from app.nodes.registry import NODE_REGISTRY
from app.storage import credential_store, project_store


WORKFLOW_ID = "__test_microsoft_login_workflow__"
LOGIN_URL = "https://fake-microsoft-login.example/login"


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        yield b
        b.close()


@pytest.fixture()
def project():
    p = project_store.create_project(ProjectCreate(name="__test_microsoft_login_project__"))
    yield p
    project_store.delete_project(p.id)


@pytest.fixture()
def credential(project):
    c = credential_store.create_credential(
        project.id, CredentialCreate(name="Microsoft", type="login", value="alice@example.com:secret123")
    )
    yield c
    credential_store.delete_credential(project.id, c.id)


@pytest.fixture()
def page(browser):
    pg = browser.new_page()
    pg.route(
        LOGIN_URL,
        lambda route: route.fulfill(content_type="text/html", body="""
            <input id='email'><button id='next'>Next</button>
            <div id='password-step' style='display:none'><input id='password' type='password'><button id='signin'>Sign in</button></div>
            <div id='dashboard' style='display:none'>Dashboard</div>
            <script>
              document.getElementById('next').onclick = () => {
                if (document.getElementById('email').value === 'alice@example.com') {
                  document.getElementById('password-step').style.display = 'block'
                }
              }
              document.getElementById('signin').onclick = () => {
                if (document.getElementById('password').value === 'secret123') {
                  document.cookie='session=valid; path=/'
                  document.getElementById('dashboard').style.display='block'
                }
              }
            </script>
        """),
    )
    yield pg
    pg.close()


@pytest.fixture()
def password_only_page(browser):
    pg = browser.new_page()
    pg.route(
        LOGIN_URL,
        lambda route: route.fulfill(content_type="text/html", body="""
            <input id='password' type='password'><button id='signin'>Sign in</button>
            <div id='dashboard' style='display:none'>Dashboard</div>
            <script>
              document.getElementById('signin').onclick = () => {
                if (document.getElementById('password').value === 'secret123') {
                  document.cookie='session=valid; path=/'
                  document.getElementById('dashboard').style.display='block'
                }
              }
            </script>
        """),
    )
    yield pg
    pg.close()


@pytest.fixture()
def both_fields_present_page(browser):
    pg = browser.new_page()
    pg.route(
        LOGIN_URL,
        lambda route: route.fulfill(content_type="text/html", body="""
            <input id='email'><button id='next'>Next</button>
            <input id='password' type='password'><button id='signin'>Sign in</button>
            <div id='dashboard' style='display:none'>Dashboard</div>
            <script>
              document.getElementById('next').onclick = () => {
                if (document.getElementById('email').value !== 'alice@example.com') throw Error('email missing')
              }
              document.getElementById('signin').onclick = () => {
                if (document.getElementById('email').value === 'alice@example.com' &&
                    document.getElementById('password').value === 'secret123') {
                  document.getElementById('dashboard').style.display = 'block'
                }
              }
            </script>
        """),
    )
    yield pg
    pg.close()


def test_registered_and_not_live_demoable():
    from app.mcp.live_sessions import is_demoable

    spec = NODE_REGISTRY["microsoft_login"]
    assert spec.icon == "log-in"
    assert next(p for p in spec.params if p.key == "credentialId").credentialType == "login"
    assert is_demoable("microsoft_login")[0] is False


def test_two_step_login_and_cookie_save(project, credential, page):
    params = {
        "url": LOGIN_URL,
        "credentialId": credential.id,
        "usernameSelector": "#email",
        "usernameSubmitSelector": "#next",
        "passwordSelector": "#password",
        "passwordSubmitSelector": "#signin",
        "staySignedInSelector": "",
        "confirmSelector": "#dashboard",
        "stepTimeout": 2,
        "confirmTimeout": 2,
        "resultVar": "login_result",
    }
    ctx = CodegenContext(
        node_id="n1", params=params, in_loop=False, project_id=project.id,
        workflow_id=WORKFLOW_ID, target_var="page", node_label="Microsoft Login",
    )
    fragment = codegen_microsoft_login(ctx)
    ns = {}
    exec(compile(HEADER, "<header>", "exec"), ns)
    ns["page"] = page
    try:
        exec(compile(fragment, "<fragment>", "exec"), ns)
        assert page.locator("#dashboard").is_visible()
        assert ns["login_result"] == {"alreadyLoggedIn": False}
        saved = cookies_dir_for_credential(project.id, credential.id) / "cookies.json"
        assert any(c["name"] == "session" for c in json.loads(saved.read_text(encoding="utf-8")))
    finally:
        d = cookies_dir_for_credential(project.id, credential.id)
        if d.exists():
            shutil.rmtree(d)


def test_session_is_shared_with_a_different_workflow_using_the_same_credential(project, browser, credential, page):
    params = {
        "url": LOGIN_URL,
        "credentialId": credential.id,
        "usernameSelector": "#email",
        "usernameSubmitSelector": "#next",
        "passwordSelector": "#password",
        "passwordSubmitSelector": "#signin",
        "staySignedInSelector": "",
        "confirmSelector": "#dashboard",
        "stepTimeout": 2,
        "confirmTimeout": 2,
    }
    ctx = CodegenContext(
        node_id="n1", params=params, in_loop=False, project_id=project.id,
        workflow_id=WORKFLOW_ID, target_var="page", node_label="Microsoft Login",
    )
    ns = {}
    exec(compile(HEADER, "<header>", "exec"), ns)
    ns["page"] = page
    try:
        exec(compile(codegen_microsoft_login(ctx), "<fragment>", "exec"), ns)
        assert page.locator("#dashboard").is_visible()

        fresh_page = browser.new_page()
        fresh_page.route(LOGIN_URL, lambda route: route.fulfill(
            content_type="text/html",
            body="<div id='dashboard'>already in from cookies</div>" if "session=valid" in route.request.headers.get("cookie", "") else "<div>no session</div>",
        ))
        try:
            other_ctx = CodegenContext(
                node_id="n1", params={**params, "resultVar": "r2"}, in_loop=False, project_id=project.id,
                workflow_id="__a_totally_different_workflow__", target_var="page", node_label="Microsoft Login",
            )
            ns2 = {}
            exec(compile(HEADER, "<header>", "exec"), ns2)
            ns2["page"] = fresh_page
            exec(compile(codegen_microsoft_login(other_ctx), "<fragment>", "exec"), ns2)
            assert ns2["r2"] == {"alreadyLoggedIn": True}
        finally:
            fresh_page.close()
    finally:
        d = cookies_dir_for_credential(project.id, credential.id)
        if d.exists():
            shutil.rmtree(d)


def test_registered_with_typing_option_params():
    spec = NODE_REGISTRY["microsoft_login"]
    param_keys = {p.key for p in spec.params}
    assert {"clearFirst", "simulateTyping"} <= param_keys
    assert "cookiesFilename" not in param_keys  # cookie storage is now tied to the credential, not a filename


def test_clear_first_and_simulate_typing_still_log_in(project, credential, page):
    params = {
        "url": LOGIN_URL,
        "credentialId": credential.id,
        "usernameSelector": "#email",
        "usernameSubmitSelector": "#next",
        "passwordSelector": "#password",
        "passwordSubmitSelector": "#signin",
        "staySignedInSelector": "",
        "confirmSelector": "#dashboard",
        "stepTimeout": 2,
        "confirmTimeout": 2,
        "resultVar": "login_result",
        "clearFirst": True,
        "simulateTyping": True,
    }
    ctx = CodegenContext(
        node_id="n1", params=params, in_loop=False, project_id=project.id,
        workflow_id=WORKFLOW_ID, target_var="page", node_label="Microsoft Login",
    )
    fragment = codegen_microsoft_login(ctx)
    assert fragment.count(".clear()") == 2  # username, password
    assert fragment.count(".press_sequentially(") == 2
    assert fragment.count(".fill(") == 2  # fallback if the typed value was not retained
    ns = {}
    exec(compile(HEADER, "<header>", "exec"), ns)
    ns["page"] = page
    try:
        exec(compile(fragment, "<fragment>", "exec"), ns)
        assert page.locator("#dashboard").is_visible()
        assert ns["login_result"] == {"alreadyLoggedIn": False}
    finally:
        d = cookies_dir_for_credential(project.id, credential.id)
        if d.exists():
            shutil.rmtree(d)


def test_login_continues_when_session_starts_on_password_step(project, credential, password_only_page):
    params = {
        "url": LOGIN_URL,
        "credentialId": credential.id,
        "usernameSelector": "#email",
        "usernameSubmitSelector": "#next",
        "passwordSelector": "#password",
        "passwordSubmitSelector": "#signin",
        "staySignedInSelector": "",
        "confirmSelector": "#dashboard",
        "stepTimeout": 0.2,
        "confirmTimeout": 2,
        "resultVar": "login_result",
    }
    ctx = CodegenContext(
        node_id="n1", params=params, in_loop=False, project_id=project.id,
        workflow_id=WORKFLOW_ID, target_var="page", node_label="Microsoft Login",
    )
    fragment = codegen_microsoft_login(ctx)
    ns = {}
    exec(compile(HEADER, "<header>", "exec"), ns)
    ns["page"] = password_only_page
    try:
        exec(compile(fragment, "<fragment>", "exec"), ns)
        assert password_only_page.locator("#dashboard").is_visible()
        assert ns["login_result"] == {"alreadyLoggedIn": False}
    finally:
        d = cookies_dir_for_credential(project.id, credential.id)
        if d.exists():
            shutil.rmtree(d)


def test_email_is_prioritized_when_both_fields_appear_visible(project, credential, both_fields_present_page):
    params = {
        "url": LOGIN_URL,
        "credentialId": credential.id,
        "usernameSelector": "#email",
        "usernameSubmitSelector": "#next",
        "passwordSelector": "#password",
        "passwordSubmitSelector": "#signin",
        "staySignedInSelector": "",
        "confirmSelector": "#dashboard",
        "stepTimeout": 0.2,
        "confirmTimeout": 2,
        "reuseSavedSession": False,
    }
    ctx = CodegenContext(
        node_id="n1", params=params, in_loop=False, project_id=project.id,
        workflow_id=WORKFLOW_ID, target_var="page", node_label="Microsoft Login",
    )
    ns = {}
    exec(compile(HEADER, "<header>", "exec"), ns)
    ns["page"] = both_fields_present_page
    try:
        exec(compile(codegen_microsoft_login(ctx), "<fragment>", "exec"), ns)
        assert both_fields_present_page.locator("#email").input_value() == "alice@example.com"
        assert both_fields_present_page.locator("#dashboard").is_visible()
    finally:
        d = cookies_dir_for_credential(project.id, credential.id)
        if d.exists():
            shutil.rmtree(d)
