#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# IBKR Portfolio Manager — Visual E2E test runner
#
# Starts the real app server, opens it in your browser, then runs the E2E
# test suite against it so you can watch the app respond to each test.
#
# Usage:
#   ./run_e2e_visual.sh
#
# Requirements:
#   - Paper TWS must be running on port 7497 with API enabled
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
APP_PORT=8889   # Use a different port so it doesn't conflict with your normal app
APP_URL="http://localhost:$APP_PORT"
SERVER_PID=""

# ── Colours ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

cleanup() {
  if [[ -n "$SERVER_PID" ]]; then
    echo ""
    echo -e "${YELLOW}▶  Stopping test server (PID $SERVER_PID)...${RESET}"
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
    echo -e "${YELLOW}   Server stopped.${RESET}"
  fi
}
trap cleanup EXIT

# ── Pre-check: TWS reachable ──────────────────────────────────────────────────
echo ""
echo -e "${BOLD}═══════════════════════════════════════════════════════${RESET}"
echo -e "${BOLD}  IBKR Portfolio Manager — Visual E2E Test Runner${RESET}"
echo -e "${BOLD}═══════════════════════════════════════════════════════${RESET}"
echo ""

echo -e "${CYAN}▶  Checking paper TWS on port 7497...${RESET}"
if ! nc -z 127.0.0.1 7497 2>/dev/null; then
  echo -e "${RED}   Paper TWS not reachable on port 7497.${RESET}"
  echo ""
  echo -e "${YELLOW}   To run visual E2E tests:${RESET}"
  echo -e "${YELLOW}     1. Open TWS in paper trading mode${RESET}"
  echo -e "${YELLOW}     2. Edit → Global Config → API → Settings${RESET}"
  echo -e "${YELLOW}     3. Enable 'Enable ActiveX and Socket Clients', port 7497${RESET}"
  echo -e "${YELLOW}     4. Re-run: ./run_e2e_visual.sh${RESET}"
  exit 1
fi
echo -e "${GREEN}   TWS reachable ✓${RESET}"
echo ""

# ── Start the app server ──────────────────────────────────────────────────────
echo -e "${CYAN}▶  Starting app server on port $APP_PORT...${RESET}"
cd "$REPO_ROOT"
python3 app/app.py --port "$APP_PORT" &
SERVER_PID=$!

# Wait for server to be ready
echo -e "${CYAN}   Waiting for server to start...${RESET}"
for i in $(seq 1 15); do
  if curl -s "$APP_URL/api/status" >/dev/null 2>&1; then
    echo -e "${GREEN}   Server ready ✓${RESET}"
    break
  fi
  sleep 1
  if [[ $i -eq 15 ]]; then
    echo -e "${RED}   Server did not start in time.${RESET}"
    exit 1
  fi
done
echo ""

# Wait for IB connection
echo -e "${CYAN}▶  Waiting for IB connection to establish...${RESET}"
for i in $(seq 1 20); do
  STATUS_JSON=$(curl -s "$APP_URL/api/status" 2>/dev/null || echo "{}")
  CONNECTED=$(echo "$STATUS_JSON" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('connected','false'))" 2>/dev/null || echo "false")
  if [[ "$CONNECTED" == "True" ]] || [[ "$CONNECTED" == "true" ]]; then
    MODE=$(echo "$STATUS_JSON" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('mode','?'))" 2>/dev/null || echo "?")
    echo -e "${GREEN}   IB connected ✓  (mode: $MODE)${RESET}"
    break
  fi
  printf "   Attempt %d/20...\r" "$i"
  sleep 1
  if [[ $i -eq 20 ]]; then
    echo -e "${YELLOW}   Warning: IB not yet connected — tests may fail or skip.${RESET}"
  fi
done
echo ""

# ── Open browser ─────────────────────────────────────────────────────────────
echo -e "${CYAN}▶  Opening browser at $APP_URL ...${RESET}"
open "$APP_URL" 2>/dev/null || xdg-open "$APP_URL" 2>/dev/null || true
echo -e "${YELLOW}   Watch the app in your browser as tests run below.${RESET}"
echo ""
sleep 1

# ── Run E2E tests against the live server ─────────────────────────────────────
echo -e "${BOLD}═══════════════════════════════════════════════════════${RESET}"
echo -e "${CYAN}▶  Running E2E tests against $APP_URL ...${RESET}"
echo -e "${BOLD}═══════════════════════════════════════════════════════${RESET}"
echo ""

E2E_EXIT=0
E2E_BASE_URL="$APP_URL" pytest app/tests/test_e2e.py \
  -v \
  -s \
  --tb=short \
  --no-header \
  -p no:warnings \
  -m e2e \
  || E2E_EXIT=$?

echo ""
echo -e "${BOLD}═══════════════════════════════════════════════════════${RESET}"
if [[ $E2E_EXIT -eq 0 ]]; then
  echo -e "${GREEN}${BOLD}✓  All E2E tests PASSED${RESET}"
else
  echo -e "${RED}${BOLD}✗  E2E tests FAILED (exit $E2E_EXIT)${RESET}"
  echo -e "${YELLOW}   Check the output above for the failing test and assertion.${RESET}"
  echo -e "${YELLOW}   See TEST_PLAN.md for details on each E2E test ID.${RESET}"
fi
echo ""

exit $E2E_EXIT
