"""
API regression tests — no TWS required.

These tests cover the bugs that have previously slipped through:
  - /api/plan hanging because ib_insync was called from the FastAPI thread
  - Cash-trimming algorithm excluding everything when one item exceeds cash
  - /api/execute hanging due to portfolio() / find_contract() in request path
  - Orders using wrong exchange (listing exchange instead of SMART)
  - /api/targets not persisting when weights don't sum to 100%

Run with:  pytest app/tests/ -v
"""

import json
import sys
import time
import threading
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Make sure app package is importable
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "claude"))


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_ib_state(tmp_path):
    """Patch routes.state so all API routes get a fake connected IB client."""
    fake_client = MagicMock()
    fake_client.ib.isConnected.return_value = True

    price_cache = {
        "SUSW":  155.10,
        "XDWT":   97.40,
        "CHDVD":  27.80,
        "XDWH":  104.50,
        "CHSPI": 161.20,
        "NUKL":   46.30,
    }
    contract_cache = {sym: _fake_contract(sym) for sym in price_cache}

    with patch("routes.state._connected", True), \
         patch("routes.state._ib_client", fake_client), \
         patch("routes.state.LIVE_MODE", False), \
         patch("routes.state._price_cache", price_cache), \
         patch("routes.state._contract_cache", contract_cache):
        yield {"client": fake_client, "prices": price_cache, "contracts": contract_cache}


@pytest.fixture
def config_file(tmp_path, monkeypatch):
    """Redirect app_config.json writes to a temp file."""
    cfg = tmp_path / "app_config.json"
    cfg.write_text(json.dumps({
        "targets": {"SUSW": 50.0, "XDWT": 20.0, "CHDVD": 10.0,
                    "XDWH": 10.0, "CHSPI": 5.0, "NUKL": 5.0},
        "pnl_alert_threshold": -10.0,
        "min_trade": 500.0,
    }))
    monkeypatch.setattr("routes.targets.CONFIG_FILE", cfg)
    return cfg


@pytest.fixture
def client(mock_ib_state, config_file):
    """FastAPI TestClient with mocked IB state and temp config."""
    from app import create_app
    with patch("routes.state.start_connection_thread"):  # don't spawn real IB thread
        app = create_app()
    with TestClient(app) as c:
        yield c


def _fake_contract(sym: str):
    c = MagicMock()
    c.symbol = sym
    c.conId = hash(sym) % 100000
    c.secType = "STK"
    c.currency = "CHF"
    c.exchange = "LSEETF"
    c.primaryExchange = "LSEETF"
    return c


def _fake_portfolio_item(sym: str, position: float, market_value: float, market_price: float):
    item = MagicMock()
    item.contract = _fake_contract(sym)
    item.position = position
    item.marketValue = market_value
    item.marketPrice = market_price
    item.unrealizedPNL = market_value * 0.05
    item.averageCost = market_price * 0.95
    return item


# ── AT-01: /api/status ────────────────────────────────────────────────────────

def test_status_returns_connected(client):
    r = client.get("/api/status")
    assert r.status_code == 200
    assert r.json()["connected"] is True


# ── AT-02 / AT-03: /api/targets round-trip ───────────────────────────────────

def test_targets_get(client):
    r = client.get("/api/targets")
    assert r.status_code == 200
    data = r.json()
    assert "targets" in data
    assert abs(sum(data["targets"].values()) - 100.0) < 0.1


def test_targets_save_and_reload(client, config_file):
    new_targets = {"SUSW": 60.0, "XDWT": 40.0}
    r = client.post("/api/targets", json={"targets": new_targets})
    assert r.status_code == 200

    r2 = client.get("/api/targets")
    assert r2.json()["targets"]["SUSW"] == 60.0


def test_targets_rejects_invalid_weights(client):
    """Weights that don't sum to 100% must be rejected — not silently lost."""
    r = client.post("/api/targets", json={"targets": {"SUSW": 60.0, "XDWT": 30.0}})
    assert r.status_code == 400, "Should reject weights summing to 90%"


# ── AT-04 / AT-05: /api/plan correctness ─────────────────────────────────────

