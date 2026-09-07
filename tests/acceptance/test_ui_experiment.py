# [EBR2-96] Browser/UI acceptance suite (pure Playwright in pytest).
#
# Drives the REAL frontend the way a person does: log in through the proxy's FS
# login page, open a husky_braitenberg experiment from the overview, and confirm
# the workbench actually runs it — the simulation clock advances and no error is
# shown. This is the human-shaped counterpart of the CLI/REST suite; together
# they prove the containerized stack works end-to-end through both surfaces.
#
# Runs headless in the suite container sharing haproxy's network namespace, so
# the frontend's build-time-baked http://localhost:9000 proxy/MQTT URLs resolve.
import time

import pytest

from conftest import BASE_URL, FS_USER, FS_PASSWORD, HUSKY_CONFIG

pytestmark = pytest.mark.ui

# The error dialog (error-dialog.js) renders only while an error is queued, so
# its mere presence is a failure signal. This exact message is raised by the
# TF/files editor (tf-editor.js dataError) when the experiment files fail to
# load — the regression EBR2-122 guards against.
ERROR_DIALOG = ".error-dialog"
FILES_LOAD_ERROR = "Could not load the experiment files."


def _login(page):
    """Authenticate through the proxy FS login page and land on the entry page."""
    page.goto(BASE_URL, wait_until="domcontentloaded", timeout=30000)
    # The frontend (enableOIDC=false) redirects to the proxy FS login form.
    page.wait_for_selector("#username", timeout=20000)
    page.fill("#username", FS_USER)
    page.fill("#password", FS_PASSWORD)
    page.click("#submit")
    # Back on the SPA: the header (with the EXPERIMENTS link) is the logged-in marker.
    page.wait_for_selector("text=EXPERIMENTS", timeout=30000)


def _sim_time_boxes(page):
    """Current text of the workbench time boxes (Real / Simulation / Left)."""
    return [el.inner_text().strip()
            for el in page.query_selector_all(".experiment-time-box")
            if el.is_visible()]


def _open_husky_experiment(page):
    """Log in and open a husky experiment's workbench (the shared UI preamble).

    Mirrors the steps a person takes: log in, open the Experiments overview,
    select a husky entry and Open it, then land on the workbench route.
    """
    _login(page)

    # Open the Experiments overview (My Experiments tab is the default).
    page.click("text=EXPERIMENTS")
    page.wait_for_selector(".list-entry-wrapper", timeout=30000)

    # Select the first husky experiment entry, then Open its workbench.
    page.locator(".list-entry-wrapper", has_text="husky").first.click()
    page.get_by_role("button", name="Open").first.click()
    page.wait_for_url("**/experiment/**", timeout=30000)


def _error_dialog_messages(page):
    """Messages of any error dialog currently on screen (empty list when none)."""
    return [el.inner_text().strip()
            for el in page.query_selector_all(f"{ERROR_DIALOG} .error-dialog-message")]


def _assert_no_error_dialog(page, context):
    """Fail if an error dialog (or the files-load error text) is displayed."""
    assert page.query_selector(ERROR_DIALOG) is None, \
        f"an error dialog is shown {context}: {_error_dialog_messages(page) or '(no message)'}"
    assert page.query_selector(f"text={FILES_LOAD_ERROR}") is None, \
        f'"{FILES_LOAD_ERROR}" is shown {context}'


@pytest.fixture
def ui_cleanup(nrp, husky_experiment):
    """Ensure at least one husky experiment exists (husky_experiment), and stop
    whatever simulation the UI launches once the test is done."""
    yield
    nrp.stop_all_running()


def test_login_reaches_dashboard(page):
    """A user can log in through the FS login page and reach the dashboard."""
    _login(page)
    assert page.query_selector("text=EXPERIMENTS") is not None


def test_launch_husky_through_ui(page, ui_cleanup):
    """Launch a husky experiment from the workbench and confirm it actually runs.

    Steps a person takes: log in, open the Experiments overview, pick a husky
    experiment, Open it, then in the workbench hit Initialize (creates the
    simulation) and Start (Play). We assert no error status is shown and the
    simulation clock advances — proving nrp-core is stepping behind the UI.
    """
    _open_husky_experiment(page)

    # Initialize the simulation (creates it on the backend), then Start it.
    page.wait_for_selector('button[title="Initialize experiment"]:not([disabled])', timeout=30000)
    page.locator('button[title="Initialize experiment"]').first.click()
    page.wait_for_selector('button[title="Start"]:not([disabled])', timeout=90000)
    page.locator('button[title="Start"]').first.click()

    # The time boxes confirm the workbench is wired to the running simulation.
    page.wait_for_selector(".experiment-time-box", timeout=30000)

    # No error status surfaced while launching/running.
    assert page.query_selector(".simulation-status-error") is None, \
        "workbench shows a simulation error status"

    # The experiment actually runs: a time box advances within a few seconds.
    before = _sim_time_boxes(page)
    advanced = False
    deadline = time.time() + 40
    while time.time() < deadline:
        time.sleep(4)
        if _sim_time_boxes(page) != before:
            advanced = True
            break
    assert advanced, f"simulation clock did not advance in the UI (time boxes stuck at {before})"

    # Cheap regression net: no error dialog surfaced anywhere in the launch flow.
    _assert_no_error_dialog(page, "at the end of the launch flow")


def test_experiment_files_panel_loads(page, husky_experiment):
    """Open the 'Edit experiment files' panel and confirm the files load cleanly.

    Regression net for EBR2-122: a "Could not load the experiment files."
    TypeError shipped because the launch test opened the workbench but never
    opened the files / TF-editor panel and never asserted the absence of an
    error dialog. The panel reads the experiment's storage files independent of
    a running simulation, so opening the workbench is enough to exercise it — no
    Initialize/Start needed.
    """
    _open_husky_experiment(page)

    # The 'Edit experiment files' (TF editor) panel is the workbench's default
    # flexlayout tab, so it opens automatically. Its shell renders whether or not
    # the file load succeeds, so waiting for it confirms the panel opened. We do
    # not click the tab: a failed load pops a modal that would (correctly) block
    # the click, so the failure is asserted below instead of hanging on it.
    page.wait_for_selector(".flexlayout__tab_button:has-text('Edit experiment files')", timeout=30000)
    page.wait_for_selector(".tf-editor-container", timeout=30000)

    # Wait for the load to resolve: either the populated file selector (success)
    # or the error dialog (failure), so a broken load fails here with a clear
    # message instead of timing out.
    page.wait_for_selector(
        f'select[name="selectTFFile"] option[value="{HUSKY_CONFIG}"], {ERROR_DIALOG}',
        state="attached", timeout=30000)

    # (a) No error dialog / "Could not load the experiment files." surfaced.
    _assert_no_error_dialog(page, "after opening the experiment files panel")

    # (b) The files panel listed the experiment config file.
    assert page.query_selector(f'select[name="selectTFFile"] option[value="{HUSKY_CONFIG}"]') is not None, \
        f"the file selector does not list {HUSKY_CONFIG}"
