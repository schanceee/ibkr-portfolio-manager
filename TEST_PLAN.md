# IBKR Portfolio Manager — Test Plan

> This document is the single source of truth for all automated tests.
> Every test ID maps to a spec section in [SPECS.md](SPECS.md).
> The CI pipeline runs the full suite on every push to `main`.

---

## How to Run Tests

| Command | What it runs |
|---|---|
| `pytest app/tests/ -v --tb=short` | All unit + API tests (no TWS needed) |
| `pytest app/tests/ -v -m e2e` | E2E tests against real paper TWS |
| `./run_tests.sh` | Unit + API tests with visual output |
| `./run_tests.sh --e2e` | Unit + API tests, then E2E tests against paper TWS |

**CI badge** — tests run automatically on every push and PR to `main` via GitHub Actions.

---

## Test Coverage Overview

| Category | Tests | TWS Required | File |
|---|---|---|---|
| Unit logic | UT-01 to UT-14 | No | `test_logic.py` |
| API (mocked IB) | AT-01 to AT-16 | No | `test_api.py` |
| End-to-end | E2E-01 to E2E-06 | Yes (paper) | `test_e2e.py` |

---

## Unit Tests — `app/tests/test_logic.py`

These tests exercise pure logic functions with no network calls and no FastAPI app.

| ID | Test Name | Spec Section | What it verifies |
|---|---|---|---|
| UT-01 | `test_weight_valid_sums_to_100` | §6 | Weights summing to 100% are accepted |
| UT-02 | `test_weight_invalid_over_100` | §6 | Weights summing to >100% are rejected |
| UT-03 | `test_weight_invalid_under_100` | §6 | Weights summing to <100% are rejected |
| UT-04 | `test_plan_cash_exactly_covers` | §3.2 | Plan includes buy when cash exactly covers the gap |
| UT-05 | `test_plan_excludes_overweight` | §3.2 | Overweight positions are never included in the plan |
| UT-06 | `test_plan_excludes_below_minimum` | §3.2 | Buys below minimum trade size are excluded |
| UT-07 | `test_plan_trims_when_cash_insufficient` | §3.2, §5 | Total included buys never exceed available cash |
| UT-08 | `test_pnl_profit` | §3.4 | P&L > threshold → green flag |
| UT-09 | `test_pnl_small_loss` | §3.4 | Small loss within threshold → green flag |
| UT-10 | `test_pnl_medium_loss` | §3.4 | Loss between threshold/2 and threshold → yellow flag |
| UT-11 | `test_pnl_large_loss` | §3.4 | Loss exceeding threshold → red flag |
| UT-12 | `test_pnl_zero_avg_cost` | §3.4 | P&L is None when avg cost is zero (new position) |
| UT-13 | `test_example_config_has_required_fields` | §6 | config.example.py has all required fields |
| UT-13b | `test_example_config_weights_sum_to_100` | §6 | config.example.py weights sum to 100% |
| UT-13c | `test_real_config_matches_example_structure` | §6 | Local config.py matches example structure (skipped in CI) |
| UT-13d | `test_default_targets_loaded` | §6 | DEFAULT_TARGETS populated from config.py or example |
| UT-14 | `test_delta_calculation` | §3.1 | Delta (current% - target%) computed correctly |

---

## API Tests — `app/tests/test_api.py`

These tests spin up the FastAPI app with a mocked IB client. No real TWS connection is made.
The IB layer is replaced with `unittest.mock.MagicMock` objects that return controlled data.

### How the mock works

```
FastAPI TestClient ──► routes/*.py ──► routes.state (patched)
                                              │
                                    MagicMock IB client
                                    (pre-populated price cache,
                                     contract cache, portfolio data)
```

| ID | Test Name | Spec Section | What it verifies |
|---|---|---|---|
| AT-01 | `test_status_returns_connected` | §Architecture | `/api/status` returns `connected: true` |
| AT-02 | `test_targets_get` | §6 | `/api/targets` returns saved weights summing to 100% |
| AT-03 | `test_targets_save_and_reload` | §6 | Saved weights survive a GET round-trip |
| AT-04 | `test_targets_rejects_invalid_weights` | §6, §5 | Weights not summing to 100% → HTTP 400 |
| AT-05 | `test_plan_returns_quickly` | §Architecture | `/api/plan` completes in < 3s (no blocking ib calls) |
| AT-06 | `test_plan_large_item_excluded_not_small_items` | §5 | When one item exceeds cash, smaller affordable items remain included |
| AT-07 | `test_plan_no_buys_when_all_overweight` | §3.2 | All-overweight portfolio produces empty plan |
| AT-08 | `test_execute_dry_run_does_not_call_place_order` | §3.2 | Dry-run returns status `dry_run`, no `placeOrder` called |
| AT-09 | `test_execute_returns_quickly` | §Architecture | `/api/execute` completes in < 12s (no blocking ib calls) |
| AT-10 | `test_execute_uses_smart_routing` | §Architecture | Orders placed with `exchange='SMART'` |
| AT-11 | `test_execute_error_when_contract_not_in_cache` | §5 | Unknown ticker → error response, no hang |
| AT-12 | `test_trades_returns_list` | §3.5 | `/api/trades` returns empty list when no file exists |
| AT-13 | `test_trades_persisted_after_execute` | §3.5 | Executed orders written to trade log |
| AT-14 | `test_dry_run_not_persisted` | §3.5 | Dry-run orders not written to trade log |
| AT-15 | `test_portfolio_returns_positions_and_cash` | §3.1 | `/api/portfolio` returns positions, cash, total value |
| AT-16 | `test_portfolio_includes_pnl` | §3.4 | Portfolio positions include computed `pnl_pct` |
| AT-17 | `test_portfolio_includes_unmanaged_positions` | §5 | Positions not in target list appear in portfolio |
| AT-18 | `test_portfolio_503_when_disconnected` | §5, §W4 | `/api/portfolio` → 503 when TWS not connected |
| AT-19 | `test_plan_503_when_disconnected` | §5, §W4 | `/api/plan` → 503 when TWS not connected |
| AT-20 | `test_execute_503_when_disconnected` | §5, §W4 | `/api/execute` → 503 when TWS not connected |
| AT-21 | `test_targets_reset_restores_defaults` | §6 | `/api/targets/reset` restores DEFAULT_TARGETS |
| AT-22 | `test_execute_places_only_buy_orders` | §2 | Orders always use `action='BUY'`, never SELL |
| AT-23 | `test_execute_orders_use_day_tif` | §W3 | Orders use `tif='DAY'` (expire end of trading day) |
| AT-24 | `test_plan_reports_shortfall_when_cash_insufficient` | §W2 | Shortfall reported when total_to_invest > cash |
| AT-25 | `test_status_returns_paper_mode` | §2, §3.1 | `/api/status` reports paper or live mode |

