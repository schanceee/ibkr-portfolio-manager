#!/usr/bin/env python3
# portfolio_scheduler.py
import sys
import subprocess
from datetime import datetime

# ---- Config ----
BUDGET_CHF = 3000                 # your monthly budget
BUY_SCRIPT = "python3 buy_simple.py"  # path/command to your working buyer

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
    """Whole months from a -> b (b >= a)."""
    return (b.year - a.year) * 12 + (b.month - a.month)

def should_buy_multiplier(freq: str, current: datetime, start: datetime) -> int:
    """
    Return 0 if not due; otherwise the multiplier to apply:
      monthly -> 1
      quarterly months -> 3
      bi-yearly months -> 6
    """
    m = months_between(start, current)
    if m < 0:
        return 0  # before start window
    if freq == "monthly":
        return 1
    if freq == "quarterly":
        return 3 if (m % 3 == 0) else 0
    if freq in ("bi-yearly", "bi_yearly", "biyearly", "semiannual", "semi-annual"):
        return 6 if (m % 6 == 0) else 0
    return 0

def main():
    # Usage: python3 portfolio_scheduler.py <START_YYYY-MM> [TARGET_YYYY-MM]
    if len(sys.argv) < 2:
        print("Usage: python3 portfolio_scheduler.py <START_YYYY-MM> [TARGET_YYYY-MM]")
        sys.exit(1)

    start = datetime.strptime(sys.argv[1], "%Y-%m")
    target = datetime.today() if len(sys.argv) < 3 else datetime.strptime(sys.argv[2], "%Y-%m")

    print(f"Start={start.strftime('%Y-%m')} | Target month={target.strftime('%Y-%m')} | Budget CHF {BUDGET_CHF}")

    for symbol, (weight_pct, freq) in PORTFOLIO.items():
        mult = should_buy_multiplier(freq, target, start)
        base_amount = BUDGET_CHF * (weight_pct / 100.0)
        chf_to_invest = int(round(base_amount * mult))

        if mult == 0 or chf_to_invest <= 0:
            print(f"Skip {symbol:5s} [{freq:9s}] — not due this month.")
            continue

        print(f"Buy  {symbol:5s} [{freq:9s}] x{mult} → CHF {chf_to_invest:.2f} "
              f"(base {base_amount:.2f} × {mult})")

        # Call your existing buyer: python3 buy_simple.py <TICKER> <CHF_AMOUNT>
        cmd = [*BUY_SCRIPT.split(), symbol, str(chf_to_invest)]
        print(f"Running command: {' '.join(cmd)}")
        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            print(f"  ERROR placing order for {symbol}: {e}")

if __name__ == "__main__":
    main()
