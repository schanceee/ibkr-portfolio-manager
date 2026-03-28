# IBKR Portfolio Manager — Backlog

> Prioritised list of user stories, dev tasks, and test cases.
> Status: ⬜ todo · 🔄 in progress · ✅ done

---

## Milestones

| # | Milestone | Goal |
|---|---|---|
| M1 | **Core plumbing** | App starts, connects to TWS, shows live data |
| M2 | **Portfolio view** | Full dashboard with editable weights and charts |
| M3 | **Rebalancing** | Plan + execute trades from the UI |
| M4 | **P&L indicators** | Avg cost column, drawdown flag |
| M5 | **Desktop shortcut** | One double-click launch, no terminal knowledge required |
| M6 | **Polish & README** | Error handling, edge cases, docs |

---

## User Stories

### M1 — Core plumbing

---

**US-01** · As a user, I want the app to refuse to show any data if TWS is not running, so I never accidentally think I'm seeing live data when I'm not.

- App attempts to connect to TWS on startup
- If connection fails, shows the disconnected screen (W4)
- All action buttons are disabled
- App retries connection every 10 seconds in the background
- When TWS comes online mid-session, app reconnects automatically and loads data

---

**US-02** · As a user, I want the app to clearly show whether I'm in PAPER or LIVE mode at all times, so I never accidentally place a real order thinking it's a test.

- Mode is set at launch via `--live` flag (default: paper)
- Mode badge visible on every screen: green = PAPER, red = LIVE
- Mode cannot be changed without restarting the app

---

**US-03** · As a user, I want the app to fetch my current positions and cash balance from TWS, so I see real data without having to enter anything manually.

- Fetches all positions with market value and currency
- Fetches CHF cash balance
- Shows "last updated" timestamp
- "Refresh" button re-fetches without restarting

---

### M2 — Portfolio view

---

**US-04** · As a user, I want to see my current portfolio in a table with current weight vs. target weight and the gap, so I understand at a glance where I'm off.

- Table columns: Ticker, Value (CHF), Current %, Target %, Delta (pp)
- Delta column colour-coded: red (large underweight), yellow (small underweight), green (on target), blue (overweight)
- Cash shown as a non-editable row at the bottom

---

**US-05** · As a user, I want to edit target weights directly in the table, so I don't have to edit a config file and restart anything.

- Target % cells are editable inline (click to edit)
- Deltas recalculate instantly on each keystroke
- Weights sum validator shown below the table
- Warning shown if weights ≠ 100%, Execute button disabled until fixed
- Edited weights auto-saved to `app_config.json` on blur

---

**US-06** · As a user, I want a "Reset to defaults" button that restores target weights from `config.py`, so I can always go back to my original allocation.

- Button visible on the dashboard
- Requires a single click confirmation ("Are you sure?")
- Reloads weights from `config.py` and saves to `app_config.json`

---

**US-07** · As a user, I want a bar chart showing current vs. target allocation, so I get a visual sense of the gap without reading every number.

- Horizontal bar chart, one row per position
- Two bars per position: current (solid) and target (outline)
- Overweight shown in a distinct colour (e.g. blue)
- Chart updates live when I edit target weights

---

### M3 — Rebalancing

---

**US-08** · As a user, I want to see a computed list of buy orders needed to reach my target, so I know exactly what to execute before clicking anything.

- Rebalancing tab/panel shows: Ticker, Gap (pp), Suggested Buy (CHF), Estimated Qty
- Rows below minimum trade size are greyed out and excluded automatically
- Minimum trade size is configurable via a slider/input (default CHF 500)
- Overweight positions show no buy suggestion

---

**US-09** · As a user, I want to see whether I have enough cash to fund all suggested buys, so I know upfront if I need to adjust.

- "Total to invest" vs "Available cash" shown below the table
- If total > cash, a shortfall warning is shown
- Smallest buys are auto-excluded until total ≤ available cash
- I can manually toggle individual rows in/out of the plan

---

**US-10** · As a user, I want a dry-run that shows me what would happen without placing any orders, so I can sanity-check the plan.

- "Run dry-run" button simulates the plan: shows each order with qty and limit price
- No connection to TWS order system during dry-run
- Results clearly labelled "DRY RUN — no orders placed"

---

**US-11** · As a user, I want to execute the rebalancing plan with a confirmation step, so I never accidentally place orders.

- "Execute buys" button opens the confirmation modal (W3)
- Modal lists every order: ticker, qty, limit price, CHF amount
- Mode badge (PAPER / LIVE) shown prominently in modal
- "Cancel" closes modal, nothing happens
- "Confirm & Execute" places orders via TWS
- Order results shown inline after execution (filled / pending / error)

---

