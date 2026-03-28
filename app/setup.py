#!/usr/bin/env python3
"""
One-time setup: creates a Desktop shortcut for the IBKR Portfolio Manager.
Run once:  python setup.py
"""

import stat
import subprocess
import sys
from pathlib import Path

APP_DIR = Path(__file__).parent.resolve()
APP_SCRIPT = APP_DIR / "app.py"
DESKTOP = Path.home() / "Desktop"
PYTHON = sys.executable


def _set_icon(target: Path) -> None:
    """Best-effort: assign a Stocks.app icon to the shortcut using NSWorkspace."""
    for icon_source in [
        "/System/Applications/Stocks.app",
        "/Applications/Stocks.app",
        "/System/Applications/Utilities/Terminal.app",
        "/Applications/Utilities/Terminal.app",
    ]:
        if Path(icon_source).exists():
            break
    else:
        return

    jxa = f"""
ObjC.import('AppKit');
var ws = $.NSWorkspace.sharedWorkspace;
var icon = ws.iconForFile('{icon_source}');
ws.setIconForFileOptions(icon, '{target}', 0);
"""
    result = subprocess.run(
        ["osascript", "-l", "JavaScript", "-e", jxa],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        print(f"  Icon set from: {Path(icon_source).name}")
    else:
        print(f"  Note: Could not set custom icon ({result.stderr.strip()})")


def make_command_file(dest: Path):
    content = f"""#!/bin/bash
# IBKR Portfolio Manager
# Double-click to launch. Close this window to stop the app.

cd "{APP_DIR}"
echo ""
echo "  ─────────────────────────────────────────"
echo "   IBKR Portfolio Manager"
echo "   Mode: auto-detect (paper or live)"
echo "  ─────────────────────────────────────────"
echo ""

# Stop any previous server instance listening on port 8888 (not clients like browsers)
OLDPID=$(lsof -ti tcp:8888 -sTCP:LISTEN 2>/dev/null)
if [ -n "$OLDPID" ]; then
  echo "  Stopping previous instance (PID $OLDPID)…"
  kill $OLDPID 2>/dev/null
  sleep 1
fi

# Check Python dependencies
"{PYTHON}" -c "import fastapi, uvicorn, ib_insync" 2>/dev/null || {{
  echo "  Installing required packages…"
  "{PYTHON}" -m pip install fastapi uvicorn ib_insync --quiet
}}

"{PYTHON}" "{APP_SCRIPT}"
echo ""
echo "  App stopped. You can close this window."
read -p "  Press Enter to close…"
"""
    dest.write_text(content)
    dest.chmod(dest.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    print(f"  Created: {dest}")


def main():
    print("\nIBKR Portfolio Manager — Setup\n")

    target_dir = DESKTOP if DESKTOP.exists() else APP_DIR

    # Remove old two-shortcut files if they exist
    for old in ["IBKR Portfolio (Paper).command", "IBKR Portfolio (Live).command"]:
        old_path = target_dir / old
        if old_path.exists():
            old_path.unlink()
            print(f"  Removed old shortcut: {old}")

    shortcut = target_dir / "IBKR Portfolio.command"
    make_command_file(shortcut)
    _set_icon(shortcut)

    print(f"""
  Done!

  One shortcut has been placed on your Desktop:

    • IBKR Portfolio.command

  Open TWS (paper or live), then double-click the shortcut.
  The app detects which mode TWS is running in automatically.
  Your browser will open at http://localhost:8888
""")


if __name__ == "__main__":
    main()
