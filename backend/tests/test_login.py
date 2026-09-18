"""Tests for the Login node (backend/app/nodes/login.py) — a composite node that
loads any previously-saved cookies, checks whether it's already logged in, and only
runs the full username/password/2FA form + saves fresh cookies if not.

Real headless Chromium, same _exec_fragment-against-HEADER pattern as
test_download_file.py/test_cookies.py/test_click_bypass.py. The login page itself is
served via page.route() interception rather than a real HTTP server or a `data:` URL
— `data:` pages can't hold cookies (opaque origin), and route() gives a real,
cookie-capable https:// origin without needing a server. The routed handler inspects
the incoming request's Cookie header to decide whether to serve the "already logged
in" page or the login form, mirroring how a real site's server-side session check
would behave.

Credentials are stored per-project (app/storage/credential_store.py requires a real
project to exist), so this uses a real project via project_store, same as
test_mcp_run_workflow.py, rather than a hardcoded fake project id.
"""

import json
import shutil

import pytest
from playwright.sync_api import sync_playwright

from app.codegen.context import CodegenContext, CodegenError
from app.codegen.engine import HEADER, generate_script
from app.config import cookies_dir_for_credential
from app.models.credential import CredentialCreate
from app.models.project import ProjectCreate
from app.models.workflow import Position, WFEdge, WFNode
from app.nodes.login import codegen_login
from app.nodes.registry import NODE_REGISTRY
from app.storage import credential_store, project_store

WORKFLOW_ID = "__test_login_workflow__"
LOGIN_URL = "https://fake-login-test.example/login"
LOGIN_URL_2FA = "https://fake-login-test.example/login-2fa"

ALREADY_LOGGED_IN_HTML = "<div id=\"dashboard\">Bem-vindo de volta</div>"

LOGIN_FORM_HTML = """
<input id="user"><input id="pass" type="password">
<button id="go">Entrar</button>
<div id="dashboard" style="display:none">Bem-vindo</div>
<script>
document.getElementById('go').addEventListener('click', function () {
  if (document.getElementById('user').value === 'alice' && document.getElementById('pass').value === 'secret123') {
    document.cookie = 'session=valid; path=/';
    document.getElementById('dashboard').style.display = 'block';
  }
});
</script>
"""

LOGIN_FORM_2FA_HTML = """
<input id="user"><input id="pass" type="password">
<button id="go">Entrar</button>
<div id="twofa" style="display:none">
  <input id="code">
  <button id="code-submit">Verificar</button>
</div>
<div id="dashboard" style="display:none">Bem-vindo</div>
<script>
document.getElementById('go').addEventListener('click', function () {
  if (document.getElementById('user').value === 'alice' && document.getElementById('pass').value === 'secret123') {
    document.getElementById('twofa').style.display = 'block';
  }
});
document.getElementById('code-submit').addEventListener('click', function () {
  if (/^[0-9]{6}$/.test(document.getElementById('code').value)) {
    document.cookie = 'session=valid; path=/';
    document.getElementById('dashboard').style.display = 'block';
  }
});
</script>
"""


def _route_handler(html_when_logged_out: str):
    def handler(route):
        cookie_header = route.request.headers.get("cookie", "")
        body = ALREADY_LOGGED_IN_HTML if "session=valid" in cookie_header else html_when_logged_out

        route.fulfill(content_type="text/html", body=body)

    return handler


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        yield b
        b.close()


@pytest.fixture()
def project():
    p = project_store.create_project(ProjectCreate(name="__test_login_project__"))
    yield p
    project_store.delete_project(p.id)


@pytest.fixture()
def page(browser):
    pg = browser.new_page()
    pg.route(LOGIN_URL, _route_handler(LOGIN_FORM_HTML))
    pg.route(LOGIN_URL_2FA, _route_handler(LOGIN_FORM_2FA_HTML))
    yield pg
    pg.close()