### M4 — P&L indicators

---

**US-12** · As a user, I want to see my average cost per position and the current unrealised P&L in %, so I immediately notice if something has dropped significantly.

- Columns added to dashboard table: Avg Cost (CHF), P&L %
- P&L % = (current price − avg cost) / avg cost
- Colour-coded flag: 🟢 > -5% / 🟡 -5% to -10% / 🔴 below -10%
- Threshold (-10%) configurable in `app_config.json`
- Average cost fetched from TWS account data (already returned by `ib_insync`)

---

**US-13** · As a user, I want positions with a large drawdown to stand out visually, so I don't miss them in a longer table.

- Entire row background tinted red (subtle) when P&L flag is 🔴
- Tooltip on the flag shows: avg cost, current price, exact P&L %, CHF loss

---

### M5 — Desktop shortcut

---

**US-14** · As a user, I want to launch the app by double-clicking a Desktop icon, so I never have to open a terminal.

- `python setup.py` creates two `.command` files on the Desktop:
  - `IBKR Portfolio (Paper).command`
  - `IBKR Portfolio (Live).command`
- Double-clicking either opens a Terminal window, starts the server, and opens the browser
- The `.command` files work even if the user moves the `IBKR-Investments` folder, by using relative paths resolved at runtime
- The setup script is idempotent (safe to re-run)

---

### M6 — Polish & README

---

**US-15** · As a user, I want a README that tells me everything I need to do to get started, so I don't need to read code or ask anyone.

- README covers: prerequisites (Python, TWS API enabled), one-time setup, daily use, troubleshooting common errors

---

**US-16** · As a user, I want clear error messages when something goes wrong (TWS disconnects mid-session, order rejected, price data unavailable), so I understand what happened and what to do.

- TWS mid-session disconnect: banner appears, data freezes, app retries
- Order rejected: per-row error message in the order results
- No price data: position shown with "—" in price/P&L columns, no crash

---

---

## Dev Tasks

### M1 — Core plumbing

| ID | Task | Notes |
|---|---|---|
| T-01 | Scaffold FastAPI app (`app/app.py`) with `--live` flag | Reads port from flag, starts uvicorn, opens browser |
| T-02 | `GET /api/status` endpoint | Returns `{ connected, mode, port, last_checked }` |
| T-03 | `GET /api/portfolio` endpoint | Wraps `ib_client.get_portfolio_positions()` + `get_account_cash()` |
| T-04 | Auto-retry connection loop (background task) | Retries every 10s if disconnected |
| T-05 | Serve `static/index.html` from FastAPI | All frontend from one file |

### M2 — Portfolio view

| ID | Task | Notes |
|---|---|---|
| T-06 | `GET /api/targets` endpoint | Reads `app_config.json`, falls back to `config.py` |
| T-07 | `POST /api/targets` endpoint | Validates weights sum ≤ 100.01%, saves to `app_config.json` |
| T-08 | Frontend: portfolio table with editable target % cells | Inline edit, blur saves via POST /api/targets |
| T-09 | Frontend: delta calculation in JS | Runs client-side on every input event |
| T-10 | Frontend: weight sum validator | Shows warning + disables Execute if ≠ 100% |
| T-11 | Frontend: Chart.js horizontal bar chart | Current vs target, updates on edit |
| T-12 | Frontend: connection status banner | Polls GET /api/status every 5s |
| T-13 | Frontend: mode badge (PAPER / LIVE) | Colour-coded, always visible in header |

### M3 — Rebalancing

| ID | Task | Notes |
|---|---|---|
| T-14 | `POST /api/plan` endpoint | Wraps `portfolio_manager.get_rebalancing_plan()`, accepts min_trade param |
| T-15 | `POST /api/execute` endpoint | Wraps `portfolio_manager.execute_rebalancing_plan()`, returns per-order results |
| T-16 | Frontend: rebalancing panel | Table, min-trade slider, cash warning |
| T-17 | Frontend: per-row include/exclude toggle | Sends included tickers with POST /api/plan |
| T-18 | Frontend: dry-run display | Results panel labelled clearly |
| T-19 | Frontend: confirmation modal | Order list, mode badge, Cancel / Confirm buttons |

### M4 — P&L indicators

| ID | Task | Notes |
|---|---|---|
| T-20 | Extend `GET /api/portfolio` to include avg cost | `ib_insync` returns `avgCost` on position objects |
| T-21 | Frontend: P&L column in dashboard table | Calculated client-side from avg cost + current price |
| T-22 | Frontend: row highlight for large drawdowns | Red tint + tooltip |
| T-23 | `app_config.json`: add `pnl_alert_threshold` field | Default -10, editable in config |

### M5 — Desktop shortcut

