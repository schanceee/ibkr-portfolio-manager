"""POST /api/plan  and  POST /api/execute  and  GET /api/trades"""

import json
import math
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from .state import get_client, ensure_event_loop
import routes.state as _state
from .targets import _load_config

logger = logging.getLogger(__name__)
router = APIRouter()

TRADES_LOG = Path(__file__).parent.parent / "trades_log.json"


def _append_trade(record: dict) -> None:
    """Persist a trade record to trades_log.json."""
    try:
        existing: list = []
        if TRADES_LOG.exists():
            try:
                existing = json.loads(TRADES_LOG.read_text())
            except Exception:
                existing = []
        existing.append(record)
        TRADES_LOG.write_text(json.dumps(existing, indent=2))
    except Exception as e:
        logger.warning(f"Could not write trade log: {e}")


@router.get("/trades")
def get_trades():
    if not TRADES_LOG.exists():
        return {"trades": []}
    try:
        return {"trades": json.loads(TRADES_LOG.read_text())}
    except Exception:
        return {"trades": []}


# ── helpers ───────────────────────────────────────────────────────────────────

def _build_plan(
    positions_by_symbol: Dict[str, float],
    cash_chf: float,
    total_value: float,
    targets: Dict[str, float],
    min_trade: float,
    excluded: List[str],
) -> List[dict]:
    """Pure logic: return list of suggested buys sorted by gap desc."""
    results = []
    for sym, target_pct in targets.items():
        if sym in excluded:
            continue
        current_val = positions_by_symbol.get(sym, 0.0)
        current_pct = (current_val / total_value * 100) if total_value > 0 else 0.0
        gap_pp = target_pct - current_pct
        if gap_pp <= 0:
            continue  # overweight or on target — skip
        suggested_chf = total_value * gap_pp / 100
        if suggested_chf < min_trade:
            results.append({
                "ticker": sym,
                "gap_pp": round(gap_pp, 2),
                "suggested_chf": round(suggested_chf, 2),
                "estimated_qty": None,
                "included": False,
                "reason": f"Below min trade (CHF {suggested_chf:.0f} < CHF {min_trade:.0f})",
            })
            continue
        results.append({
            "ticker": sym,
            "gap_pp": round(gap_pp, 2),
            "suggested_chf": round(suggested_chf, 2),
            "estimated_qty": None,  # filled below if price known
            "included": True,
            "reason": None,
        })

    # Sort: included first by gap desc, then excluded
    results.sort(key=lambda r: (-r["included"], -r["gap_pp"]))

    # Fit within available cash: trim smallest included buys until total ≤ cash
    included = [r for r in results if r["included"]]
    excluded_rows = [r for r in results if not r["included"]]
    total_needed = sum(r["suggested_chf"] for r in included)

    while total_needed > cash_chf and included:
        # Remove the smallest included buy
        smallest = min(included, key=lambda r: r["suggested_chf"])
        smallest["included"] = False
        smallest["reason"] = "Excluded: insufficient cash"
        included.remove(smallest)
        excluded_rows.append(smallest)
        total_needed = sum(r["suggested_chf"] for r in included)

    return included + excluded_rows


# ── routes ────────────────────────────────────────────────────────────────────

class PlanRequest(BaseModel):
    min_trade: Optional[float] = None
    excluded_tickers: List[str] = []


@router.post("/plan")
def compute_plan(req: PlanRequest):
    ensure_event_loop()
    client = get_client()
    if not client:
        raise HTTPException(status_code=503, detail="Not connected to TWS")

    cfg = _load_config()
    targets = cfg.get("targets", {})
    min_trade = req.min_trade if req.min_trade is not None else cfg.get("min_trade", 500)

    try:
        portfolio_items = client.ib.portfolio()
        cash_chf = client.get_account_cash()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    positions_by_symbol: Dict[str, float] = {}
    price_cache: Dict[str, float] = {}
    for item in portfolio_items:
        if item.position and item.position != 0:
            sym = item.contract.symbol
            positions_by_symbol[sym] = positions_by_symbol.get(sym, 0) + (item.marketValue or 0)
            if item.marketPrice and item.marketPrice > 0:
                price_cache[sym] = item.marketPrice

    total_value = sum(positions_by_symbol.values()) + cash_chf

    plan = _build_plan(
        positions_by_symbol=positions_by_symbol,
        cash_chf=cash_chf,
        total_value=total_value,
        targets=targets,
        min_trade=min_trade,
        excluded=req.excluded_tickers,
    )

    for row in plan:
        if row["included"]:
            price = price_cache.get(row["ticker"])
            if price:
                row["estimated_qty"] = max(1, math.floor(row["suggested_chf"] / price))
                row["limit_price"] = round(price * 1.005, 2)

    included = [r for r in plan if r["included"]]
    total_to_invest = sum(r["suggested_chf"] for r in included)

    return {
        "plan": plan,
        "total_to_invest": round(total_to_invest, 2),
        "cash_available": round(cash_chf, 2),
        "shortfall": round(max(0, total_to_invest - cash_chf), 2),
    }


