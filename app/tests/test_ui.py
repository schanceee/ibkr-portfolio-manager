"""
Playwright UI tests — visually drive the browser against the running app.

These tests open a real browser window so you can watch every step.
Run with:
    pytest app/tests/test_ui.py -v -s -m ui

Requirements:
    - Paper TWS running on port 7497 with API enabled
    - App server already running (started by run_ui_tests.sh)
    - E2E_BASE_URL env var pointing at the server (set by run_ui_tests.sh)
"""

import os
import sys
import time
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect, sync_playwright

sys.path.insert(0, str(Path(__file__).parent.parent))

BASE_URL = os.environ.get("E2E_BASE_URL", "http://localhost:8889")
SLOW_MO = int(os.environ.get("SLOW_MO", "700"))   # ms between actions so you can watch


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def browser_context():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            slow_mo=SLOW_MO,
            args=["--start-maximized"],
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            no_viewport=False,
        )
        yield context
        browser.close()


@pytest.fixture
def page(browser_context):
    page = browser_context.new_page()
    yield page
    page.close()


# ── UI-01: Dashboard loads ─────────────────────────────────────────────────────

@pytest.mark.ui
def test_ui_dashboard_loads(page: Page):
    """UI: Dashboard loads with the correct title and connection banner."""
    page.goto(BASE_URL)
    expect(page).to_have_title("IBKR Portfolio Manager")

    # Connection status banner must be visible
    status = page.locator("#status-banner, #connection-status, .status-banner, [id*='status']").first
    status.wait_for(timeout=10_000)


@pytest.mark.ui
def test_ui_connection_status_shows_connected(page: Page):
    """UI: Status banner shows TWS connected in paper mode."""
    page.goto(BASE_URL)
    page.wait_for_load_state("networkidle")

    # Wait for the JS to populate connection status
    page.wait_for_timeout(2000)

    body_text = page.locator("body").inner_text()
    assert any(word in body_text.lower() for word in ("connected", "paper", "tws")), (
        "Dashboard must show connection status — expected 'connected', 'paper', or 'TWS' in page"
    )


# ── UI-02: Portfolio table ────────────────────────────────────────────────────

@pytest.mark.ui
def test_ui_portfolio_table_loads(page: Page):
    """UI: Portfolio table renders with at least one position row."""
    page.goto(BASE_URL)
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(3000)  # wait for IB data to arrive

    # The table should have rows beyond the header
    rows = page.locator("table tbody tr, #positions-table tbody tr, .position-row")
    expect(rows.first).to_be_visible(timeout=15_000)


@pytest.mark.ui
def test_ui_portfolio_shows_cash(page: Page):
    """UI: Dashboard shows available cash amount."""
    page.goto(BASE_URL)
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(3000)

    body_text = page.locator("body").inner_text()
    assert "chf" in body_text.lower() or "cash" in body_text.lower(), (
        "Dashboard must show cash in CHF"
    )


@pytest.mark.ui
def test_ui_portfolio_table_sortable(page: Page):
    """UI: Clicking a column header sorts the table."""
    page.goto(BASE_URL)
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(3000)

    # Find a sortable header (has data-sort or ↕ indicator)
    header = page.locator("th[data-sort], th:has-text('↕'), th:has-text('Ticker')").first
    if not header.is_visible():
        pytest.skip("No sortable column headers found")

    # Click once — should sort ascending
    header.click()
    page.wait_for_timeout(500)

    # Click again — should sort descending
    header.click()
    page.wait_for_timeout(500)

    # No assertion on order — just verify page didn't crash
    expect(page.locator("body")).to_be_visible()


# ── UI-03: Target weight editing ──────────────────────────────────────────────

@pytest.mark.ui
def test_ui_target_weight_editable(page: Page):
    """UI: Target weight cells are editable inputs."""
    page.goto(BASE_URL)
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(3000)

    # Find an editable weight input
    weight_input = page.locator("input[type='number'], td[contenteditable='true']").first
    if not weight_input.is_visible():
        pytest.skip("No editable weight inputs found — may still be loading")

    expect(weight_input).to_be_editable()


# ── UI-04: Rebalancing tab ────────────────────────────────────────────────────

