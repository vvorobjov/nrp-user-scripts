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

from conftest import BASE_URL, FS_USER, FS_PASSWORD

pytestmark = pytest.mark.ui


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
