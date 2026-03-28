#!/usr/bin/env python3
"""IBKR Portfolio Manager — local web app"""

import sys
import threading
import webbrowser
import time
import logging
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

sys.path.insert(0, str(Path(__file__).parent.parent / "claude"))

from routes.portfolio import router as portfolio_router
from routes.targets import router as targets_router
from routes.orders import router as orders_router
import routes.state as state
from routes.state import start_connection_thread

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(title="IBKR Portfolio Manager", docs_url=None, redoc_url=None)

    app.include_router(portfolio_router, prefix="/api")
    app.include_router(targets_router, prefix="/api")
    app.include_router(orders_router, prefix="/api")

    static_dir = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/")
    def index():
        return FileResponse(static_dir / "index.html")

    @app.on_event("startup")
    async def startup():
        logger.info("Starting — will auto-detect paper vs live from TWS")
        start_connection_thread()

    return app


def open_browser(port: int):
    time.sleep(1.5)
    webbrowser.open(f"http://localhost:{port}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="IBKR Portfolio Manager")
    parser.add_argument("--port", type=int, default=8888, help="Web app port (default 8888)")
    args = parser.parse_args()

    app = create_app()

    print(f"\n{'='*50}")
    print(f"  IBKR Portfolio Manager")
    print(f"  Mode : auto-detect (paper / live)")
    print(f"  URL  : http://localhost:{args.port}")
    print(f"  Stop : Ctrl+C")
    print(f"{'='*50}\n")

    threading.Thread(target=open_browser, args=(args.port,), daemon=True).start()

    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")
