#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# IBKR Portfolio Manager — local test runner
#
# Usage:
#   ./run_tests.sh          Run unit + API tests (no TWS needed)
#   ./run_tests.sh --e2e    Run unit + API tests, then E2E tests against paper TWS
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
TESTS_DIR="$REPO_ROOT/app/tests"

# ── Colours ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

RUN_E2E=false
if [[ "${1:-}" == "--e2e" ]]; then
  RUN_E2E=true
fi

echo ""
echo -e "${BOLD}═══════════════════════════════════════════════════════${RESET}"
echo -e "${BOLD}  IBKR Portfolio Manager — Test Runner${RESET}"
echo -e "${BOLD}═══════════════════════════════════════════════════════${RESET}"
echo ""

# ── Step 1: Unit + API tests (no TWS) ─────────────────────────────────────────
echo -e "${CYAN}▶  Running unit and API tests (no TWS required)...${RESET}"
echo ""

cd "$REPO_ROOT"

UNIT_EXIT=0
pytest "$TESTS_DIR/test_logic.py" "$TESTS_DIR/test_api.py" \
  -v \
  --tb=short \
  --no-header \
  -p no:warnings \
  || UNIT_EXIT=$?

echo ""
if [[ $UNIT_EXIT -eq 0 ]]; then
  echo -e "${GREEN}${BOLD}✓  Unit + API tests PASSED${RESET}"
else
  echo -e "${RED}${BOLD}✗  Unit + API tests FAILED (exit $UNIT_EXIT)${RESET}"
  echo -e "${YELLOW}   Check the output above for the failing test name and assertion.${RESET}"
  echo -e "${YELLOW}   See TEST_PLAN.md for details on each test ID.${RESET}"
fi

echo ""

# ── Step 2: E2E tests (paper TWS required) ────────────────────────────────────
E2E_EXIT=0

if [[ "$RUN_E2E" == "true" ]]; then
  echo -e "${BOLD}═══════════════════════════════════════════════════════${RESET}"
  echo ""
  echo -e "${CYAN}▶  Checking for paper TWS on port 7497...${RESET}"

  if nc -z 127.0.0.1 7497 2>/dev/null; then
    echo -e "${GREEN}   TWS reachable ✓${RESET}"
    echo ""
    echo -e "${CYAN}▶  Running E2E tests against paper TWS...${RESET}"
    echo ""

    pytest "$TESTS_DIR/test_e2e.py" \
      -v \
      --tb=short \
      --no-header \
      -p no:warnings \
      -m e2e \
      || E2E_EXIT=$?

    echo ""
    if [[ $E2E_EXIT -eq 0 ]]; then
      echo -e "${GREEN}${BOLD}✓  E2E tests PASSED${RESET}"
    else
      echo -e "${RED}${BOLD}✗  E2E tests FAILED (exit $E2E_EXIT)${RESET}"
      echo -e "${YELLOW}   Check the output above for failing tests.${RESET}"
      echo -e "${YELLOW}   Make sure paper TWS is running and API is enabled on port 7497.${RESET}"
    fi
  else
    echo -e "${YELLOW}   Paper TWS not reachable on port 7497 — skipping E2E tests.${RESET}"
    echo ""
    echo -e "${YELLOW}   To run E2E tests:${RESET}"
    echo -e "${YELLOW}     1. Open TWS in paper trading mode${RESET}"
    echo -e "${YELLOW}     2. Enable API: Edit → Global Config → API → Settings${RESET}"
    echo -e "${YELLOW}     3. Ensure port is 7497 and 'Enable ActiveX and Socket Clients' is checked${RESET}"
    echo -e "${YELLOW}     4. Re-run: ./run_tests.sh --e2e${RESET}"
    E2E_EXIT=0  # Not a failure — just not available
  fi
  echo ""
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo -e "${BOLD}═══════════════════════════════════════════════════════${RESET}"
echo -e "${BOLD}  Summary${RESET}"
echo -e "${BOLD}═══════════════════════════════════════════════════════${RESET}"
echo ""

if [[ $UNIT_EXIT -eq 0 ]]; then
  echo -e "  ${GREEN}✓${RESET} Unit + API tests"
else
  echo -e "  ${RED}✗${RESET} Unit + API tests  ← FAILED"
fi

if [[ "$RUN_E2E" == "true" ]]; then
  if [[ $E2E_EXIT -eq 0 ]]; then
    echo -e "  ${GREEN}✓${RESET} E2E tests"
  else
    echo -e "  ${RED}✗${RESET} E2E tests  ← FAILED"
  fi
else
  echo -e "  ${YELLOW}—${RESET} E2E tests  (skipped — run ./run_tests.sh --e2e to include)"
fi

echo ""

FINAL_EXIT=$(( UNIT_EXIT + E2E_EXIT ))
if [[ $FINAL_EXIT -eq 0 ]]; then
  echo -e "${GREEN}${BOLD}All tests passed.${RESET}"
else
  echo -e "${RED}${BOLD}One or more test suites failed. See above for details.${RESET}"
fi

echo ""
exit $FINAL_EXIT
