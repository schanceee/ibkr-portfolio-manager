"""GET /api/targets  and  POST /api/targets"""

import json
import logging
from pathlib import Path
from typing import Optional, Dict
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()

CONFIG_FILE = Path(__file__).parent.parent / "app_config.json"
DEFAULTS_FILE = Path(__file__).parent.parent.parent / "claude" / "config.py"

# ── default allocation read from claude/config.py at import time ──────────────
# config.py is gitignored (personal data) — fall back to empty defaults in CI
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "claude"))
try:
    import config as _cfg
    DEFAULT_TARGETS: Dict[str, float] = dict(_cfg.TARGET_ALLOCATION)
    DEFAULT_MIN_TRADE: float = float(_cfg.MIN_TRADE)
except ImportError:
    DEFAULT_TARGETS = {}
    DEFAULT_MIN_TRADE = 500.0

DEFAULT_PNL_THRESHOLD: float = -10.0


def _load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except Exception:
            pass
    return {
        "targets": DEFAULT_TARGETS,
        "pnl_alert_threshold": DEFAULT_PNL_THRESHOLD,
        "min_trade": DEFAULT_MIN_TRADE,
    }


def _save_config(data: dict):
    CONFIG_FILE.write_text(json.dumps(data, indent=2))


# ── routes ────────────────────────────────────────────────────────────────────

@router.get("/targets")
def get_targets():
    cfg = _load_config()
    return {
        "targets": cfg.get("targets", DEFAULT_TARGETS),
        "pnl_alert_threshold": cfg.get("pnl_alert_threshold", DEFAULT_PNL_THRESHOLD),
        "min_trade": cfg.get("min_trade", DEFAULT_MIN_TRADE),
        "defaults": DEFAULT_TARGETS,
    }


class TargetsPayload(BaseModel):
    targets: Dict[str, float]
    pnl_alert_threshold: Optional[float] = None
    min_trade: Optional[float] = None


@router.post("/targets")
def save_targets(payload: TargetsPayload):
    total = sum(payload.targets.values())
    if abs(total - 100.0) > 0.1:
        raise HTTPException(
            status_code=400,
            detail=f"Weights sum to {total:.1f}%, must be 100%",
        )

    cfg = _load_config()
    cfg["targets"] = payload.targets
    if payload.pnl_alert_threshold is not None:
        cfg["pnl_alert_threshold"] = payload.pnl_alert_threshold
    if payload.min_trade is not None:
        cfg["min_trade"] = payload.min_trade
    _save_config(cfg)
    return {"ok": True}


@router.post("/targets/reset")
def reset_targets():
    cfg = _load_config()
    cfg["targets"] = DEFAULT_TARGETS
    _save_config(cfg)
    return {"ok": True, "targets": DEFAULT_TARGETS}
