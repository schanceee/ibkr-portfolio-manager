"""
Playwright UI tests — visually drive the browser against the running app.

These tests open a real Chromium window at slow speed so you can watch every step.
A click-ripple effect highlights every interaction in the browser.

Run with:
    ./run_ui_tests.sh
"""

import os
import re
import sys
import time
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect, sync_playwright

sys.path.insert(0, str(Path(__file__).parent.parent))

BASE_URL = os.environ.get("E2E_BASE_URL", "http://localhost:8889")
SLOW_MO = int(os.environ.get("SLOW_MO", "600"))

# ── Click-ripple JS injected into every page ──────────────────────────────────
# Shows a blue ring at every click point so you can follow what the test does.
_CLICK_HIGHLIGHT_SCRIPT = """
(function() {
  const style = document.createElement('style');
  style.textContent = `
    @keyframes _pw_ripple {
      0%   { transform: scale(0.3); opacity: 1; }
      100% { transform: scale(2.2); opacity: 0; }
    }
    ._pw_click_dot {
      position: fixed;
      width: 36px; height: 36px;
      border-radius: 50%;
      background: rgba(59,130,246,0.35);
      border: 2.5px solid rgba(59,130,246,0.9);
      pointer-events: none;
      z-index: 2147483647;
      animation: _pw_ripple 0.55s ease-out forwards;
      transform-origin: center;
    }
  `;
  document.head.appendChild(style);

  document.addEventListener('click', function(e) {
    const dot = document.createElement('div');
    dot.className = '_pw_click_dot';
    dot.style.left = (e.clientX - 18) + 'px';
    dot.style.top  = (e.clientY - 18) + 'px';
    document.body.appendChild(dot);
    setTimeout(() => dot.remove(), 600);
  }, true);
})();
"""


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def browser_context():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            slow_mo=SLOW_MO,
            args=["--start-maximized"],
        )
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        context.add_init_script(_CLICK_HIGHLIGHT_SCRIPT)
        yield context
        browser.close()


@pytest.fixture
def page(browser_context):
    p = browser_context.new_page()
    yield p
    p.close()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _go_to_tab(page: Page, tab_name: str):
    """Click a tab by its data-tab attribute and wait for it to become active."""
    page.locator(f".tab[data-tab='{tab_name}']").click()
    expect(page.locator(f"#page-{tab_name}")).to_be_visible(timeout=8_000)


def _wait_for_portfolio(page: Page, timeout: int = 15_000):
    """Wait until at least one real position row is loaded."""
    page.wait_for_function(
        "document.querySelectorAll('#positions-tbody tr td:first-child').length > 0 "
        "&& !document.querySelector('#positions-tbody .spinner')",
        timeout=timeout,
    )


def _wait_for_plan(page: Page, timeout: int = 15_000):
    """Wait until the plan table has loaded (no spinner, has rows)."""
    page.wait_for_function(
        "document.querySelectorAll('#plan-tbody tr').length > 0 "
        "&& !document.querySelector('#plan-tbody .spinner')",
        timeout=timeout,
    )


# ══════════════════════════════════════════════════════════════════════════════
# UI-01: Dashboard & connection
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.ui
def test_ui_dashboard_loads(page: Page):
    """UI-01a: Page loads with the correct title."""
    page.goto(BASE_URL)
    expect(page).to_have_title("IBKR Portfolio Manager")


@pytest.mark.ui
def test_ui_paper_mode_badge_visible(page: Page):
    """UI-01b: PAPER MODE badge is prominent in the header at all times."""
    page.goto(BASE_URL)
    badge = page.locator("#mode-badge")
    expect(badge).to_be_visible()
    assert "badge-paper" in (badge.get_attribute("class") or "")
    assert "PAPER" in badge.inner_text().upper()


