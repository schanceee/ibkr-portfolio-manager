#!/usr/bin/env python3
import sys, math
from datetime import datetime
from ib_insync import *

# ---------- CONFIG ----------
BUDGET_CHF = 3000

# Symbol -> (weight_pct, frequency)
PORTFOLIO = {
    "SUSW":  (50, "monthly"),
    "XDWT":  (20, "monthly"),
    "CHDVD": (10, "quarterly"),
    "XDWH":  (10, "quarterly"),
    "CHSPI": (5,  "bi-yearly"),
    "NUKL":  (5,  "bi-yearly"),
}

# Avoid symbol lookups: use contract IDs you resolved once
CONID = {
    "SUSW": 292495500,   # LSEETF EUR
    "XDWH": 227263992,   # Xetra EUR
    "CHDVD":150029466,   # SIX CHF
    "CHSPI":150029461,   # SIX CHF
    "NUKL": 613031265,   # Euronext Paris (or your venue)
    # "XDWT": <ADD YOUR CONID HERE>  # Xetra EUR – look up once
}

PRICE_PAD = 0.001  # +0.10% aggressive limit so it fills but still capped
HOST, PORT, CID = '127.0.0.1', 7497, 900  # 7496 live

# ---------- HELPERS ----------
def months_between(a: datetime, b: datetime) -> int:
    return (b.year - a.year) * 12 + (b.month - a.month)

def due_multiplier(freq: str, current: datetime, start: datetime) -> int:
    m = months_between(start, current)
    if m < 0: return 0
    if freq == "monthly":   return 1
    if freq == "quarterly": return 3 if m % 3 == 0 else 0
    if freq in ("bi-yearly","semiannual","semi-annual"):
        return 6 if m % 6 == 0 else 0
    return 0

def ref_price_from_ticker(t: Ticker):
    for p in (t.ask, t.midpoint(), t.last, t.close):
        if p and p > 0: return float(p)

# ---------- MAIN ----------
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 portfolio_scheduler_batch.py <START_YYYY-MM> [TARGET_YYYY-MM]")
        sys.exit(1)
    start = datetime.strptime(sys.argv[1], "%Y-%m")
    target = datetime.today() if len(sys.argv) < 3 else datetime.strptime(sys.argv[2], "%Y-%m")

    print(f"Start={start.strftime('%Y-%m')} | Target={target.strftime('%Y-%m')} | Budget CHF {BUDGET_CHF}")

    ib = IB()
    ib.connect(HOST, PORT, clientId=CID)
    ib.reqMarketDataType(4)  # allow delayed data in Paper

    for sym, (w, freq) in PORTFOLIO.items():
        mult = due_multiplier(freq, target, start)
        base_amt = BUDGET_CHF * (w/100.0)
        chf_amt = int(round(base_amt * mult))  # whole CHF

        if mult == 0 or chf_amt <= 0:
            print(f"Skip {sym:5s} [{freq:9s}] — not due.")
            continue
        if sym not in CONID:
            print(f"Skip {sym}: missing conId (add it to CONID dict).")
            continue

        # Build contract from conId (robust, no lookup/rate-limit)
        ct = Contract(conId=CONID[sym], secType='STK')
        q = ib.qualifyContracts(ct)
        if not q:
            print(f"  ERROR: unknown contract for {sym} (conId {CONID[sym]}).")
            continue
        ct = q[0]

        # Get a price (delayed ok). If none, use last daily close.
        t = ib.reqMktData(ct, '', False, False); ib.sleep(1.0)
        px = ref_price_from_ticker(t)

        if not px:
            bars = ib.reqHistoricalData(
                ct, endDateTime='', durationStr='2 D', barSizeSetting='1 day',
                whatToShow='TRADES', useRTH=False, formatDate=1
            )
            if bars:
                px = float(bars[-1].close)
        if not px:
            print(f"  ERROR: No price for {sym}; check delayed data/permissions.")
            continue

        qty = max(1, math.floor(chf_amt / px))
        lmt = round(px * (1 + PRICE_PAD), 2)

        order = LimitOrder('BUY', qty, lmt)
        trade = ib.placeOrder(ct, order)
        ib.sleep(1.0)

        print(f"Buy {sym:5s} [{freq:9s}] x{mult} → CHF {chf_amt:>5} | "
              f"{ct.currency} {qty} @ {lmt} (ref {px:.4f}) | status={trade.orderStatus.status}")

        # brief pause to avoid pacing/overlap
        ib.sleep(0.8)

    ib.disconnect()