def _portfolio_for_plan(mock_ib_state):
    """Simulates a portfolio where SUSW is massively underweight."""
    mock_ib_state["client"].ib.portfolio.return_value = [
        _fake_portfolio_item("XDWT",  36, 3506.4,  97.40),
        _fake_portfolio_item("NUKL",  60, 2778.0,  46.30),
        _fake_portfolio_item("XDWH",  25, 2612.5, 104.50),
    ]
    mock_ib_state["client"].get_account_cash.return_value = 7787.0


def test_plan_returns_quickly(client, mock_ib_state):
    """Regression: /api/plan must not block on ib_insync calls from the request thread."""
    _portfolio_for_plan(mock_ib_state)
    start = time.time()
    r = client.post("/api/plan", json={"min_trade": 500, "excluded_tickers": []})
    elapsed = time.time() - start
    assert r.status_code == 200
    assert elapsed < 3.0, f"/api/plan took {elapsed:.1f}s — likely blocking on ib_insync"


def test_plan_large_item_excluded_not_small_items(client, mock_ib_state):
    """
    Regression: when one item costs more than cash, it should be excluded
    and the affordable smaller items should still be included.

    Previous bug: the trimming loop removed smallest-first, leaving the
    expensive item last, then excluded it too — resulting in zero buys
    even though the user had enough cash for several smaller positions.
    """
    mock_ib_state["client"].ib.portfolio.return_value = [
        _fake_portfolio_item("XDWT", 36, 3506.4, 97.40),
        _fake_portfolio_item("NUKL", 60, 2778.0, 46.30),
        _fake_portfolio_item("XDWH", 25, 2612.5, 104.50),
    ]
    mock_ib_state["client"].get_account_cash.return_value = 7787.0

    r = client.post("/api/plan", json={"min_trade": 500, "excluded_tickers": []})
    assert r.status_code == 200
    data = r.json()

    included = [row for row in data["plan"] if row["included"]]
    excluded = [row for row in data["plan"] if not row["included"]]

    # SUSW needs ~CHF 11k which is more than the CHF 7787 cash — must be excluded
    susw_excluded = any(r["ticker"] == "SUSW" for r in excluded)
    assert susw_excluded, "SUSW (too expensive alone) must be excluded"

    # Smaller items that fit within cash must remain included
    assert len(included) > 0, "Affordable smaller items must be included, not everything excluded"

    # Total of included buys must not exceed cash
    total = sum(r["suggested_chf"] for r in included)
    assert total <= 7787 + 1, f"Included total {total:.0f} exceeds available cash 7787"


def test_plan_no_buys_when_all_overweight(client, mock_ib_state):
    """If every position is at or above target, the plan should be empty."""
    mock_ib_state["client"].ib.portfolio.return_value = [
        _fake_portfolio_item("SUSW", 100, 15000.0, 150.0),
    ]
    mock_ib_state["client"].get_account_cash.return_value = 5000.0

    with patch("routes.targets.CONFIG_FILE") as _:
        pass  # config already mocked via fixture

    r = client.post("/api/plan", json={"min_trade": 500, "excluded_tickers": []})
    assert r.status_code == 200
    data = r.json()
    included = [row for row in data["plan"] if row["included"]]
    # SUSW at 75% vs 50% target → overweight → no buy
    susw_included = any(r["ticker"] == "SUSW" for r in included)
    assert not susw_included


# ── AT-06 / AT-07: /api/execute ──────────────────────────────────────────────

def test_execute_dry_run_does_not_call_place_order(client, mock_ib_state):
    r = client.post("/api/execute", json={
        "dry_run": True,
        "orders": [{"ticker": "CHSPI", "qty": 4, "limit_price": 161.20, "estimated_chf": 644.0}],
    })
    assert r.status_code == 200
    results = r.json()["results"]
    assert results[0]["status"] == "dry_run"
    mock_ib_state["client"].ib.placeOrder.assert_not_called()


