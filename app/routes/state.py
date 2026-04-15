"""Shared IB connection state for all route modules"""

import asyncio
import logging
import random
import threading
import time
import sys
from pathlib import Path
from typing import Optional, Dict

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "claude"))
from ib_client import IBClient

logger = logging.getLogger(__name__)

# Detected at runtime by the connection thread
LIVE_MODE: bool = False
IB_PORT: int = 0   # 0 = not yet determined

_PAPER_PORT = 7497
_LIVE_PORT  = 7496

_ib_client: Optional[IBClient] = None
_connected: bool = False
_lock = threading.Lock()
_name_cache: Dict[str, str] = {}       # ticker → longName
_price_cache: Dict[str, float] = {}    # ticker → latest market price
_contract_cache: Dict[str, object] = {} # ticker → qualified Contract
_price_cache_lock = threading.Lock()


def get_client() -> Optional[IBClient]:
    return _ib_client if _connected else None


def is_connected() -> bool:
    return _connected


def get_name(ticker: str) -> str:
    return _name_cache.get(ticker, "")


def get_cached_price(ticker: str) -> Optional[float]:
    with _price_cache_lock:
        return _price_cache.get(ticker)


def get_price_cache() -> Dict[str, float]:
    with _price_cache_lock:
        return dict(_price_cache)


def get_contract_cache() -> Dict[str, object]:
    with _price_cache_lock:
        return dict(_contract_cache)


def _fetch_names(client: IBClient) -> None:
    """Populate _name_cache for all current portfolio positions."""
    global _name_cache
    try:
        for item in client.ib.portfolio():
            sym = item.contract.symbol
            if sym not in _name_cache:
                try:
                    details = client.ib.reqContractDetails(item.contract)
                    _name_cache[sym] = details[0].longName if details else ""
                except Exception:
                    _name_cache[sym] = ""
        logger.info(f"Name cache populated: {list(_name_cache.keys())}")
    except Exception as e:
        logger.warning(f"Name fetch failed: {e}")


def _fetch_prices(client: IBClient) -> None:
    """Populate _price_cache for all portfolio + target tickers.
    Must be called from the connection thread (owns the ib event loop)."""
    global _price_cache
    from ib_insync import Stock
    import math as _math

    new_cache: Dict[str, float] = {}
    try:
        portfolio_items = client.ib.portfolio()
        contract_map: Dict[str, object] = {}

        # Step 1: prices from portfolio items
        for item in portfolio_items:
            sym = item.contract.symbol
            contract_map[sym] = item.contract
            if item.marketPrice and item.marketPrice > 0:
                new_cache[sym] = item.marketPrice
            elif item.marketValue and item.position and item.position != 0:
                derived = abs(item.marketValue / item.position)
                if derived > 0:
                    new_cache[sym] = derived

        # Step 2: qualify contracts for target tickers not yet held
        try:
            from .targets import _load_config
            targets = _load_config().get("targets", {})
            unresolved = [s for s in targets if s not in contract_map]
            for sym in unresolved:
                for currency in ['CHF', 'EUR', 'USD']:
                    try:
                        q = client.ib.qualifyContracts(Stock(sym, 'SMART', currency))
                        if q:
                            contract_map[sym] = q[0]
                            break
                    except Exception:
                        continue

            # Step 3: reqTickers for anything still missing a price
            needed_contracts = [contract_map[s] for s in targets
                                if s not in new_cache and s in contract_map]
            if needed_contracts:
                tickers = client.ib.reqTickers(*needed_contracts)
                for t in tickers:
                    p = t.marketPrice()
                    if p and p > 0 and not _math.isnan(p):
                        new_cache[t.contract.symbol] = p
        except Exception as e:
            logger.warning(f"Price fetch (targets step) failed: {e}")

        with _price_cache_lock:
            _price_cache = new_cache
            _contract_cache.update(contract_map)
        logger.info(f"Price cache updated: { {k: round(v,2) for k,v in new_cache.items()} }")
    except Exception as e:
        logger.warning(f"Price fetch failed: {e}")


def ensure_event_loop():
    """ib_insync's sync API requires an event loop in every thread that calls it."""
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())


def _try_connect(port: int) -> Optional[IBClient]:
    """Attempt a single connection on the given port. Returns client or None."""
    client = IBClient(
        host="127.0.0.1",
        port=port,
        client_id=random.randint(510, 599),
        timeout=5,
    )
    ok = client.connect(retries=1)
    return client if ok else None


def _connection_worker():
    """Daemon thread: auto-detect paper vs live, keep connected, health-check."""
    global _ib_client, _connected, LIVE_MODE, IB_PORT

    asyncio.set_event_loop(asyncio.new_event_loop())

    while True:
        with _lock:
            currently_connected = _connected
            current_client = _ib_client

        if not currently_connected:
            # Try paper first (safer default), then live
            for port, is_live in [(_PAPER_PORT, False), (_LIVE_PORT, True)]:
                logger.info(f"Trying {'LIVE' if is_live else 'PAPER'} port {port}…")
                try:
                    client = _try_connect(port)
                    if client:
                        with _lock:
                            _ib_client = client
                            _connected = True
                            LIVE_MODE = is_live
                            IB_PORT = port
                        logger.info(f"IB connected ✓  ({'LIVE' if is_live else 'PAPER'} mode, port {port})")
                        _fetch_names(client)
                        _fetch_prices(client)
                        break
                except Exception as e:
                    logger.warning(f"Port {port} failed: {e}")
            else:
                logger.info("TWS not reachable on either port — retrying in 10 s")
            # Not connected — plain sleep, nothing to pump
            time.sleep(10)
        else:
            # Pump ib_insync's event loop in 0.5 s slices for 10 s total.
            # This lets the connection thread process TWS callbacks (order status,
            # market data updates, etc.) while still doing a periodic health-check.
            for _ in range(20):
                try:
                    if current_client:
                        current_client.ib.sleep(0.5)
                except Exception:
                    break
            # Refresh price cache after each pump cycle
            try:
                if current_client:
                    _fetch_prices(current_client)
            except Exception:
                pass
            # Health-check after the pump cycle
            try:
                if current_client and not current_client.ib.isConnected():
                    logger.warning("IB connection lost — will reconnect")
                    with _lock:
                        _connected = False
                        _ib_client = None
                        IB_PORT = 0
            except Exception:
                with _lock:
                    _connected = False
                    _ib_client = None
                    IB_PORT = 0


def start_connection_thread():
    t = threading.Thread(target=_connection_worker, daemon=True, name="ib-connector")
    t.start()
    logger.info("IB connection thread started (auto-detect mode)")
