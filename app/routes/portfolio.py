"""GET /api/status  and  GET /api/portfolio"""

import logging
from datetime import datetime
from typing import Dict
from fastapi import APIRouter, HTTPException
from .state import get_client, is_connected, ensure_event_loop, get_name
import routes.state as _state

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/status")
def get_status():
    return {
        "connected": is_connected(),
        "mode": "live" if _state.LIVE_MODE else "paper",
        "port": _state.IB_PORT,
        "last_checked": datetime.now().isoformat(),
    }


@router.get("/portfolio")
def get_portfolio():
    ensure_event_loop()
    client = get_client()
    if not client:
        raise HTTPException(status_code=503, detail="Not connected to TWS")

    try:
        # ib.portfolio() is already subscribed at connection time — instant, no re-fetch
        portfolio_items = client.ib.portfolio()
        cash_chf = client.get_account_cash()
    except Exception as e:
        logger.error(f"Error fetching portfolio: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    positions = []
    total_invested = 0.0

    for item in portfolio_items:
        sym = item.contract.symbol
        qty = item.position
        if not qty or qty == 0:
            continue

        market_price = item.marketPrice if item.marketPrice else None
        market_value = item.marketValue if item.marketValue else 0.0
        avg_cost = item.averageCost if item.averageCost else None
        total_invested += market_value

        pnl_pct = None
        if avg_cost and avg_cost > 0 and market_price and market_price > 0:
            pnl_pct = round((market_price - avg_cost) / avg_cost * 100, 2)

        unrealized_pnl = item.unrealizedPNL if item.unrealizedPNL is not None else None

        positions.append({
            "ticker": sym,
            "name": get_name(sym),
            "quantity": qty,
            "market_price": round(market_price, 4) if market_price else None,
            "value_chf": round(market_value, 2),
            "currency": item.contract.currency,
            "entry_price": round(avg_cost, 4) if avg_cost else None,
            "pnl_pct": pnl_pct,
            "unrealized_pnl": round(unrealized_pnl, 2) if unrealized_pnl is not None else None,
        })

    total_value = total_invested + cash_chf

    return {
        "positions": positions,
        "cash_chf": round(cash_chf, 2),
        "total_invested": round(total_invested, 2),
        "total_value_chf": round(total_value, 2),
        "last_updated": datetime.now().isoformat(),
    }