| ID | Task | Notes |
|---|---|---|
| T-24 | `setup.py` script | Creates `.command` files on Desktop, sets executable bit |
| T-25 | `.command` file template | Resolves project path at runtime, launches app, opens browser |

### M6 — Polish & README

| ID | Task | Notes |
|---|---|---|
| T-26 | `README.md` — setup & daily use | Prerequisites, setup steps, troubleshooting |
| T-27 | Error handling: TWS mid-session disconnect | Frontend detects via status poll, freezes UI gracefully |
| T-28 | Error handling: order rejected | Returns structured error per order in POST /api/execute |
| T-29 | Error handling: no price data | Returns null for price fields, frontend shows "—" |

---

---

## Test Cases

### Unit Tests (automated, run with `pytest`)

These test logic in isolation, no TWS required.

---

**UT-01** — Weight validation: valid case
```
Input:  { SUSW: 50, XDWT: 20, CHDVD: 10, XDWH: 10, CHSPI: 5, NUKL: 5 }
Expect: valid = True
```

**UT-02** — Weight validation: sum > 100
```
Input:  { SUSW: 50, XDWT: 25, CHDVD: 15, XDWH: 10, CHSPI: 5, NUKL: 5 }
Expect: valid = False, error = "Weights sum to 110%, must be 100%"
```

**UT-03** — Weight validation: sum < 100
```
Input:  { SUSW: 40, XDWT: 20, CHDVD: 10, XDWH: 10, CHSPI: 5, NUKL: 5 }
Expect: valid = False, error = "Weights sum to 90%, must be 100%"
```

**UT-04** — Rebalancing plan: cash exactly covers buys
```
Positions: SUSW 5000, cash 5000, total 10000
Targets:   SUSW 100%
Expect:    plan = [{ ticker: SUSW, buy_chf: 5000 }]
```

**UT-05** — Rebalancing plan: cash does not cover all buys
```
Positions: SUSW 2000, XDWT 2000, cash 1000, total 5000
Targets:   SUSW 60%, XDWT 40%
Current:   SUSW 40%, XDWT 40%
Expect:    SUSW needs CHF 1000 → included (cash exactly covers)
           XDWT is on target → no buy
```

**UT-06** — Rebalancing plan: buy below minimum excluded
```
Positions: XDWH 2650, cash 500, total 3150
Target:    XDWH 85%, current 84.1%
Gap:       ~CHF 28 buy needed
Min trade: CHF 500
Expect:    plan = [] (buy excluded, below minimum)
```

**UT-07** — Rebalancing plan: overweight position not bought
```
Positions: NUKL 2664, total 15000
Target:    NUKL 5%
Current:   NUKL 17.8% (overweight)
Expect:    NUKL not in plan
```

**UT-08** — P&L calculation: profit
```
avg_cost = 100, current_price = 110
Expect: pnl_pct = +10.0%,  flag = "green"
```

**UT-09** — P&L calculation: small loss
```
avg_cost = 100, current_price = 96
Expect: pnl_pct = -4.0%, flag = "green"
```

**UT-10** — P&L calculation: medium loss (yellow zone)
```
avg_cost = 100, current_price = 92
Expect: pnl_pct = -8.0%, flag = "yellow"
```

**UT-11** — P&L calculation: large loss (red zone)
```
avg_cost = 100, current_price = 88
Expect: pnl_pct = -12.0%, flag = "red"
```

**UT-12** — P&L calculation: position with zero avg cost (not yet held)
```
avg_cost = 0, current_price = 55
Expect: pnl_pct = None, flag = None (no P&L shown)
```

**UT-13** — Config fallback: `app_config.json` missing
```
Given:  app_config.json does not exist
Expect: targets loaded from config.py defaults
        app_config.json created on first save
```

**UT-14** — Delta calculation
```
current_pct = 23.7, target_pct = 50.0
Expect: delta = -26.3 pp
```

---

### Integration Tests (automated, requires TWS paper account running)

These test the full stack: frontend → API → ib_insync → TWS.

---

**IT-01** — Status endpoint when TWS running
```
GET /api/status
Expect: { connected: true, mode: "paper", port: 7497 }
```

**IT-02** — Status endpoint when TWS not running
```
GET /api/status (with TWS closed)
Expect: { connected: false }
Status: 200 (not 500 — disconnected is a valid state, not an error)
```

**IT-03** — Portfolio fetch returns expected shape
```
GET /api/portfolio
Expect: {
  positions: [{ ticker, value_chf, current_pct, avg_cost, pnl_pct }],
  cash_chf: number,
  total_value_chf: number,
  last_updated: ISO timestamp
}
```