@pytest.fixture()
def cookies_path_for(project):
    """Login's cookie jar is now keyed by CREDENTIAL, not by this workflow (see
    app/nodes/login.py) — a fixture factory since different tests use different
    credentials (login_credential, a locally-created bad_cred, ...)."""
    created = []

    def _for(credential_id: str):
        d = cookies_dir_for_credential(project.id, credential_id)
        if d.exists():
            shutil.rmtree(d)
        created.append(d)
        return d

    yield _for
    for d in created:
        if d.exists():
            shutil.rmtree(d)


@pytest.fixture()
def login_credential(project):
    cred = credential_store.create_credential(
        project.id, CredentialCreate(name="test login", type="login", value="alice:secret123")
    )
    yield cred
    credential_store.delete_credential(project.id, cred.id)


@pytest.fixture()
def totp_credential(project):
    # A syntactically valid base32 TOTP secret — pyotp.TOTP(...).now() just needs to
    # run and produce 6 digits; the fake page accepts any 6-digit code (see
    # LOGIN_FORM_2FA_HTML), so the secret's real value doesn't matter here.
    cred = credential_store.create_credential(
        project.id, CredentialCreate(name="test totp", type="totp", value="JBSWY3DPEHPK3PXP")
    )
    yield cred
    credential_store.delete_credential(project.id, cred.id)


def _ctx(project_id: str, params: dict, workflow_id: str = WORKFLOW_ID) -> CodegenContext:
    return CodegenContext(
        node_id="test_node",
        params=params,
        in_loop=False,
        project_id=project_id,
        workflow_id=workflow_id,
        target_var="page",
        node_label="Login",
    )


def _exec_fragment(page, fragment: str, ns: dict | None = None) -> dict:
    if ns is None:
        ns = {}
        exec(compile(HEADER, "<header>", "exec"), ns)
    ns["page"] = page
    exec(compile(fragment, "<fragment>", "exec"), ns)
    return ns


def _base_params(login_credential, **overrides) -> dict:
    params = {
        "url": LOGIN_URL,
        "credentialId": login_credential.id,
        "usernameSelector": "#user",
        "usernameSelectorType": "css",
        "passwordSelector": "#pass",
        "passwordSelectorType": "css",
        "submitSelector": "#go",
        "submitSelectorType": "css",
        "confirmSelector": "#dashboard",
        "confirmSelectorType": "css",
        "confirmTimeout": 5,
    }
    params.update(overrides)
    return params


# --- catalog / registry ---------------------------------------------------


def test_node_registered_with_expected_shape():
    spec = NODE_REGISTRY["login"]
    assert spec.label == "Login"
    assert spec.category == "browser"
    assert spec.icon == "log-in"
    assert spec.opens_block is False
    param_keys = {p.key for p in spec.params}
    assert {
        "url",
        "credentialId",
        "usernameSelector",
        "passwordSelector",
        "submitSelector",
        "confirmSelector",
        "has2FA",
        "reuseSavedSession",
    } <= param_keys
    reuse_field = next(p for p in spec.params if p.key == "reuseSavedSession")
    assert reuse_field.type == "boolean"
    assert reuse_field.default is True
    assert "cookiesFilename" not in param_keys  # cookie storage is now tied to the credential, not a filename


def test_get_node_catalog_includes_login():
    from app.services.workflow_reconstructor import build_node_catalog

    catalog = build_node_catalog()
    entry = next(c for c in catalog if c["type"] == "login")
    assert entry["category"] == "browser"
    assert entry["icon"] == "log-in"


def test_validate_workflow_accepts_open_browser_login(project, login_credential):
    nodes = [
        WFNode(id="n1", type="open_browser", position=Position(x=0, y=0), params={"headless": True}),
        WFNode(
            id="n2",
            type="login",
            position=Position(x=1, y=0),
            params={
                "url": "https://example.com/login",
                "credentialId": login_credential.id,
                "usernameSelector": "#user",
                "passwordSelector": "#pass",
                "submitSelector": "#go",
                "confirmSelector": "#dashboard",
            },
        ),
    ]
    edges = [WFEdge(id="e1", source="n1", target="n2")]
    script = generate_script(nodes, edges, project.id, workflow_id=WORKFLOW_ID)
    compile(script, "<generated>", "exec")