def test_execute_returns_quickly(client, mock_ib_state):
    """
    Regression: /api/execute must not block on portfolio() or find_contract().
    Previously these ib_insync calls from the FastAPI thread blocked indefinitely.
    """
    trade_mock = MagicMock()
    trade_mock.orderStatus.status = "Submitted"
    trade_mock.order.orderId = 42
    trade_mock.log = []
    mock_ib_state["client"].ib.placeOrder.return_value = trade_mock

    start = time.time()
    r = client.post("/api/execute", json={
        "dry_run": False,
        "orders": [{"ticker": "CHSPI", "qty": 4, "limit_price": 161.20, "estimated_chf": 644.0}],
    })
    elapsed = time.time() - start
    assert r.status_code == 200
    assert elapsed < 12.0, f"/api/execute took {elapsed:.1f}s — likely blocking on ib_insync"


def test_execute_uses_smart_routing(client, mock_ib_state):
    """
    Regression: orders must be placed with exchange='SMART', not the listing
    exchange directly. Using LSEETF/IBIS2 as the routing exchange causes TWS
    to silently ignore the order (stays PendingSubmit forever).
    """
    trade_mock = MagicMock()
    trade_mock.orderStatus.status = "Submitted"
    trade_mock.order.orderId = 99
    trade_mock.log = []
    mock_ib_state["client"].ib.placeOrder.return_value = trade_mock

    client.post("/api/execute", json={
        "dry_run": False,
        "orders": [{"ticker": "CHSPI", "qty": 4, "limit_price": 161.20, "estimated_chf": 644.0}],
    })

    assert mock_ib_state["client"].ib.placeOrder.called
    placed_contract = mock_ib_state["client"].ib.placeOrder.call_args[0][0]
    assert placed_contract.exchange == "SMART", (
        f"Order must use exchange='SMART', got '{placed_contract.exchange}'. "
        "Using the listing exchange directly causes TWS to silently drop the order."
    )


def test_execute_error_when_contract_not_in_cache(client, mock_ib_state):
    """If a ticker has no pre-qualified contract, return an error — don't hang."""
    r = client.post("/api/execute", json={
        "dry_run": False,
        "orders": [{"ticker": "UNKNOWN_XYZ", "qty": 1, "limit_price": 100.0, "estimated_chf": 100.0}],
    })
    assert r.status_code == 200
    results = r.json()["results"]
    assert results[0]["status"] == "error"
    assert "not found" in (results[0]["error"] or "").lower()


# ── AT-08: /api/trades ────────────────────────────────────────────────────────

def test_trades_returns_list(client, tmp_path, monkeypatch):
    """Trade history endpoint must always return a list, even with no file."""
    monkeypatch.setattr("routes.orders.TRADES_LOG", tmp_path / "no_trades.json")
    r = client.get("/api/trades")
    assert r.status_code == 200
    assert r.json()["trades"] == []


def test_trades_persisted_after_execute(client, mock_ib_state, tmp_path, monkeypatch):
    """Executed orders must be written to the trade log."""
    log_file = tmp_path / "trades_log.json"
    monkeypatch.setattr("routes.orders.TRADES_LOG", log_file)

    trade_mock = MagicMock()
    trade_mock.orderStatus.status = "Submitted"
    trade_mock.order.orderId = 77
    trade_mock.log = []
    mock_ib_state["client"].ib.placeOrder.return_value = trade_mock

    client.post("/api/execute", json={
        "dry_run": False,
        "orders": [{"ticker": "CHSPI", "qty": 4, "limit_price": 161.20, "estimated_chf": 644.0}],
    })

    assert log_file.exists(), "Trade log file must be created after execution"
    trades = json.loads(log_file.read_text())
    assert len(trades) == 1
    assert trades[0]["ticker"] == "CHSPI"
    assert trades[0]["qty"] == 4


def test_dry_run_not_persisted(client, mock_ib_state, tmp_path, monkeypatch):
    """Dry-run orders must NOT be written to the trade log."""
    log_file = tmp_path / "trades_log.json"
    monkeypatch.setattr("routes.orders.TRADES_LOG", log_file)

    client.post("/api/execute", json={
        "dry_run": True,
        "orders": [{"ticker": "CHSPI", "qty": 4, "limit_price": 161.20, "estimated_chf": 644.0}],
    })

    assert not log_file.exists(), "Dry-run must not write to trade log"