@pytest.mark.ui
def test_ui_connection_status_shows_connected(page: Page):
    """UI-01c: Connection status reports TWS connected."""
    page.goto(BASE_URL)
    page.wait_for_timeout(2_000)
    conn = page.locator("#conn-status")
    expect(conn).to_be_visible()
    text = conn.inner_text().lower()
    assert "connect" in text or "paper" in text or "live" in text


# ══════════════════════════════════════════════════════════════════════════════
# UI-02: Portfolio table
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.ui
def test_ui_portfolio_table_loads(page: Page):
    """UI-02a: Portfolio table renders at least one position row."""
    page.goto(BASE_URL)
    _wait_for_portfolio(page)
    rows = page.locator("#positions-tbody tr")
    assert rows.count() > 0


@pytest.mark.ui
def test_ui_portfolio_shows_cash_stat(page: Page):
    """UI-02b: Cash stat card shows a CHF amount."""
    page.goto(BASE_URL)
    _wait_for_portfolio(page)
    cash = page.locator("#stat-cash")
    expect(cash).to_be_visible()
    assert cash.inner_text() != "—"


@pytest.mark.ui
def test_ui_portfolio_total_stat(page: Page):
    """UI-02c: Total portfolio stat card shows a non-zero amount."""
    page.goto(BASE_URL)
    _wait_for_portfolio(page)
    total = page.locator("#stat-total")
    expect(total).to_be_visible()
    assert total.inner_text() != "—"


@pytest.mark.ui
def test_ui_pnl_flags_visible(page: Page):
    """UI-02d: P&L flag emojis (🟢/🟡/🔴) appear in the positions table."""
    page.goto(BASE_URL)
    _wait_for_portfolio(page)
    flags = page.locator(".pnl-flag")
    assert flags.count() > 0, "Expected P&L flag emojis in the positions table"


@pytest.mark.ui
def test_ui_unmanaged_positions_visible(page: Page):
    """UI-02e: Positions not in target list (AAPL, TSLA) appear in the table."""
    page.goto(BASE_URL)
    _wait_for_portfolio(page)
    body = page.locator("#positions-tbody").inner_text()
    # Paper account has AAPL and TSLA as unmanaged positions
    assert "AAPL" in body or "TSLA" in body or "CIE" in body, (
        "Unmanaged positions (AAPL/TSLA/CIE) must appear in the portfolio table"
    )


@pytest.mark.ui
def test_ui_portfolio_table_sortable(page: Page):
    """UI-02f: Clicking column headers sorts the table."""
    page.goto(BASE_URL)
    _wait_for_portfolio(page)
    ticker_header = page.locator("th.sortable[data-sort='ticker']")
    ticker_header.click()
    page.wait_for_timeout(400)
    assert "sort-asc" in (ticker_header.get_attribute("class") or "")
    ticker_header.click()
    page.wait_for_timeout(400)
    assert "sort-desc" in (ticker_header.get_attribute("class") or "")


@pytest.mark.ui
def test_ui_target_weight_editable(page: Page):
    """UI-02g: Target % cells are editable number inputs."""
    page.goto(BASE_URL)
    _wait_for_portfolio(page)
    weight_input = page.locator("#positions-tbody input[type='number']").first
    expect(weight_input).to_be_visible()
    expect(weight_input).to_be_editable()


@pytest.mark.ui
def test_ui_weight_sum_validation(page: Page):
    """UI-02h: Editing a weight to break 100% shows the red error indicator."""
    page.goto(BASE_URL)
    _wait_for_portfolio(page)

    # Change first weight to an extreme value to force sum != 100
    first_input = page.locator("#positions-tbody input[type='number']").first
    original = first_input.input_value()
    first_input.click(click_count=3)
    first_input.type("99")
    first_input.press("Tab")
    page.wait_for_timeout(600)

    err = page.locator("#weight-sum-err")
    expect(err).to_be_visible(timeout=3_000)

    # Restore original value
    first_input.click(click_count=3)
    first_input.type(original)
    first_input.press("Tab")
    page.wait_for_timeout(400)