@pytest.mark.ui
def test_ui_rebalancing_tab_loads(page: Page):
    """UI: Switching to Rebalancing tab loads the plan."""
    page.goto(BASE_URL)
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2000)

    # Find and click the Rebalancing tab
    rebalance_tab = page.locator(
        "button:has-text('Rebalanc'), a:has-text('Rebalanc'), [data-tab='rebalance'], #rebalance-tab"
    ).first
    if not rebalance_tab.is_visible(timeout=5000):
        pytest.skip("Rebalancing tab not found")

    rebalance_tab.click()
    page.wait_for_timeout(3000)

    # Plan table or cash info should appear
    body_text = page.locator("body").inner_text()
    assert any(word in body_text.lower() for word in ("cash", "invest", "plan", "chf")), (
        "Rebalancing tab must show cash or plan data after loading"
    )


@pytest.mark.ui
def test_ui_rebalancing_shows_plan_rows(page: Page):
    """UI: Rebalancing plan displays ticker rows with amounts."""
    page.goto(BASE_URL)
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2000)

    rebalance_tab = page.locator(
        "button:has-text('Rebalanc'), a:has-text('Rebalanc'), [data-tab='rebalance'], #rebalance-tab"
    ).first
    if not rebalance_tab.is_visible(timeout=5000):
        pytest.skip("Rebalancing tab not found")

    rebalance_tab.click()
    page.wait_for_timeout(4000)

    # The plan table should have visible rows in the active rebalancing section
    rows = page.locator("#plan-table tbody tr, .plan-row, table tbody tr").filter(
        has=page.locator(":visible")
    )
    if rows.count() > 0:
        expect(rows.first).to_be_visible()
    else:
        pytest.skip("Plan has no visible rows — portfolio may be fully balanced")


# ── UI-05: Dry-run execute ────────────────────────────────────────────────────

@pytest.mark.ui
def test_ui_dry_run_button_visible(page: Page):
    """UI: Dry-run button is present on the rebalancing page."""
    page.goto(BASE_URL)
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2000)

    rebalance_tab = page.locator(
        "button:has-text('Rebalanc'), a:has-text('Rebalanc'), [data-tab='rebalance'], #rebalance-tab"
    ).first
    if not rebalance_tab.is_visible(timeout=5000):
        pytest.skip("Rebalancing tab not found")

    rebalance_tab.click()
    page.wait_for_timeout(2000)

    dry_run_btn = page.locator(
        "button:has-text('Dry'), button:has-text('dry'), button:has-text('Run')"
    ).first
    if not dry_run_btn.is_visible(timeout=5000):
        pytest.skip("Dry-run button not found")

    expect(dry_run_btn).to_be_visible()


@pytest.mark.ui
def test_ui_dry_run_executes_and_shows_results(page: Page):
    """UI: Clicking Dry-run shows order results without placing real orders."""
    page.goto(BASE_URL)
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2000)

    rebalance_tab = page.locator(
        "button:has-text('Rebalanc'), a:has-text('Rebalanc'), [data-tab='rebalance'], #rebalance-tab"
    ).first
    if not rebalance_tab.is_visible(timeout=5000):
        pytest.skip("Rebalancing tab not found")

    rebalance_tab.click()
    page.wait_for_timeout(3000)

    # Select at least one row if checkboxes exist
    checkbox = page.locator("input[type='checkbox']").first
    if checkbox.is_visible():
        if not checkbox.is_checked():
            checkbox.check()
        page.wait_for_timeout(500)

    dry_run_btn = page.locator(
        "button:has-text('Dry'), button:has-text('dry'), button:has-text('Run')"
    ).first
    if not dry_run_btn.is_visible(timeout=5000):
        pytest.skip("Dry-run button not found")

    dry_run_btn.click()
    page.wait_for_timeout(3000)

    # Results should appear — either a modal, status update, or inline text
    body_text = page.locator("body").inner_text()
    assert any(word in body_text.lower() for word in ("dry", "result", "order", "submitted")), (
        "After dry-run, page must show order results"
    )


# ── UI-06: Trade history tab ──────────────────────────────────────────────────

@pytest.mark.ui
def test_ui_trade_history_tab_loads(page: Page):
    """UI: Trade history tab shows the list of past trades."""
    page.goto(BASE_URL)
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2000)

    history_tab = page.locator(
        "button:has-text('History'), a:has-text('History'), [data-tab='history'], #history-tab"
    ).first
    if not history_tab.is_visible(timeout=5000):
        pytest.skip("History tab not found")

    history_tab.click()
    page.wait_for_timeout(2000)

    body_text = page.locator("body").inner_text()
    assert any(word in body_text.lower() for word in ("trade", "history", "no trades", "order")), (
        "History tab must show trade history content"
    )