# ── AT-09 / AT-10: /api/portfolio ────────────────────────────────────────────

def test_portfolio_returns_positions_and_cash(client, mock_ib_state):
    """GET /api/portfolio must return positions, cash, and total portfolio value."""
    mock_ib_state["client"].ib.portfolio.return_value = [
        _fake_portfolio_item("SUSW", 40, 6200.0, 155.0),
        _fake_portfolio_item("XDWT", 36, 3506.4, 97.40),
    ]
    mock_ib_state["client"].get_account_cash.return_value = 5000.0

    r = client.get("/api/portfolio")
    assert r.status_code == 200
    data = r.json()
    assert "positions" in data
    assert "cash_chf" in data
    assert "total_value_chf" in data
    tickers = [p["ticker"] for p in data["positions"]]
    assert "SUSW" in tickers
    assert "XDWT" in tickers
    assert data["cash_chf"] == 5000.0
    assert abs(data["total_value_chf"] - (6200.0 + 3506.4 + 5000.0)) < 1.0


def test_portfolio_includes_pnl(client, mock_ib_state):
    """GET /api/portfolio positions must include pnl_pct computed from avg_cost."""
    mock_ib_state["client"].ib.portfolio.return_value = [
        _fake_portfolio_item("NUKL", 60, 2778.0, 46.30),
    ]
    mock_ib_state["client"].get_account_cash.return_value = 1000.0

    r = client.get("/api/portfolio")
    assert r.status_code == 200
    positions = r.json()["positions"]
    nukl = next((p for p in positions if p["ticker"] == "NUKL"), None)
    assert nukl is not None
    # _fake_portfolio_item sets averageCost = marketPrice * 0.95 → pnl ≈ +5.26%
    assert nukl["pnl_pct"] is not None
    assert nukl["pnl_pct"] > 0


def test_portfolio_includes_unmanaged_positions(client, mock_ib_state):
    """Spec §5: Positions not in target list must appear in portfolio response."""
    mock_ib_state["client"].ib.portfolio.return_value = [
        _fake_portfolio_item("SUSW", 40, 6200.0, 155.0),
        _fake_portfolio_item("AAPL", 10, 1500.0, 150.0),  # not in any target
    ]
    mock_ib_state["client"].get_account_cash.return_value = 2000.0

    r = client.get("/api/portfolio")
    assert r.status_code == 200
    tickers = [p["ticker"] for p in r.json()["positions"]]
    assert "AAPL" in tickers, "Unmanaged positions must appear in portfolio response"
    assert "SUSW" in tickers


# ── AT-11: 503 responses when TWS is disconnected ────────────────────────────

@pytest.fixture
def disconnected_client(config_file):
    """FastAPI TestClient with TWS not connected."""
    with patch("routes.state._connected", False), \
         patch("routes.state._ib_client", None):
        from app import create_app
        with patch("routes.state.start_connection_thread"):
            app = create_app()
        with TestClient(app) as c:
            yield c


def test_portfolio_503_when_disconnected(disconnected_client):
    """Spec §5: App must refuse to operate if TWS is not running."""
    r = disconnected_client.get("/api/portfolio")
    assert r.status_code == 503


def test_plan_503_when_disconnected(disconnected_client):
    """Spec §5: /api/plan must return 503 when TWS is not connected."""
    r = disconnected_client.post("/api/plan", json={"min_trade": 500, "excluded_tickers": []})
    assert r.status_code == 503


def test_execute_503_when_disconnected(disconnected_client):
    """Spec §5: /api/execute must return 503 when TWS is not connected."""
    r = disconnected_client.post("/api/execute", json={
        "dry_run": False,
        "orders": [{"ticker": "CHSPI", "qty": 4, "limit_price": 161.20, "estimated_chf": 644.0}],
    })
    assert r.status_code == 503


# ── AT-12: /api/targets/reset ────────────────────────────────────────────────

