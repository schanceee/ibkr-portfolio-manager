#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# IBKR Portfolio Manager — Visual UI test runner (Playwright)
#
# Starts the app, then runs Playwright tests in a visible browser so you
# can watch every click and navigation as tests execute.
#
# Usage:
#   ./run_ui_tests.sh
#
# Requirements:
#   - Paper TWS running on port 7497 with API enabled
#   - pip3 install playwright && python3 -m playwright install chromium
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
APP_PORT=8889
APP_URL="http://localhost:$APP_PORT"
SERVER_PID=""

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

cleanup() {
  if [[ -n "$SERVER_PID" ]]; then
    echo ""
    echo -e "${YELLOW}▶  Stopping app server (PID $SERVER_PID)...${RESET}"
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
    echo -e "${YELLOW}   Server stopped.${RESET}"
  fi
}
trap cleanup EXIT

echo ""
echo -e "${BOLD}═══════════════════════════════════════════════════════${RESET}"
echo -e "${BOLD}  IBKR Portfolio Manager — Visual UI Tests (Playwright)${RESET}"
echo -e "${BOLD}═══════════════════════════════════════════════════════${RESET}"
echo ""

# ── Pre-check: TWS ────────────────────────────────────────────────────────────
echo -e "${CYAN}▶  Checking paper TWS on port 7497...${RESET}"
if ! nc -z 127.0.0.1 7497 2>/dev/null; then
  echo -e "${RED}   Paper TWS not reachable.${RESET}"
  echo -e "${YELLOW}   Open TWS (paper mode), enable API on port 7497, then retry.${RESET}"
  exit 1
fi
echo -e "${GREEN}   TWS reachable ✓${RESET}"
echo ""

# ── Pre-check: Playwright installed ───────────────────────────────────────────
if ! python3 -c "import playwright" 2>/dev/null; then
  echo -e "${RED}   Playwright not installed.${RESET}"
  echo -e "${YELLOW}   Run: pip3 install playwright && python3 -m playwright install chromium${RESET}"
  exit 1
fi

# ── Start the app server ──────────────────────────────────────────────────────
echo -e "${CYAN}▶  Starting app server on $APP_URL ...${RESET}"
cd "$REPO_ROOT"
python3 app/app.py --port "$APP_PORT" &
SERVER_PID=$!

# Wait for HTTP server to be up
for i in $(seq 1 15); do
  if curl -s "$APP_URL/api/status" >/dev/null 2>&1; then
    echo -e "${GREEN}   HTTP server ready ✓${RESET}"
    break
  fi
  sleep 1
  if [[ $i -eq 15 ]]; then
    echo -e "${RED}   Server did not start in time.${RESET}"
    exit 1
  fi
done

# Wait for IB connection
echo -e "${CYAN}▶  Waiting for IB connection...${RESET}"
for i in $(seq 1 20); do
  STATUS=$(curl -s "$APP_URL/api/status" 2>/dev/null || echo "{}")
  CONNECTED=$(echo "$STATUS" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('connected',False))" 2>/dev/null || echo "False")
  if [[ "$CONNECTED" == "True" ]]; then
    MODE=$(echo "$STATUS" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('mode','?'))" 2>/dev/null || echo "?")
    echo -e "${GREEN}   IB connected ✓  (mode: $MODE)${RESET}"
    break
  fi
  printf "   Attempt %d/20...\r" "$i"
  sleep 1
  if [[ $i -eq 20 ]]; then
    echo -e "${YELLOW}   Warning: IB not yet connected — some tests may skip.${RESET}"
  fi
done
echo ""

# ── Run Playwright UI tests ───────────────────────────────────────────────────
echo -e "${BOLD}═══════════════════════════════════════════════════════${RESET}"
echo -e "${CYAN}▶  Launching browser and running UI tests...${RESET}"
echo -e "${YELLOW}   Watch the browser window that's about to open.${RESET}"
echo -e "${BOLD}═══════════════════════════════════════════════════════${RESET}"
echo ""
sleep 1

UI_EXIT=0
E2E_BASE_URL="$APP_URL" SLOW_MO=700 pytest app/tests/test_ui.py \
  -v \
  -s \
  --tb=short \
  --no-header \
  -p no:warnings \
  -m ui \
  || UI_EXIT=$?

echo ""
echo -e "${BOLD}═══════════════════════════════════════════════════════${RESET}"
if [[ $UI_EXIT -eq 0 ]]; then
  echo -e "${GREEN}${BOLD}✓  All UI tests PASSED${RESET}"
else
  echo -e "${RED}${BOLD}✗  UI tests FAILED (exit $UI_EXIT)${RESET}"
  echo -e "${YELLOW}   Check the output above for the failing test.${RESET}"
fi
echo ""

exit $UI_EXIT