def test_missing_url_raises_codegen_error(project, login_credential):
    with pytest.raises(CodegenError, match="URL"):
        codegen_login(_ctx(project.id, _base_params(login_credential, url="")))


def test_not_demoable_live():
    """login can never be demoed live via MCP's demo_node — even with a real
    credential id, codegen's real fragment has nested if/try blocks (the
    cookie-fast-path check, the optional 2FA branch) that can't be sent to a paused
    pdb session one line at a time, and no MCP client can ever supply a real
    credential anyway (no credential-listing tool). is_demoable() catches this
    explicitly with a clear message rather than letting either problem surface as a
    raw CodegenError or a generic 'indented code block' error (see
    app/mcp/live_sessions.py::is_demoable)."""
    from app.mcp import live_sessions

    spec = NODE_REGISTRY["login"]
    assert spec.demo_codegen is None

    demoable, reason = live_sessions.is_demoable("login")
    assert demoable is False
    assert "credential" in (reason or "")


# --- real functional behavior ----------------------------------------------


def test_first_run_fills_form_and_saves_cookies(project, page, login_credential, cookies_path_for):
    cookies_path = cookies_path_for(login_credential.id)
    fragment = codegen_login(_ctx(project.id, _base_params(login_credential, resultVar="r")))
    ns = _exec_fragment(page, fragment)

    assert page.locator("#dashboard").is_visible()
    assert ns["r"] == {"alreadyLoggedIn": False}

    saved = cookies_path / "cookies.json"
    assert saved.exists()
    data = json.loads(saved.read_text(encoding="utf-8"))
    assert any(c["name"] == "session" and c["value"] == "valid" for c in data)


def test_node_registered_with_typing_option_params():
    spec = NODE_REGISTRY["login"]
    param_keys = {p.key for p in spec.params}
    assert {"clearFirst", "simulateTyping"} <= param_keys


def test_codegen_includes_clear_and_press_sequentially_for_every_field(project, login_credential, totp_credential):
    fragment = codegen_login(
        _ctx(
            project.id,
            _base_params(
                login_credential,
                has2FA=True,
                twoFaCodeSelector="#code",
                totpCredentialId=totp_credential.id,
                clearFirst=True,
                simulateTyping=True,
            ),
        )
    )
    assert fragment.count(".clear()") == 3  # username, password, 2FA code
    assert fragment.count(".press_sequentially(") == 3
    assert ".fill(" not in fragment


def test_clear_first_and_simulate_typing_still_log_in_successfully(project, page, login_credential, cookies_path_for):
    cookies_path_for(login_credential.id)
    fragment = codegen_login(
        _ctx(project.id, _base_params(login_credential, resultVar="r", clearFirst=True, simulateTyping=True))
    )
    ns = _exec_fragment(page, fragment)

    assert page.locator("#dashboard").is_visible()
    assert ns["r"] == {"alreadyLoggedIn": False}


def test_second_run_skips_form_using_saved_cookies(project, browser, page, login_credential, cookies_path_for):
    cookies_path_for(login_credential.id)
    # First run: real login, saves cookies to disk.
    first_fragment = codegen_login(_ctx(project.id, _base_params(login_credential)))
    _exec_fragment(page, first_fragment)

    # Second run: a totally fresh page/context that never logged in itself — only
    # the Login node's own cookie-loading step (at the top of its fragment) can make
    # this work.
    fresh_page = browser.new_page()
    fresh_page.route(LOGIN_URL, _route_handler(LOGIN_FORM_HTML))
    try:
        second_fragment = codegen_login(_ctx(project.id, _base_params(login_credential, resultVar="r2")))
        ns = _exec_fragment(fresh_page, second_fragment)
        assert ns["r2"] == {"alreadyLoggedIn": True}
        assert fresh_page.locator("#dashboard").is_visible()
        assert fresh_page.locator("#user").count() == 0  # the login FORM never rendered at all
    finally:
        fresh_page.close()