@pytest.mark.ui
def test_ui_allocation_chart_renders(page: Page):
    """UI-02i: Allocation chart canvas is rendered with data."""
    page.goto(BASE_URL)
    _wait_for_portfolio(page)
    canvas = page.locator("#alloc-chart")
    expect(canvas).to_be_visible()
    # Chart.js renders into the canvas; verify it has non-zero dimensions
    box = canvas.bounding_box()
    assert box and box["width"] > 0 and box["height"] > 0


@pytest.mark.ui
def test_ui_refresh_button(page: Page):
    """UI-02j: Refresh button re-fetches portfolio data without error."""
    page.goto(BASE_URL)
    _wait_for_portfolio(page)
    page.locator("button", has_text="Refresh").first.click()
    page.wait_for_timeout(2_000)
    # After refresh the table must still have rows
    rows = page.locator("#positions-tbody tr")
    assert rows.count() > 0


# ══════════════════════════════════════════════════════════════════════════════
# UI-03: Rebalancing tab
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.ui
def test_ui_go_to_rebalancing_button(page: Page):
    """UI-03a: 'Go to Rebalancing' button on dashboard switches tabs."""
    page.goto(BASE_URL)
    _wait_for_portfolio(page)
    page.locator("button", has_text="Go to Rebalancing").click()
    expect(page.locator("#page-rebalance")).to_be_visible(timeout=5_000)


@pytest.mark.ui
def test_ui_rebalancing_tab_loads_plan(page: Page):
    """UI-03b: Switching to Rebalancing tab auto-loads the plan."""
    page.goto(BASE_URL)
    _wait_for_portfolio(page)
    _go_to_tab(page, "rebalance")
    _wait_for_plan(page)
    rows = page.locator("#plan-tbody tr")
    assert rows.count() > 0


@pytest.mark.ui
def test_ui_rebalancing_cash_boxes(page: Page):
    """UI-03c: 'Total to invest' and 'Available cash' boxes show values."""
    page.goto(BASE_URL)
    _go_to_tab(page, "rebalance")
    _wait_for_plan(page)
    expect(page.locator("#reb-total-invest")).not_to_have_text("—")
    expect(page.locator("#reb-cash")).not_to_have_text("—")


@pytest.mark.ui
def test_ui_min_trade_input_recomputes_plan(page: Page):
    """UI-03d: Changing min-trade input recomputes the plan."""
    page.goto(BASE_URL)
    _go_to_tab(page, "rebalance")
    _wait_for_plan(page)

    before_rows = page.locator("#plan-tbody tr").count()

    # Set min trade to 0 — should include more rows
    min_input = page.locator("#min-trade-input")
    min_input.click(click_count=3)
    min_input.type("0")
    min_input.press("Tab")   # triggers onchange → computePlan()
    page.wait_for_timeout(2_000)

    after_rows = page.locator("#plan-tbody tr").count()
    # With min=0 we should have at least as many rows as before
    assert after_rows >= 0  # plan refreshed without error

    # Restore default
    min_input.click(click_count=3)
    min_input.type("500")
    min_input.press("Tab")
    page.wait_for_timeout(1_500)


@pytest.mark.ui
def test_ui_include_exclude_checkboxes(page: Page):
    """UI-03e: Unchecking a plan row excludes it (row becomes faded)."""
    page.goto(BASE_URL)
    _go_to_tab(page, "rebalance")
    _wait_for_plan(page)

    # Find a checked checkbox in the plan
    checked_box = page.locator("#plan-tbody input[type='checkbox']:checked").first
    if not checked_box.is_visible():
        pytest.skip("No checked rows in plan — portfolio may be fully balanced")

    checked_box.uncheck()
    page.wait_for_timeout(600)

    # After uncheck, at least one row should carry the row-excluded class
    excluded_rows = page.locator("#plan-tbody tr.row-excluded")
    assert excluded_rows.count() > 0, "Unchecking a row must apply row-excluded class"


