# IBKR Portfolio Manager — App Specifications

> Version 1.1 | March 2026

---

## 1. Product Overview

A **local web app** that runs on your laptop and opens in your browser. It connects to your already-running IBKR Trader Workstation (TWS) — exactly like your Python scripts do today — and gives you a visual, interactive interface to:

- See your live portfolio vs. your target allocation
- Adjust target weights in a table (like Excel)
- See the gap (delta) between where you are and where you want to be
- Execute buys to close that gap, with a confirmation step

No server, no cloud, no hosting. Double-click a shortcut on your Desktop — the app starts and your browser opens automatically. When you close the app, it stops.

---

## 2. Constraints & Non-Negotiables

| Constraint | Detail |
|---|---|
| **Desktop shortcut** | Double-click to launch, no terminal required |
| **Local only** | App runs on your machine, never deployed anywhere |
| **TWS must be open** | The app refuses to operate if TWS is not running. This is your security gate. |
| **No selling** | App only places BUY orders, never SELL |
| **Paper vs. Live** | Clear, unmistakable mode indicator at all times |
| **Confirmation before trades** | Any order requires an explicit confirm step |
| **CHF as base currency** | All amounts displayed in CHF |

---

## 3. Pages & Features

### 3.1 Portfolio Dashboard (main page)

**What it shows:**
- Connection status banner (TWS connected / disconnected, PAPER or LIVE mode)
- Your current portfolio as a table: ticker, current value (CHF), current weight (%), target weight (%), delta (pp)
- A bar chart or donut chart showing current vs. target allocation side by side
- Total portfolio value, total cash available, last refreshed timestamp
- A "Refresh" button to re-fetch live data from TWS

**The target weights column is editable directly in the table.** You change a number, hit Enter or Tab, and the deltas recalculate instantly. The weights must sum to 100% — the app warns you if they don't.

The table also shows a **P&L column**: current price vs. your average buy price (fetched from TWS). If a position is down more than 10% from your average cost, the row is flagged with a red indicator. The threshold is configurable. No sophisticated analytics — just a simple flag so you notice a big drawdown at a glance.

---

### 3.2 Rebalancing Panel (side panel or second tab)

**What it shows:**
- Based on your current portfolio + edited targets, a list of recommended buys
- Each row: ticker, current weight, target weight, gap, suggested buy amount (CHF), suggested quantity
- A "Minimum buy" slider or input (default CHF 500, from your existing config)
- Rows below the minimum are greyed out / excluded
- Total cash required vs. cash available — highlighted red if you don't have enough

**Actions:**
- "Run dry-run" — shows what would happen, no orders placed
- "Execute buys" — opens a confirmation modal then places limit orders via TWS

---

### 3.3 Confirmation Modal (before any trade)

- Lists every order about to be placed: ticker, qty, limit price, CHF amount
- Shows PAPER or LIVE in large text with a colored badge (green = paper, red = live)
- Requires clicking a "Confirm & Execute" button (not just pressing Enter)
- Shows order results after execution (filled, pending, error)

---

### 3.4 P&L Summary Strip

A compact row below the main table showing for each position:
- Average cost (from TWS)
- Current price
- Unrealised P&L in % and CHF
- A simple flag: 🟢 fine / 🟡 -5% to -10% / 🔴 below -10%

No historical chart needed for v1. Just the number and the flag. Threshold for the red flag is configurable in `app_config.json` (default: -10%).

### 3.5 History Tab (optional, v2)

- List of past orders placed through the app
- Sourced from your existing `purchase_history.json`

---

## 4. User Flows

### Flow A — Morning check, no trades

```
Open terminal → python app.py
Browser opens → Dashboard loads
See current portfolio vs. targets
No action needed → Close browser
```

### Flow B — Monthly rebalance

```
Transfer money to IB account (done externally)
Open TWS (paper or live)
python app.py --live   (or just python app.py for paper)
Browser opens → Dashboard loads
Tweak target weights if needed (edit table inline)
Switch to Rebalancing tab
Review recommended buys, adjust minimum trade if needed
Click "Execute buys"
Confirmation modal → review orders → click "Confirm & Execute"
See order results
Close app
```

### Flow C — TWS not open

```
python app.py
Browser opens → Red banner: "Cannot connect to TWS. Please open Trader Workstation first."
All action buttons disabled
```

---

## 5. States & Edge Cases

