# IBKR Portfolio Manager

A local web app that connects to your running Trader Workstation (TWS) and gives you a visual interface to monitor your portfolio, edit target allocations, and execute rebalancing buys — all from your browser.

---

## Prerequisites

1. **Python 3.10+** — check with `python3 --version`
2. **IBKR Trader Workstation (TWS)** — must be open before you launch the app
3. **TWS API enabled** — in TWS: *Edit → Global Configuration → API → Settings*
   - Check "Enable ActiveX and Socket Clients"
   - Add `127.0.0.1` to trusted IP addresses
   - Paper trading port: **7497** · Live trading port: **7496**

---

## One-time setup

Open a terminal, run:

```bash
cd /Users/edouardgence/IBKR-Investments/app
python3 setup.py
```

This installs the required Python packages and creates two shortcuts on your Desktop:

| Shortcut | What it does |
|---|---|
| `IBKR Portfolio (Paper).command` | Connects to paper trading account |
| `IBKR Portfolio (Live).command`  | Connects to real money account 🔴 |

---

## Daily use

1. Open TWS (paper or live account)
2. Double-click the Desktop shortcut
3. A small Terminal window opens, then your browser opens at `http://localhost:8888`
4. When you're done, close the Terminal window

---

## What the app does

### Portfolio tab
- Live positions fetched directly from TWS
- Edit target weights inline — click any "Target %" cell, type a new number, press Tab
- Delta column shows how far each position is from its target (colour-coded)
- P&L column shows unrealised gain/loss vs. your average buy price
  - 🟢 fine · 🟡 -5% to -10% · 🔴 below -10% (row highlighted red)
- Bar chart: current vs. target allocation, updates as you edit
- "Reset targets" restores the original weights from `claude/config.py`

### Rebalancing tab
- Computed buy plan based on your current positions and target weights
- Adjust the minimum trade size (default CHF 500)
- Toggle individual positions in/out of the plan
- **Run Dry-Run** — simulates orders, nothing sent to TWS
- **Execute Buys** — opens a confirmation screen, then places limit orders

---

## Editing target weights permanently

Your edited weights are saved automatically to `app/app_config.json`. They persist across restarts. To reset to the original defaults, click **Reset targets** in the app or delete `app_config.json`.

To change the P&L alert threshold (default -10%), edit `app/app_config.json`:
```json
{
  "pnl_alert_threshold": -10,
  ...
}
```

---

## Running tests

```bash
cd /Users/edouardgence/IBKR-Investments
pip install pytest
pytest app/tests/test_logic.py -v
```

No TWS connection needed for the unit tests.

---

## Troubleshooting

**"Cannot connect to TWS"**
- Make sure TWS is open and fully loaded (not just the login screen)
- Check the API is enabled: *Edit → Global Configuration → API → Settings*
- Make sure the port matches (7497 for paper, 7496 for live)
- Try clicking "Retry now" in the app

**Browser doesn't open automatically**
- Manually navigate to `http://localhost:8888`

**"ModuleNotFoundError: No module named 'fastapi'"**
- Run: `pip3 install fastapi uvicorn`

**Port 8888 already in use**
- Launch from terminal with a different port: `python3 app.py --port 8889`

**macOS: "cannot be opened because it is from an unidentified developer"**
- Right-click the `.command` file → Open → Open anyway
- You only need to do this once

---

## File structure

```
IBKR-Investments/
├── claude/                  ← original scripts (unchanged)
│   ├── config.py            ← default target allocation lives here
│   ├── ib_client.py
│   ├── portfolio_manager.py
│   └── rebalancer.py
│
├── app/                     ← web app
│   ├── app.py               ← main server (run this)
│   ├── setup.py             ← creates Desktop shortcuts
│   ├── app_config.json      ← your saved weights (auto-created)
│   ├── routes/
│   │   ├── portfolio.py     ← /api/portfolio, /api/status
│   │   ├── targets.py       ← /api/targets
│   │   └── orders.py        ← /api/plan, /api/execute
│   ├── static/
│   │   └── index.html       ← entire frontend
│   └── tests/
│       └── test_logic.py    ← unit tests
│
└── README.md

---

## Legacy scripts (still work independently)

```bash
python3 portfolio.py 2025-08 2025-08   # periodic buy scheduler
python3 buy_simple.py TSLA 1000        # buy CHF 1000 of a single stock
```