---

## End-to-End Tests — `app/tests/test_e2e.py`

These tests connect to a **real paper TWS** running on `127.0.0.1:7497`.
They are excluded from CI (no TWS in GitHub Actions) and must be run manually.

**Pre-conditions before running:**
1. Open TWS in paper trading mode
2. Go to TWS → Edit → Global Configuration → API → Settings
3. Enable "Enable ActiveX and Socket Clients"
4. Ensure port is `7497`
5. Run: `pytest app/tests/test_e2e.py -v -m e2e`
   Or: `./run_tests.sh --e2e`

| ID | Test Name | Spec Section | What it verifies |
|---|---|---|---|
| E2E-01a | `test_e2e_tws_reachable` | §2 | Paper TWS is reachable on port 7497 |
| E2E-01b | `test_e2e_status_connected` | §3.1, §W1 | App connects and reports `connected=true, mode=paper` |
| E2E-02a | `test_e2e_portfolio_returns_data` | §3.1 | `/api/portfolio` returns valid positions and cash |
| E2E-02b | `test_e2e_portfolio_positions_have_required_fields` | §3.1 | Each position has all required fields |
| E2E-03 | `test_e2e_targets_get` | §6 | `/api/targets` returns weights summing to 100% |
| E2E-04a | `test_e2e_plan_returns_valid_structure` | §3.2 | `/api/plan` returns correct structure |
| E2E-04b | `test_e2e_plan_cash_constraint_respected` | §3.2, §5 | Included buys never exceed available cash |
| E2E-04c | `test_e2e_plan_no_sell_positions` | §2 | Plan never contains negative amounts (sells) |
| E2E-04d | `test_e2e_plan_excluded_tickers_respected` | §3.2 | Excluded tickers absent from plan |
| E2E-05a | `test_e2e_dry_run_does_not_place_orders` | §3.2, §3.3 | Dry-run returns `status=dry_run`, no real orders |
| E2E-05b | `test_e2e_dry_run_not_written_to_trade_log` | §3.5 | Dry-run not persisted to trade log |
| E2E-06a | `test_e2e_execute_unknown_ticker_returns_error` | §5 | Unknown ticker → error, no hang |
| E2E-06b | `test_e2e_targets_rejects_invalid_weights` | §6, §5 | Invalid weights → HTTP 400 |

---

## Regression Tests (bugs fixed, must not regress)

These are covered by the API tests but listed here explicitly as regressions to watch for:

| Bug | Covered by | Symptom if regressed |
|---|---|---|
| `/api/plan` blocking on ib_insync calls | AT-05 | Test takes > 3s |
| Cash-trimming excluding all items | AT-06 | Zero items included when cash insufficient |
| `/api/execute` blocking on `portfolio()` / `find_contract()` | AT-09 | Test takes > 12s |
| Orders placed on listing exchange instead of SMART | AT-10 | Orders silently dropped by TWS |
| Weights not persisted when not summing to 100% | AT-04 | Invalid weights saved without error |

---

## When a Test Fails

1. **In CI**: GitHub will mark the push/PR as failed. The failing test name appears in the Actions log.
   - Go to the repo → Actions tab → click the failed run → expand "Run tests" step.
   - The exact test ID and assertion error are printed.

2. **Locally**: Run `pytest app/tests/ -v --tb=short` to see which test failed and why.

3. **To investigate**: Find the test by ID in this document, read its "What it verifies" column,
   and check which spec section it covers. That tells you exactly what broke.

---

## Adding New Tests

When fixing a bug or adding a feature:

1. Add a unit test in `test_logic.py` for pure logic (no IB, no FastAPI)
2. Add an API test in `test_api.py` for endpoint behaviour (mocked IB)
3. Add an E2E test in `test_e2e.py` only if the feature requires real TWS interaction
4. Add a row to this document with the next available ID
5. Run `pytest app/tests/ -v --tb=short` — must be green before committing