class OrderItem(BaseModel):
    ticker: str
    qty: int
    limit_price: float
    estimated_chf: float


class ExecuteRequest(BaseModel):
    orders: List[OrderItem]
    dry_run: bool = True


@router.post("/execute")
def execute_orders(req: ExecuteRequest):
    ensure_event_loop()
    client = get_client()
    if not client:
        raise HTTPException(status_code=503, detail="Not connected to TWS")

    results = []

    # Build contract cache from portfolio items (already qualified — no lookup needed)
    portfolio_contracts: Dict[str, object] = {}
    try:
        for item in client.ib.portfolio():
            sym = item.contract.symbol
            if sym not in portfolio_contracts:
                portfolio_contracts[sym] = item.contract
    except Exception as e:
        logger.warning(f"Could not pre-cache portfolio contracts: {e}")

    for order in req.orders:
        if req.dry_run:
            results.append({
                "ticker": order.ticker,
                "qty": order.qty,
                "limit_price": order.limit_price,
                "estimated_chf": order.estimated_chf,
                "status": "dry_run",
                "order_id": None,
                "error": None,
            })
            continue

        try:
            # Use contract from portfolio cache (already qualified); fall back to symbol search
            raw_contract = portfolio_contracts.get(order.ticker) or client.find_contract(order.ticker)
            if not raw_contract:
                results.append({
                    "ticker": order.ticker,
                    "qty": order.qty,
                    "limit_price": order.limit_price,
                    "estimated_chf": order.estimated_chf,
                    "status": "error",
                    "order_id": None,
                    "error": "Contract not found",
                })
                continue

            # Portfolio contracts store the listing exchange (e.g. LSEETF, IBIS2).
            # IBKR order routing needs exchange='SMART' with primaryExch set to the
            # listing exchange; otherwise TWS sends the order to the wrong venue and
            # never acknowledges it (stays PendingSubmit).
            from ib_insync import Contract, LimitOrder
            contract = Contract(
                conId=raw_contract.conId,
                secType=raw_contract.secType or "STK",
                symbol=raw_contract.symbol,
                currency=raw_contract.currency,
                exchange="SMART",
                primaryExchange=getattr(raw_contract, "primaryExchange", "") or raw_contract.exchange,
            )

            ib_order = LimitOrder("BUY", order.qty, order.limit_price)
            ib_order.tif = "DAY"
            ib_order.outsideRth = True   # allow pre/post-market in paper testing

            trade = client.ib.placeOrder(contract, ib_order)

            # Poll up to 10 s for the status to advance past PendingSubmit.
            # The connection thread pumps ib_insync's event loop every 0.5 s, which
            # processes TWS callbacks and updates trade.orderStatus.  We just wait
            # here with plain time.sleep() until the status changes.
            deadline = time.time() + 10
            while time.time() < deadline:
                time.sleep(0.5)
                if trade.orderStatus.status and trade.orderStatus.status != "PendingSubmit":
                    break

            # Collect any error/warning messages from TWS logged on this trade
            error_msg = None
            for entry in (trade.log or []):
                msg = getattr(entry, "message", "") or ""
                code = getattr(entry, "errorCode", 0) or 0
                if code and code not in (202, 399):   # 202=cancelled ok, 399=routing warning
                    error_msg = f"[{code}] {msg}"
                    break
                if "error" in msg.lower():
                    error_msg = msg
                    break

            status = trade.orderStatus.status if trade.orderStatus.status else "submitted"
            if error_msg:
                status = "error"

            results.append({
                "ticker": order.ticker,
                "qty": order.qty,
                "limit_price": order.limit_price,
                "estimated_chf": order.estimated_chf,
                "status": status,
                "order_id": trade.order.orderId,
                "error": error_msg,
            })
        except Exception as e:
            logger.error(f"Error placing order for {order.ticker}: {e}")
            results.append({
                "ticker": order.ticker,
                "qty": order.qty,
                "limit_price": order.limit_price,
                "estimated_chf": order.estimated_chf,
                "status": "error",
                "order_id": None,
                "error": str(e),
            })

    # Persist all results (including errors) so the user has a full audit trail
    if not req.dry_run:
        mode = "live" if _state.LIVE_MODE else "paper"
        ts = datetime.now().isoformat()
        for r in results:
            _append_trade({
                "timestamp": ts,
                "mode": mode,
                "ticker": r["ticker"],
                "qty": r["qty"],
                "limit_price": r["limit_price"],
                "estimated_chf": r["estimated_chf"],
                "status": r["status"],
                "order_id": r["order_id"],
                "error": r["error"],
            })

    return {"dry_run": req.dry_run, "results": results}