**IT-04** — Save and reload targets
```
POST /api/targets  { SUSW: 40, XDWT: 25, ... (sums to 100) }
GET  /api/targets
Expect: returned targets match what was posted
```

**IT-05** — Plan endpoint returns buy list
```
POST /api/plan { min_trade: 500 }
Expect: list of { ticker, gap_pp, suggested_chf, estimated_qty }
        no overweight tickers in list
        no tickers below min_trade in list
```

**IT-06** — Dry-run execute does not place orders
```
POST /api/execute { dry_run: true, orders: [...] }
Expect: response contains simulated results
        no open orders in TWS paper account after call
```

**IT-07** — Live execute places orders in TWS paper account
```
POST /api/execute { dry_run: false, orders: [{ ticker: SUSW, qty: 1 }] }
Expect: order appears in TWS paper account open orders
        response: { ticker: SUSW, status: "submitted", order_id: ... }
```

---

### Manual / Smoke Tests (checklist, run before each release)

---

**MT-01 — TWS disconnected on launch**
- [ ] Close TWS
- [ ] Double-click Desktop shortcut
- [ ] Verify: disconnected banner shown, all buttons disabled
- [ ] Open TWS
- [ ] Wait 15s
- [ ] Verify: app reconnects automatically, portfolio loads

**MT-02 — Mode badge visibility**
- [ ] Launch in paper mode
- [ ] Verify: green "PAPER MODE" badge in header
- [ ] Quit, relaunch with `--live`
- [ ] Verify: red "LIVE MODE" badge in header, badge visible on confirmation modal

**MT-03 — Inline weight editing**
- [ ] Click on SUSW target % cell
- [ ] Change from 50 to 45
- [ ] Verify: delta updates immediately, weight sum shows 95% with warning
- [ ] Change XDWT from 20 to 25
- [ ] Verify: weight sum shows 100% ✓, warning gone
- [ ] Refresh page
- [ ] Verify: weights still show 45 / 25 (persisted)

**MT-04 — Reset to defaults**
- [ ] Edit some weights (make them different from config.py)
- [ ] Click "Reset to defaults"
- [ ] Click confirm in the dialog
- [ ] Verify: weights return to SUSW 50, XDWT 20, etc.

**MT-05 — Rebalancing plan respects minimum trade**
- [ ] Set minimum trade to CHF 5,000
- [ ] Verify: only positions with large gaps remain in plan
- [ ] Set minimum trade to CHF 0
- [ ] Verify: all underweight positions appear in plan

**MT-06 — Cash shortfall warning**
- [ ] Manually set all targets high to generate large buys
- [ ] Verify: shortfall warning appears if total > cash
- [ ] Verify: smallest buys are auto-excluded until shortfall disappears

**MT-07 — Confirmation modal (paper)**
- [ ] Click "Execute buys" with a valid plan
- [ ] Verify: modal shows PAPER badge in green
- [ ] Verify: order list matches the plan
- [ ] Click "Cancel"
- [ ] Verify: modal closes, no orders placed
- [ ] Click "Execute buys" again → "Confirm & Execute"
- [ ] Verify: order results shown (paper account)

**MT-08 — P&L flag colour logic**
- [ ] Verify: position with <5% loss shows green flag
- [ ] Verify: position with ~8% loss shows yellow flag
- [ ] Verify: position with >10% loss shows red flag and tinted row
- [ ] Hover over red flag → verify tooltip shows avg cost, current price, CHF loss

**MT-09 — Desktop shortcut (macOS)**
- [ ] Run `python setup.py`
- [ ] Verify: two `.command` files appear on Desktop
- [ ] Double-click paper shortcut
- [ ] Verify: Terminal window opens, browser opens at localhost:8888
- [ ] Close Terminal window
- [ ] Verify: browser shows connection error (server stopped)

**MT-10 — TWS mid-session disconnect**
- [ ] Launch app with TWS running
- [ ] Load portfolio data
- [ ] Quit TWS
- [ ] Wait 15s
- [ ] Verify: disconnected banner appears, data shown but labelled as stale
- [ ] Verify: Execute button is disabled

---

## Priority Order for Dev

```
T-01 → T-02 → T-03 → T-05          (M1: get the app running and connected)
T-06 → T-07 → T-08 → T-09 → T-10  (M2a: targets + editable table)
T-11 → T-12 → T-13                 (M2b: chart + status banner)
T-14 → T-15 → T-16 → T-17         (M3a: plan)
T-18 → T-19                        (M3b: dry-run + execute)
T-20 → T-21 → T-22 → T-23         (M4: P&L)
T-04 → T-27 → T-28 → T-29         (M1+M6: resilience)
T-24 → T-25                        (M5: desktop shortcut)
T-26                                (M6: README)
```