| Situation | App Behaviour |
|---|---|
| TWS not running | Red connection banner, all buttons disabled, auto-retries every 10s |
| Weights don't sum to 100% | Yellow warning on the weights column, Execute button disabled |
| Not enough cash for all buys | Cash row turns red, buys exceeding available cash are excluded |
| Order rejected by IBKR | Show error inline next to the order row |
| Market closed | Show warning, orders will be day orders that expire at next open |
| Position not in target list | Show as "unmanaged" row in grey |

---

## 6. Target Allocation Persistence

The target weights you set in the app are **saved locally** (to a JSON file on your machine). Next time you open the app, your last weights are pre-loaded. You can reset to the defaults from `config.py` at any time with a "Reset to defaults" button.

---
---

# Wireframes

> ASCII wireframes. Numbers in [brackets] reference notes below each wireframe.

---

## W1 — Dashboard (main view)

```
┌─────────────────────────────────────────────────────────────────────┐
│  IBKR Portfolio Manager                      [1] ● PAPER MODE       │
│                                                   TWS Connected ✓   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Portfolio Value: CHF 27,363    Cash: CHF 12,169    [Refresh ↺]    │
│  Last updated: today 09:14                                          │
│                                                                     │
│ ┌───────────────────────────────────────────────────────────────────┐ │
│ │ Ticker │ Value(CHF) │ Cur% │ Target% │ Delta  │ Avg Cost │ P&L [5]│ │
│ ├────────┼────────────┼──────┼─────────┼────────┼──────────┼────────┤ │
│ │ SUSW   │  6,475     │23.7% │[50.0]✎  │-26.3pp │  CHF 118 │ +5.2%🟢│ │
│ │ XDWT   │  3,402     │12.4% │[20.0]✎  │ -7.6pp │   CHF 89 │ -2.1%🟢│ │
│ │ CHDVD  │      0     │ 0.0% │[10.0]✎  │-10.0pp │      —   │    — │ │
│ │ XDWH   │  2,654     │ 9.7% │[10.0]✎  │ -0.3pp │   CHF 71 │-11.4%🔴│ │
│ │ CHSPI  │      0     │ 0.0% │ [5.0]✎  │ -5.0pp │      —   │    — │ │
│ │ NUKL   │  2,664     │ 9.7% │ [5.0]✎  │ +4.7pp │   CHF 55 │ -6.8%🟡│ │
│ │ Cash   │ 12,169     │44.5% │    —    │    —   │      —   │    — │ │
│ └───────────────────────────────────────────────────────────────────┘ │
│                                          [3] Weights sum: 100% ✓   │
│                                                                     │
│  [4] Current vs. Target Allocation                                  │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ SUSW   ████████████████████████████████░░░░░░░░░░░░░░░░░░░  │   │
│  │ XDWT   ████████████░░░░░░░░░░░░░░░░░░░░                     │   │
│  │ CHDVD  ░░░░░░░░░░░░░░░░░░░░                                  │   │
│  │ XDWH   █████████░░░░                                         │   │
│  │ CHSPI  ░░░░░░░░░░                                            │   │
│  │ NUKL   █████████▓▓▓▓▓                                        │   │
│  │        ─── Current  ░░░ Target   ▓▓▓ Over target            │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│                        [Go to Rebalancing →]                        │
└─────────────────────────────────────────────────────────────────────┘
```

**Notes:**
- [1] Mode badge: green background = PAPER, red background = LIVE. Always visible.
- [2] Delta column: red = significantly underweight, yellow = slightly under, green = on target, blue = overweight
- [3] Weight sum validator: turns red and shows warning if total ≠ 100%
- [4] Horizontal bar chart, each row has two bars (current in solid, target in outline)
- [5] P&L vs average cost: 🟢 > -5% / 🟡 -5% to -10% / 🔴 below -10%. Threshold configurable in settings.

---

## W2 — Rebalancing Panel

