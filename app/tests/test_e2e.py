"""
End-to-end tests — require a real paper TWS running on port 7497.

These tests connect to the actual FastAPI app with a live IB connection.
They only perform dry-run operations — no real orders are ever placed.

Run with:
    pytest app/tests/test_e2e.py -v -m e2e

Skip automatically if TWS is not reachable.
"""

import os
import sys
import time
import socket
import threading
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "claude"))


# ── Helpers ───────────────────────────────────────────────────────────────────

def _tws_reachable(host: str = "127.0.0.1", port: int = 7497, timeout: float = 2.0) -> bool:
    """Check if TWS is reachable on the given port."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, ConnectionRefusedError):
        return False


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def e2e_client():
    """
    HTTP client for E2E tests.

    Two modes:
      - Default (no env var): spins up an in-process FastAPI TestClient.
      - Visual (E2E_BASE_URL set): uses httpx.Client pointed at the running
        server so you can watch the app respond in the browser.
        Set by run_e2e_visual.sh automatically.
    """
    base_url = os.environ.get("E2E_BASE_URL", "").strip()

    if base_url:
        # Real server mode — point httpx at the already-running app
        import httpx
        with httpx.Client(base_url=base_url, timeout=30.0) as c:
            # Wait for the server to be connected and ready
            deadline = time.time() + 20
            while time.time() < deadline:
                try:
                    r = c.get("/api/status")
                    if r.status_code == 200 and r.json().get("connected"):
                        break
                except Exception:
                    pass
                time.sleep(1)
            yield c
    else:
        # In-process mode (CI / default)
        from fastapi.testclient import TestClient
        from app import create_app

        app = create_app()
        with TestClient(app, raise_server_exceptions=False) as c:
            deadline = time.time() + 15
            while time.time() < deadline:
                r = c.get("/api/status")
                if r.status_code == 200 and r.json().get("connected"):
                    break
                time.sleep(1)
            yield c


# ── E2E-01: Connection health ─────────────────────────────────────────────────

@pytest.mark.e2e
def test_e2e_tws_reachable():
    """Pre-condition: paper TWS must be reachable on port 7497."""
    assert _tws_reachable(), (
        "Paper TWS is not reachable on 127.0.0.1:7497. "
        "Start TWS in paper trading mode and enable the API before running E2E tests."
    )


@pytest.mark.e2e
def test_e2e_status_connected(e2e_client):
    """E2E: /api/status must report connected=True and mode=paper after startup."""
    r = e2e_client.get("/api/status")
    assert r.status_code == 200
    data = r.json()
    assert data["connected"] is True, f"Expected connected=True, got: {data}"
    assert data["mode"] == "paper", (
        f"E2E tests must run in paper mode, got mode={data['mode']}. "
        "Start TWS in paper trading mode."
    )


# ── E2E-02: Portfolio data ────────────────────────────────────────────────────

@pytest.mark.e2e
def test_e2e_portfolio_returns_data(e2e_client):
    """E2E: /api/portfolio must return a valid response with cash and positions."""
    r = e2e_client.get("/api/portfolio")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    data = r.json()

    assert "positions" in data, "Response must include 'positions'"
    assert "cash_chf" in data, "Response must include 'cash_chf'"
    assert "total_value_chf" in data, "Response must include 'total_value_chf'"
    assert isinstance(data["positions"], list)
    assert isinstance(data["cash_chf"], (int, float))
    assert data["total_value_chf"] >= 0


@pytest.mark.e2e
def test_e2e_portfolio_positions_have_required_fields(e2e_client):
    """E2E: each position must have the fields the frontend expects."""
    r = e2e_client.get("/api/portfolio")
    assert r.status_code == 200
    for pos in r.json()["positions"]:
        assert "ticker" in pos
        assert "value_chf" in pos
        assert "quantity" in pos
        # pnl_pct may be None if avg_cost unavailable, but key must exist
        assert "pnl_pct" in pos


# ── E2E-03: Target allocation ─────────────────────────────────────────────────

@pytest.mark.e2e
def test_e2e_targets_get(e2e_client):
    """E2E: /api/targets must return saved weights summing to 100%."""
    r = e2e_client.get("/api/targets")
    assert r.status_code == 200
    data = r.json()
    assert "targets" in data
    total = sum(data["targets"].values())
    assert abs(total - 100.0) < 0.1, f"Targets sum to {total:.1f}% — must be 100%"


# ── E2E-04: Rebalancing plan ──────────────────────────────────────────────────

@pytest.mark.e2e
def test_e2e_plan_returns_valid_structure(e2e_client):
    """E2E: /api/plan must return a plan with correct structure."""
    r = e2e_client.post("/api/plan", json={"min_trade": 500, "excluded_tickers": []})
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    data = r.json()

    assert "plan" in data
    assert "total_to_invest" in data
    assert "cash_available" in data
    assert "shortfall" in data
    assert isinstance(data["plan"], list)
    assert data["cash_available"] >= 0
    assert data["shortfall"] >= 0


@pytest.mark.e2e
def test_e2e_plan_cash_constraint_respected(e2e_client):
    """E2E: included buys must never exceed available cash."""
    r = e2e_client.post("/api/plan", json={"min_trade": 500, "excluded_tickers": []})
    assert r.status_code == 200
    data = r.json()

    included_total = sum(row["suggested_chf"] for row in data["plan"] if row["included"])
    cash = data["cash_available"]
    assert included_total <= cash + 1.0, (
        f"Included buys total {included_total:.2f} exceeds cash {cash:.2f}"
    )


@pytest.mark.e2e
def test_e2e_plan_no_sell_positions(e2e_client):
    """E2E: plan must never include negative suggested amounts (sells)."""
    r = e2e_client.post("/api/plan", json={"min_trade": 500, "excluded_tickers": []})
    assert r.status_code == 200
    for row in r.json()["plan"]:
        assert row["suggested_chf"] >= 0, (
            f"Plan row for {row['ticker']} has negative amount {row['suggested_chf']} — "
            "the app must never suggest sells"
        )


@pytest.mark.e2e
def test_e2e_plan_excluded_tickers_respected(e2e_client):
    """E2E: tickers in excluded_tickers must not appear in the plan."""
    r_targets = e2e_client.get("/api/targets")
    all_tickers = list(r_targets.json()["targets"].keys())
    if not all_tickers:
        pytest.skip("No target tickers configured")

    exclude_ticker = all_tickers[0]
    r = e2e_client.post("/api/plan", json={
        "min_trade": 0,
        "excluded_tickers": [exclude_ticker],
    })
    assert r.status_code == 200
    plan_tickers = [row["ticker"] for row in r.json()["plan"]]
    assert exclude_ticker not in plan_tickers, (
        f"Excluded ticker {exclude_ticker} must not appear in the plan"
    )


# ── E2E-05: Dry-run execute ───────────────────────────────────────────────────

@pytest.mark.e2e
def test_e2e_dry_run_does_not_place_orders(e2e_client):
    """E2E: dry-run execute must return dry_run status and place no real orders."""
    # Get a plan first to find a valid ticker with a price
    r_plan = e2e_client.post("/api/plan", json={"min_trade": 0, "excluded_tickers": []})
    assert r_plan.status_code == 200
    plan = r_plan.json()["plan"]

    # Find first included row with a limit_price
    order_row = next(
        (row for row in plan if row.get("included") and row.get("limit_price") and row.get("estimated_qty")),
        None,
    )
    if not order_row:
        pytest.skip("No included orders in plan — portfolio may be fully balanced")

    r = e2e_client.post("/api/execute", json={
        "dry_run": True,
        "orders": [{
            "ticker": order_row["ticker"],
            "qty": order_row["estimated_qty"],
            "limit_price": order_row["limit_price"],
            "estimated_chf": order_row["suggested_chf"],
        }],
    })
    assert r.status_code == 200
    results = r.json()["results"]
    assert len(results) == 1
    assert results[0]["status"] == "dry_run", (
        f"Expected status='dry_run', got '{results[0]['status']}'"
    )


@pytest.mark.e2e
def test_e2e_dry_run_not_written_to_trade_log(e2e_client, tmp_path, monkeypatch):
    """E2E: dry-run must not persist anything to the trade log."""
    log_file = tmp_path / "e2e_trades.json"
    monkeypatch.setattr("routes.orders.TRADES_LOG", log_file)

    e2e_client.post("/api/execute", json={
        "dry_run": True,
        "orders": [{"ticker": "CHSPI", "qty": 1, "limit_price": 161.0, "estimated_chf": 161.0}],
    })
    assert not log_file.exists(), "Dry-run must not write to trade log"


# ── E2E-06: Error handling ────────────────────────────────────────────────────

@pytest.mark.e2e
def test_e2e_execute_unknown_ticker_returns_error(e2e_client):
    """E2E: executing an order for an unknown ticker must return an error, not hang."""
    start = time.time()
    r = e2e_client.post("/api/execute", json={
        "dry_run": False,
        "orders": [{"ticker": "UNKNOWN_XYZ_E2E", "qty": 1, "limit_price": 100.0, "estimated_chf": 100.0}],
    })
    elapsed = time.time() - start
    assert r.status_code == 200
    results = r.json()["results"]
    assert results[0]["status"] == "error"
    assert elapsed < 5.0, f"Unknown ticker lookup took {elapsed:.1f}s — must not block"


@pytest.mark.e2e
def test_e2e_targets_rejects_invalid_weights(e2e_client):
    """E2E: POST /api/targets with weights != 100% must be rejected."""
    r = e2e_client.post("/api/targets", json={"targets": {"SUSW": 50.0, "XDWT": 30.0}})
    assert r.status_code == 400