def test_reuse_saved_session_false_forces_a_fresh_login_despite_saved_cookies(
    project, browser, page, login_credential, cookies_path_for
):
    # Mirrors microsoft_login's reuseSavedSession toggle (app/nodes/microsoft_login.py)
    # — added here for consistency after a user noticed the plain Login node had no
    # way to force a fresh login even when a saved (possibly stale) session exists.
    cookies_path_for(login_credential.id)
    first_fragment = codegen_login(_ctx(project.id, _base_params(login_credential)))
    _exec_fragment(page, first_fragment)

    fresh_page = browser.new_page()
    fresh_page.route(LOGIN_URL, _route_handler(LOGIN_FORM_HTML))
    try:
        second_fragment = codegen_login(
            _ctx(project.id, _base_params(login_credential, resultVar="r2", reuseSavedSession=False))
        )
        ns = _exec_fragment(fresh_page, second_fragment)
        assert ns["r2"] == {"alreadyLoggedIn": False}
        assert fresh_page.locator("#user").count() == 1  # the login FORM DID render this time
        assert fresh_page.locator("#dashboard").is_visible()  # still logs in for real and succeeds
    finally:
        fresh_page.close()


def test_session_is_shared_with_a_different_workflow_using_the_same_credential(
    project, browser, page, login_credential, cookies_path_for
):
    cookies_path_for(login_credential.id)
    # Logged in from WORKFLOW_ID...
    first_fragment = codegen_login(_ctx(project.id, _base_params(login_credential)))
    _exec_fragment(page, first_fragment)

    # ...picked up by a Login node in a COMPLETELY DIFFERENT workflow, same credential —
    # this is the whole point: no shared workflow needed, just the same credential.
    fresh_page = browser.new_page()
    fresh_page.route(LOGIN_URL, _route_handler(LOGIN_FORM_HTML))
    try:
        other_fragment = codegen_login(
            _ctx(project.id, _base_params(login_credential, resultVar="r2"), workflow_id="__a_totally_different_workflow__")
        )
        ns = _exec_fragment(fresh_page, other_fragment)
        assert ns["r2"] == {"alreadyLoggedIn": True}
        assert fresh_page.locator("#user").count() == 0  # the login FORM never rendered at all
    finally:
        fresh_page.close()


def test_wrong_password_times_out_without_saving_cookies(project, page, cookies_path_for):
    bad_cred = credential_store.create_credential(
        project.id, CredentialCreate(name="bad", type="login", value="alice:wrong-password")
    )
    cookies_path = cookies_path_for(bad_cred.id)
    try:
        fragment = codegen_login(_ctx(project.id, _base_params(bad_cred, confirmTimeout=2)))
        with pytest.raises(Exception):
            _exec_fragment(page, fragment)
        assert not (cookies_path / "cookies.json").exists()
    finally:
        credential_store.delete_credential(project.id, bad_cred.id)


def test_2fa_flow(project, page, login_credential, totp_credential, cookies_path_for):
    cookies_path = cookies_path_for(login_credential.id)
    fragment = codegen_login(
        _ctx(
            project.id,
            _base_params(
                login_credential,
                url=LOGIN_URL_2FA,
                has2FA=True,
                totpCredentialId=totp_credential.id,
                twoFaCodeSelector="#code",
                twoFaCodeSelectorType="css",
                twoFaSubmitSelector="#code-submit",
                twoFaSubmitSelectorType="css",
            ),
        )
    )
    _exec_fragment(page, fragment)
    assert page.locator("#dashboard").is_visible()

    saved = cookies_path / "cookies.json"
    assert saved.exists()
