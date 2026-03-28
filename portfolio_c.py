#!/usr/bin/env python3
import sys
import subprocess
import json
from datetime import datetime, date
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---- Config ----
BUDGET_CHF = 3000
BUY_SCRIPT = "python3 buy_simple.py"

# Portfolio configuration
PORTFOLIO = {
    "SUSW":  (50, "monthly"),      # 50% monthly
    "XDWT":  (20, "quarterly"),    # 20% quarterly  
    "CHDVD": (10, "quarterly"),    # 10% quarterly
    "XDWH":  (10, "quarterly"),    # 10% quarterly
    "CHSPI": (5,  "bi-yearly"),    # 5% bi-yearly
    "NUKL":  (5,  "bi-yearly"),    # 5% bi-yearly
}

# Track purchase history to avoid duplicates
HISTORY_FILE = "purchase_history.json"

def load_purchase_history():
    """Load purchase history from file"""
    if Path(HISTORY_FILE).exists():
        try:
            with open(HISTORY_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Error loading history: {e}")
    return {}

def save_purchase_history(history):
    """Save purchase history to file"""
    try:
        with open(HISTORY_FILE, 'w') as f:
            json.dump(history, f, indent=2, default=str)
    except Exception as e:
        logger.error(f"Error saving history: {e}")

def months_between(start_date: datetime, target_date: datetime) -> int:
    """Calculate whole months between dates"""
    return (target_date.year - start_date.year) * 12 + (target_date.month - start_date.month)

def should_buy_multiplier(freq: str, current: datetime, start: datetime) -> int:
    """
    Determine if we should buy and return the multiplier:
    - monthly: every month (multiplier 1)
    - quarterly: every 3 months (multiplier 3) 
    - bi-yearly: every 6 months (multiplier 6)
    """
    months_elapsed = months_between(start, current)
    
    if months_elapsed < 0:
        return 0  # Before start date
    
    if freq == "monthly":
        return 1
    elif freq == "quarterly":
        return 3 if (months_elapsed % 3 == 0) else 0
    elif freq in ("bi-yearly", "bi_yearly", "biyearly", "semiannual", "semi-annual"):
        return 6 if (months_elapsed % 6 == 0) else 0
    else:
        logger.warning(f"Unknown frequency: {freq}")
        return 0

def validate_portfolio():
    """Validate portfolio configuration"""
    total_weight = sum(weight for weight, _ in PORTFOLIO.values())
    if abs(total_weight - 100) > 0.01:
        logger.warning(f"Portfolio weights sum to {total_weight}%, not 100%")
    
    for symbol, (weight, freq) in PORTFOLIO.items():
        if weight <= 0:
            raise ValueError(f"Invalid weight for {symbol}: {weight}")
        if freq not in ["monthly", "quarterly", "bi-yearly"]:
            raise ValueError(f"Invalid frequency for {symbol}: {freq}")

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 portfolio_scheduler.py <START_YYYY-MM> [TARGET_YYYY-MM] [--dry-run]")
        print("Example: python3 portfolio_scheduler.py 2024-01 2024-12 --dry-run")
        sys.exit(1)

    # Parse arguments
    start_str = sys.argv[1]
    target_str = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith('--') else datetime.today().strftime('%Y-%m')
    dry_run = '--dry-run' in sys.argv

    try:
        start = datetime.strptime(start_str, "%Y-%m")
        target = datetime.strptime(target_str, "%Y-%m")
    except ValueError as e:
        print(f"Error parsing dates: {e}")
        sys.exit(1)

    # Validate configuration
    validate_portfolio()
    
    # Load purchase history
    history = load_purchase_history()
    target_key = target.strftime('%Y-%m')
    
    print(f"{'DRY RUN: ' if dry_run else ''}Portfolio Scheduler")
    print(f"Start: {start.strftime('%Y-%m')} | Target: {target.strftime('%Y-%m')} | Budget: CHF {BUDGET_CHF:,}")
    print("-" * 60)

    orders_placed = []
    total_invested = 0

    for symbol, (weight_pct, freq) in PORTFOLIO.items():
        mult = should_buy_multiplier(freq, target, start)
        base_amount = BUDGET_CHF * (weight_pct / 100.0)
        chf_to_invest = round(base_amount * mult, 2)

        # Check if already purchased this month
        already_purchased = (
            target_key in history and 
            symbol in history[target_key]
        )

        status = ""
        if mult == 0:
            status = "not due"
        elif already_purchased:
            status = "already purchased"
        elif chf_to_invest <= 0:
            status = "zero amount"
        else:
            status = "ready to buy"

        print(f"{symbol:6s} | {freq:10s} | {weight_pct:3.0f}% | x{mult} | CHF {chf_to_invest:7.2f} | {status}")

        if mult > 0 and chf_to_invest > 0 and not already_purchased:
            if not dry_run:
                # Execute the purchase
                cmd = [*BUY_SCRIPT.split(), symbol, str(chf_to_invest)]
                logger.info(f"Executing: {' '.join(cmd)}")
                
                try:
                    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
                    logger.info(f"Order placed for {symbol}: {result.stdout.strip()}")
                    
                    # Record the purchase
                    if target_key not in history:
                        history[target_key] = {}
                    history[target_key][symbol] = {
                        'amount_chf': chf_to_invest,
                        'timestamp': datetime.now().isoformat(),
                        'frequency': freq,
                        'multiplier': mult
                    }
                    
                    orders_placed.append((symbol, chf_to_invest))
                    total_invested += chf_to_invest
                    
                except subprocess.CalledProcessError as e:
                    logger.error(f"Error placing order for {symbol}: {e}")
                    logger.error(f"stderr: {e.stderr}")
            else:
                print(f"  → Would execute: {BUY_SCRIPT} {symbol} {chf_to_invest}")
                orders_placed.append((symbol, chf_to_invest))
                total_invested += chf_to_invest

    print("-" * 60)
    print(f"Orders {'to be ' if dry_run else ''}placed: {len(orders_placed)}")
    print(f"Total {'planned ' if dry_run else ''}investment: CHF {total_invested:.2f}")
    
    if orders_placed:
        print("Summary:")
        for symbol, amount in orders_placed:
            print(f"  - {symbol}: CHF {amount:.2f}")

    # Save history (only if not dry run)
    if not dry_run and orders_placed:
        save_purchase_history(history)
        logger.info(f"Purchase history saved to {HISTORY_FILE}")

if __name__ == "__main__":
    main()