def test_targets_reset_restores_defaults(client, config_file):
    """POST /api/targets/reset must overwrite saved config with DEFAULT_TARGETS."""
    # First save a custom allocation
    client.post("/api/targets", json={"targets": {"SUSW": 60.0, "XDWT": 40.0}})

    r = client.post("/api/targets/reset")
    assert r.status_code == 200

    r2 = client.get("/api/targets")
    returned = r2.json()["targets"]
    from routes.targets import DEFAULT_TARGETS
    for ticker, weight in DEFAULT_TARGETS.items():
        assert abs(returned.get(ticker, -1) - weight) < 0.01, (
            f"After reset, {ticker} should be {weight}% but got {returned.get(ticker)}"
        )


# ── AT-13: BUY-only enforcement ───────────────────────────────────────────────

def test_execute_places_only_buy_orders(client, mock_ib_state):
    """Spec §2: App only places BUY orders, never SELL."""
    trade_mock = MagicMock()
    trade_mock.orderStatus.status = "Submitted"
    trade_mock.order.orderId = 55
    trade_mock.log = []
    mock_ib_state["client"].ib.placeOrder.return_value = trade_mock

    client.post("/api/execute", json={
        "dry_run": False,
        "orders": [{"ticker": "CHSPI", "qty": 4, "limit_price": 161.20, "estimated_chf": 644.0}],
    })

    assert mock_ib_state["client"].ib.placeOrder.called
    placed_order = mock_ib_state["client"].ib.placeOrder.call_args[0][1]
    assert placed_order.action == "BUY", (
        f"Order action must be 'BUY', got '{placed_order.action}'. "
        "The app must never place SELL orders per spec."
    )


# ── AT-14: DAY time-in-force ──────────────────────────────────────────────────

def test_execute_orders_use_day_tif(client, mock_ib_state):
    """Spec §W3: Orders expire at end of trading day (tif=DAY)."""
    trade_mock = MagicMock()
    trade_mock.orderStatus.status = "Submitted"
    trade_mock.order.orderId = 66
    trade_mock.log = []
    mock_ib_state["client"].ib.placeOrder.return_value = trade_mock

    client.post("/api/execute", json={
        "dry_run": False,
        "orders": [{"ticker": "CHSPI", "qty": 4, "limit_price": 161.20, "estimated_chf": 644.0}],
    })

    placed_order = mock_ib_state["client"].ib.placeOrder.call_args[0][1]
    assert placed_order.tif == "DAY", (
        f"Order tif must be 'DAY', got '{placed_order.tif}'. "
        "Orders must expire at end of trading day per spec."
    )


# ── AT-15: Shortfall calculation ─────────────────────────────────────────────

def test_plan_reports_shortfall_when_cash_insufficient(client, mock_ib_state):
    """Spec §W2: when total_to_invest > cash, shortfall must be reported."""
    mock_ib_state["client"].ib.portfolio.return_value = [
        _fake_portfolio_item("SUSW", 10, 1550.0, 155.0),
        _fake_portfolio_item("XDWT", 10, 974.0, 97.40),
    ]
    mock_ib_state["client"].get_account_cash.return_value = 500.0

    r = client.post("/api/plan", json={"min_trade": 100, "excluded_tickers": []})
    assert r.status_code == 200
    data = r.json()

    assert "shortfall" in data
    assert "total_to_invest" in data
    assert "cash_available" in data
    assert data["cash_available"] == 500.0
    if data["total_to_invest"] > data["cash_available"]:
        expected_shortfall = data["total_to_invest"] - data["cash_available"]
        assert abs(data["shortfall"] - expected_shortfall) < 1.0, (
            f"Shortfall should be {expected_shortfall:.2f}, got {data['shortfall']}"
        )


# ── AT-16: Status returns mode ───────────────────────────────────────────────

def test_status_returns_paper_mode(client):
    """GET /api/status must report paper/live mode."""
    r = client.get("/api/status")
    assert r.status_code == 200
    data = r.json()
    assert "mode" in data
    assert data["mode"] in ("paper", "live")
