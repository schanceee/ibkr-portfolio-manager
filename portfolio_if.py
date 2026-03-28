#!/usr/bin/env python3
import sys
import subprocess
from datetime import datetime

# ---- Config ----
BUDGET_CHF = 3000
BUY_SCRIPT = "python3 buy_simple.py"  # your existing buyer

# symbol: (weight_percent, frequency)
PORTFOLIO = {
    "SUSW":  (50, "monthly"),
    "XDWT":  (20, "quarterly"),
    "CHDVD": (10, "quarterly"),
    "XDWH":  (10, "quarterly"),
    "CHSPI": (5,  "bi-yearly"),
    "NUKL":  (5,  "bi-yearly"),
}

def months_between(a: datetime, b: datetime) -> int:
    return (b.year - a.year) * 12 + (b.month - a.month)

def should_buy_multiplier(freq: str, current: datetime, start: datetime) -> int:
    m = months_between(start, current)
    if m < 0: return 0
    if freq == "monthly":   return 1
    if freq == "quarterly": return 3 if (m % 3 == 0) else 0
    if freq in ("bi-yearly", "bi_yearly", "biyearly", "semiannual", "semi-annual"):
        return 6 if (m % 6 == 0) else 0
    return 0

def main():
    # Usage:
    #   python3 portfolio.py <START_YYYY-MM> [TARGET_YYYY-MM] [--whatif]
    if len(sys.argv) < 2:
        print("Usage: python3 portfolio.py <START_YYYY-MM> [TARGET_YYYY-MM] [--whatif]")
        sys.exit(1)

    start = datetime.strptime(sys.argv[1], "%Y-%m")
    # second arg may be target or the --whatif flag
    whatif = False
    if len(sys.argv) >= 3 and sys.argv[2].startswith("--"):
        target = datetime.today()
        whatif = (sys.argv[2] == "--whatif")
    else:
        target = datetime.today() if len(sys.argv) < 3 else datetime.strptime(sys.argv[2], "%Y-%m")
        if len(sys.argv) >= 4:
            whatif = (sys.argv[3] == "--whatif")

    print(f"Start={start.strftime('%Y-%m')} | Target month={target.strftime('%Y-%m')} "
          f"| Budget CHF {BUDGET_CHF} | WhatIf={whatif}")

    for symbol, (weight_pct, freq) in PORTFOLIO.items():
        mult = should_buy_multiplier(freq, target, start)
        base_amount = BUDGET_CHF * (weight_pct / 100.0)
        chf_to_invest = int(round(base_amount * mult))

        if mult == 0 or chf_to_invest <= 0:
            print(f"Skip {symbol:5s} [{freq:9s}] — not due this month.")
            continue

        print(f"{'Sim' if whatif else 'Buy '}  {symbol:5s} [{freq:9s}] x{mult} → CHF {chf_to_invest} "
              f"(base {base_amount:.2f} × {mult})")

        cmd = [*BUY_SCRIPT.split(), symbol, str(chf_to_invest)]
        if whatif:
            cmd.append("--whatif")

        print(f"Running command: {' '.join(cmd)}")
        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            print(f"  ERROR placing order for {symbol}: {e}")

if __name__ == "__main__":
    main()