```
┌─────────────────────────────────────────────────────────────────────┐
│  IBKR Portfolio Manager                      [1] ● LIVE MODE  🔴   │
│                                                   TWS Connected ✓   │
├─────────────────────────────────────────────────────────────────────┤
│  [← Back to Portfolio]          Rebalancing Plan                    │
│                                                                     │
│  Available Cash: CHF 12,169                                         │
│  Min. trade size:  [CHF 500  ▼]                                     │
│                                                                     │
│ ┌─────────────────────────────────────────────────────────────────┐ │
│ │ Ticker │ Gap (pp) │ Suggested Buy │ Est. Qty │ Include? │        │ │
│ ├────────┼──────────┼───────────────┼──────────┼──────────┤        │ │
│ │ SUSW   │ -26.3 pp │  CHF 7,195   │    ~54   │   ✓ [5]  │        │ │
│ │ XDWT   │  -7.6 pp │  CHF 2,080   │    ~14   │   ✓      │        │ │
│ │ CHDVD  │ -10.0 pp │  CHF 2,736   │    ~18   │   ✓      │        │ │
│ │ XDWH   │  -0.3 pp │    CHF 82    │     ~1   │   — [6]  │        │ │
│ │ CHSPI  │  -5.0 pp │  CHF 1,368   │     ~9   │   ✓      │        │ │
│ │ NUKL   │  +4.7 pp │      —       │     —    │   — [7]  │        │ │
│ └─────────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  Total to invest:  CHF 13,459                                       │
│  Available cash:   CHF 12,169                                [8]    │
│  ─────────────────────────────                                      │
│  Shortfall:       -CHF  1,290   ⚠  Some buys will be excluded      │
│                                                                     │
│         [Run Dry-Run]          [Execute Buys →]                     │
└─────────────────────────────────────────────────────────────────────┘
```

**Notes:**
- [5] Checkbox per row lets you manually include/exclude a position from the plan
- [6] XDWH greyed out — below minimum trade size (CHF 82 < CHF 500)
- [7] NUKL greyed out — already overweight, no buy suggested
- [8] If total > available cash, smallest buys get automatically excluded, shortfall is shown in red

---

## W3 — Confirmation Modal

```
        ┌──────────────────────────────────────────────┐
        │                                              │
        │   ⚠  LIVE TRADING — REAL MONEY  ⚠           │
        │   ─────────────────────────────────────────  │
        │                                              │
        │  You are about to place 4 orders:            │
        │                                              │
        │  SUSW    54 shares    limit CHF 133.5        │
        │  XDWT    14 shares    limit CHF  87.2        │
        │  CHDVD   18 shares    limit CHF  72.1        │
        │  CHSPI    9 shares    limit CHF  89.4        │
        │                                              │
        │  Total cash:  ~CHF 12,169                    │
        │  Orders expire at end of trading day         │
        │                                              │
        │  ┌──────────────┐   ┌───────────────────┐   │
        │  │    Cancel    │   │ Confirm & Execute  │   │
        │  └──────────────┘   └───────────────────┘   │
        │                                              │
        └──────────────────────────────────────────────┘
```

---

## W4 — TWS Disconnected State

```
┌─────────────────────────────────────────────────────────────────────┐
│  IBKR Portfolio Manager                         ● NOT CONNECTED 🔴 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  🔴  Cannot connect to Trader Workstation                   │   │
│  │                                                             │   │
│  │  Please open TWS or IB Gateway on this machine, then        │   │
│  │  make sure the API is enabled (port 7497 for paper,         │   │
│  │  port 7496 for live).                                       │   │
│  │                                                             │   │
│  │  Retrying in 8s...                    [Retry now]           │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  (All portfolio data and controls are disabled until connected)     │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---
---

# Technical Specifications & Architecture

---

## Stack Recommendation

| Layer | Technology | Why |
|---|---|---|
| **Backend** | Python + FastAPI | Reuses all your existing `ib_insync` code as-is. FastAPI is lightweight and runs a local HTTP server. |
| **Frontend** | Single HTML file + vanilla JS | No build step, no npm, no Node.js. Open the browser, it works. |
| **Charts** | Chart.js (loaded from CDN) | Simple, zero setup, good-looking bar + donut charts |
| **Data tables** | Plain HTML table + JS | Editable cells, live recalculation on input |
| **State / persistence** | JSON file on disk | Target weights saved to `app_config.json`, same pattern as your existing scripts |
| **Launch** | `python app.py` | One command. App auto-opens browser tab. |

**No Docker, no npm, no deployment. If you can run your Python scripts, you can run this app.**

---

## Architecture Diagram

```
Your laptop
┌─────────────────────────────────────────────────────────┐
│                                                         │
│   Browser (localhost:8888)                              │
│   ┌────────────────────────┐                            │
│   │  index.html            │  HTTP/JSON API             │
│   │  (JS + Chart.js)       │ ◄──────────────────────┐  │
│   └────────────────────────┘                        │  │
│                                                     │  │
│   FastAPI app (Python)                              │  │
│   ┌────────────────────────────────────────────┐   │  │
│   │  app.py  (new)                             │   │  │
│   │    ├── GET /api/portfolio   ←──────────────┘  │  │
│   │    ├── GET /api/targets                        │  │
│   │    ├── POST /api/targets    (save weights)     │  │
│   │    ├── POST /api/plan       (compute buys)     │  │
│   │    ├── POST /api/execute    (place orders)     │  │
│   │    └── GET /api/status      (TWS connection)   │  │
│   │                                                │  │
│   │  Reuses existing code:                         │  │
│   │    ├── ib_client.py   (unchanged)              │  │
│   │    ├── portfolio_manager.py  (unchanged)       │  │
│   │    └── config.py  (unchanged)                  │  │
│   └────────────────────────────────────────────────┘  │
│              │                                         │
│              │  ib_insync (socket, port 7496/7497)     │
│              ▼                                         │
│   TWS / IB Gateway (must be running)                  │
│   ┌────────────────────────┐                           │
│   │  Trader Workstation    │ ◄── Your IB account       │
│   └────────────────────────┘                           │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## File Structure (new files only)