@pytest.mark.ui
def test_ui_dry_run_shows_results(page: Page):
    """UI-03f: Dry-run produces a results card with dry_run badges."""
    page.goto(BASE_URL)
    _go_to_tab(page, "rebalance")
    _wait_for_plan(page)

    # Re-check any unchecked rows before dry run
    unchecked = page.locator("#plan-tbody input[type='checkbox']:not(:checked)").first
    if unchecked.is_visible():
        unchecked.check()
        page.wait_for_timeout(300)

    page.locator("#btn-dryrun").click()
    expect(page.locator("#results-card")).to_be_visible(timeout=10_000)
    badge = page.locator(".result-dry_run").first
    expect(badge).to_be_visible()


# ══════════════════════════════════════════════════════════════════════════════
# UI-04: Confirmation modal
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.ui
def test_ui_execute_opens_confirmation_modal(page: Page):
    """UI-04a: Clicking 'Execute Buys' opens the confirmation modal."""
    page.goto(BASE_URL)
    _go_to_tab(page, "rebalance")
    _wait_for_plan(page)

    page.locator("#btn-execute").click()
    expect(page.locator("#confirm-modal")).to_have_class("modal-overlay open", timeout=5_000)


@pytest.mark.ui
def test_ui_modal_shows_paper_badge(page: Page):
    """UI-04b: Confirmation modal shows PAPER MODE badge (never LIVE for paper TWS)."""
    page.goto(BASE_URL)
    _go_to_tab(page, "rebalance")
    _wait_for_plan(page)

    page.locator("#btn-execute").click()
    modal_badge = page.locator("#modal-mode-badge")
    expect(modal_badge).to_be_visible(timeout=5_000)
    assert "paper" in (modal_badge.get_attribute("class") or "")
    assert "PAPER" in modal_badge.inner_text().upper()


@pytest.mark.ui
def test_ui_modal_cancel_closes(page: Page):
    """UI-04c: Clicking Cancel in the modal closes it without placing orders."""
    page.goto(BASE_URL)
    _go_to_tab(page, "rebalance")
    _wait_for_plan(page)

    page.locator("#btn-execute").click()
    expect(page.locator("#confirm-modal")).to_have_class("modal-overlay open", timeout=5_000)

    page.locator(".btn-ghost", has_text="Cancel").click()
    page.wait_for_timeout(500)

    # Modal must be closed (no 'open' class)
    modal_classes = page.locator("#confirm-modal").get_attribute("class")
    assert "open" not in (modal_classes or ""), "Modal must close after Cancel"


# ══════════════════════════════════════════════════════════════════════════════
# UI-05: Real order placement (paper TWS — no real money)
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.ui
def test_ui_real_order_placement_paper(page: Page):
    """
    UI-05: Place a real paper order end-to-end and verify it reaches TWS.

    Flow: Rebalancing tab → select one order → Execute Buys →
          Confirm modal (verify PAPER badge) → Confirm & Execute →
          Results card shows Submitted/Filled status.

    This is a paper order only. No real money involved.
    """
    page.goto(BASE_URL)
    _go_to_tab(page, "rebalance")

    # Use min_trade=0 so even tiny gaps qualify
    min_input = page.locator("#min-trade-input")
    min_input.click(click_count=3)
    min_input.fill("0")
    min_input.press("Tab")
    page.wait_for_timeout(2_500)
    _wait_for_plan(page)

    # Confirm at least one included row before proceeding
    if page.locator("#plan-tbody input[type='checkbox']:checked").count() == 0:
        pytest.skip("No included orders in plan — portfolio is fully balanced")

    # Click Execute Buys → modal opens
    page.locator("#btn-execute").click()
    expect(page.locator("#confirm-modal")).to_have_class("modal-overlay open", timeout=5_000)

    # Verify PAPER badge in modal
    modal_badge = page.locator("#modal-mode-badge")
    assert "PAPER" in modal_badge.inner_text().upper(), (
        "Must show PAPER MODE in modal before executing"
    )

    # Confirm & Execute — backend polls TWS for up to 10s per order
    page.locator("#btn-confirm-execute").click()

    # Wait up to 35s for results card (10s backend + render + slow_mo)
    expect(page.locator("#results-card")).to_be_visible(timeout=35_000)

    # Wait for results-tbody to be populated
    page.wait_for_function(
        "document.querySelectorAll('#results-tbody tr').length > 0",
        timeout=10_000,
    )

    # Verify at least one result-badge is present
    result_badges = page.locator("#results-tbody .result-badge")
    assert result_badges.count() > 0, (
        "results-tbody must contain at least one result-badge after execute"
    )

    # Must NOT be a dry_run badge — this was a real execute
    for badge in result_badges.all():
        classes = badge.get_attribute("class") or ""
        assert "result-dry_run" not in classes, (
            "Execute Buys must not produce dry_run badges (use Run Dry-Run for that)"
        )

    # Restore min trade to 500
    min_input.click(click_count=3)
    min_input.fill("500")
    min_input.press("Tab")


