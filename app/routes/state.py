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
_name_cache: Dict[str, str] = {}   # ticker → longName, populated at connect time


def get_client() -> Optional[IBClient]:
    return _ib_client if _connected else None


def is_connected() -> bool:
    return _connected


def get_name(ticker: str) -> str:
    return _name_cache.get(ticker, "")


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