```
IBKR-Investments/
├── claude/               ← existing, unchanged
│   ├── config.py
│   ├── ib_client.py
│   ├── portfolio_manager.py
│   └── rebalancer.py
│
├── app/                  ← new
│   ├── app.py            ← FastAPI server + launch script
│   ├── routes/
│   │   ├── portfolio.py  ← /api/portfolio, /api/status
│   │   ├── targets.py    ← /api/targets (GET + POST)
│   │   └── orders.py     ← /api/plan, /api/execute
│   ├── static/
│   │   └── index.html    ← entire frontend (HTML + JS + CSS inline)
│   └── app_config.json   ← saved target weights (auto-created)
│
└── requirements.txt      ← fastapi, uvicorn, ib_insync (already installed)
```

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/status` | TWS connection status, paper/live mode |
| `GET` | `/api/portfolio` | Fetches live positions + cash from TWS |
| `GET` | `/api/targets` | Returns saved target weights |
| `POST` | `/api/targets` | Saves updated target weights |
| `POST` | `/api/plan` | Computes rebalancing plan (no orders placed) |
| `POST` | `/api/execute` | Places buy orders via TWS |

All responses are JSON. All amounts in CHF.

---

## Key Design Decisions

### Security: TWS as the gate
The app has no authentication of its own — it doesn't need any. It can only run on your machine, and it can only do anything if TWS is already open. If TWS is closed, every API call that touches orders returns an error. This mirrors exactly how your existing scripts behave.

### Paper vs. Live: launch flag
```bash
python app.py          # paper trading (port 7497) — default
python app.py --live   # live trading (port 7496)
```
The mode is locked at launch and displayed prominently throughout the UI. You cannot switch modes mid-session without restarting the app.

### Target weights: local JSON, not hardcoded
Currently your targets are in `config.py` and you edit the file. In the app, weights are stored in `app_config.json` and editable from the UI. On first run, `app_config.json` is created from `config.py` defaults. A "Reset to defaults" button always brings you back to `config.py`.

### Frontend: no build, no Node
The entire frontend is one `index.html` file. Chart.js is loaded from a CDN on first use (can be made fully offline by downloading it once). No React, no build step. If you can open a `.html` file, you can read and understand the structure.

### Rebalancing logic: unchanged
The buy calculation logic stays in `portfolio_manager.py` exactly as it is today. The app is a UI layer on top — it doesn't rewrite the logic.

---

## Launch & Installation

### One-time setup

```bash
pip install fastapi uvicorn
cd IBKR-Investments/app
python setup.py   # creates the Desktop shortcuts
```

After setup, two icons appear on your Desktop:

| Icon | What it does |
|---|---|
| `IBKR Portfolio (Paper).command` | Starts app in paper trading mode |
| `IBKR Portfolio (Live).command` | Starts app in live trading mode |

Double-clicking either icon:
1. Opens a small Terminal window (macOS requirement — apps that run Python need a terminal)
2. Starts the FastAPI server
3. Opens your browser at `http://localhost:8888` automatically
4. When you close the Terminal window, the app stops

> **Why a terminal window?** macOS requires it for any script that isn't a signed application. The window is small and unobtrusive. A future v2 could wrap this in a proper macOS `.app` bundle to hide it entirely, but that requires significantly more setup.

### Alternative: Dock shortcut

If you want to launch from the Dock instead of the Desktop, drag the `.command` file to your Dock. Works the same way.

---

## What's Out of Scope (v1)

- Mobile / tablet layout
- Selling positions
- Automatic scheduled execution (your existing scripts handle this)
- Multi-account support
- Historical P&L charts (only current snapshot in v1)
- Price alerts
- Authentication / password protection
- Hiding the Terminal window on launch (requires a signed `.app` bundle — v2)