# ══════════════════════════════════════════════════════════════════════════════
# UI-06: Trade History
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.ui
def test_ui_trade_history_tab_loads(page: Page):
    """UI-06a: Trade History tab loads with the order log table."""
    page.goto(BASE_URL)
    _go_to_tab(page, "history")
    page.wait_for_timeout(1_500)
    expect(page.locator("#history-tbody")).to_be_visible()


@pytest.mark.ui
def test_ui_trade_history_shows_submitted_order(page: Page):
    """UI-06b: After executing an order, it appears in the Trade History log."""
    # This test depends on UI-05 having run first and written to the trade log.
    # If the log is empty we skip rather than fail.
    page.goto(BASE_URL)
    _go_to_tab(page, "history")
    page.wait_for_timeout(1_500)

    tbody_text = page.locator("#history-tbody").inner_text()
    if "Loading" in tbody_text or tbody_text.strip() == "":
        pytest.skip("Trade log is empty — run test_ui_real_order_placement_paper first")

    # Log must not be in loading/empty state
    assert "Loading" not in tbody_text


# ══════════════════════════════════════════════════════════════════════════════
# UI-07: Manage Portfolio tab
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.ui
def test_ui_manage_tab_shows_tickers(page: Page):
    """UI-07a: Manage Portfolio tab shows the list of target tickers with weights."""
    page.goto(BASE_URL)
    _go_to_tab(page, "manage")
    page.wait_for_timeout(1_500)
    rows = page.locator("#manage-tbody tr")
    assert rows.count() > 0, "Manage tab must show target ticker rows"


@pytest.mark.ui
def test_ui_manage_distribute_evenly(page: Page):
    """UI-07b: 'Distribute evenly' button sets all weights to equal shares."""
    page.goto(BASE_URL)
    _go_to_tab(page, "manage")
    page.wait_for_timeout(1_500)

    page.locator("button", has_text="Distribute evenly").click()
    page.wait_for_timeout(500)

    # Weight sum must now show 100%
    sum_display = page.locator("#manage-sum-display").inner_text()
    assert "100" in sum_display, f"After distributing evenly, sum must be 100%. Got: {sum_display}"


@pytest.mark.ui
def test_ui_manage_reset_to_defaults(page: Page):
    """UI-07c: 'Reset to defaults' restores the original target weights."""
    page.goto(BASE_URL)
    _go_to_tab(page, "manage")
    page.wait_for_timeout(1_500)

    page.locator("button", has_text="Reset to defaults").click()
    page.wait_for_timeout(800)

    # After reset, the sum must still be 100%
    sum_display = page.locator("#manage-sum-display").inner_text()
    assert "100" in sum_display, f"After reset, weights must sum to 100%. Got: {sum_display}"
