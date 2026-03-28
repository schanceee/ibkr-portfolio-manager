#!/usr/bin/env python3
"""Simple portfolio rebalancer with live/paper trading support"""

import sys
import logging
from ib_insync import *
from config import TARGET_ALLOCATION, IB_LIVE_PORT, IB_PAPER_PORT, IB_HOST, IB_CLIENT_ID, MIN_TRADE

# Silence all logging
logging.getLogger().setLevel(logging.CRITICAL)
logging.getLogger('ib_insync').setLevel(logging.CRITICAL)

# Suppress stderr
class NullWriter:
    def write(self, txt): pass
    def flush(self): pass

original_stderr = sys.stderr

def get_ib_config(is_live=False):
    """Get IB configuration for live or paper trading"""
    port = IB_LIVE_PORT if is_live else IB_PAPER_PORT
    return {
        'host': IB_HOST,
        'port': port,
        'client_id': IB_CLIENT_ID
    }

def get_portfolio_data(is_live=False):
    """Get current positions and cash from IB"""
    sys.stderr = NullWriter()  # Silence IB output
    
    config = get_ib_config(is_live)
    ib = IB()
    try:
        ib.connect(config['host'], config['port'], clientId=config['client_id'], timeout=10)
        ib.reqMarketDataType(4)  # Delayed data
        
        positions = {}
        cash = 0
        
        # Get all portfolio items (this includes market values)
        portfolio_items = ib.portfolio()
        
        for item in portfolio_items:
            if item.position != 0:
                symbol = item.contract.symbol
                # Handle symbols with exchange suffixes
                base_symbol = symbol.split()[0] if ' ' in symbol else symbol
                
                if base_symbol in TARGET_ALLOCATION:
                    # Use the market value directly from portfolio
                    value = abs(item.marketValue)
                    if base_symbol in positions:
                        positions[base_symbol] += value
                    else:
                        positions[base_symbol] = value
        
        # Get CHF cash
        for av in ib.accountValues():
            if av.tag == 'CashBalance' and av.currency == 'CHF':
                cash = float(av.value)
                break
        
        ib.disconnect()
        return positions, cash
        
    except Exception as e:
        sys.stderr = original_stderr
        print(f"Error connecting to IB: {e}")
        return {}, 0
    finally:
        sys.stderr = original_stderr
        if ib.isConnected():
            ib.disconnect()

def calculate_rebalancing_plan(positions, cash):
    """Calculate what trades are needed"""
    total_invested = sum(positions.values())
    total_value = total_invested + cash
    
    if total_value == 0:
        return []
    
    trades = []
    
    for symbol, target_pct in TARGET_ALLOCATION.items():
        current_value = positions.get(symbol, 0)
        target_value = total_value * (target_pct / 100)
        needed = target_value - current_value
        
        if needed >= MIN_TRADE:
            current_pct = (current_value / total_invested * 100) if total_invested > 0 else 0
            trades.append({
                'symbol': symbol,
                'amount': needed,
                'current_pct': current_pct,
                'target_pct': target_pct
            })
    
    # Sort by largest investment needed
    trades.sort(key=lambda x: x['amount'], reverse=True)
    
    # Limit to available cash
    final_trades = []
    remaining_cash = cash
    
    for trade in trades:
        if trade['amount'] <= remaining_cash:
            final_trades.append(trade)
            remaining_cash -= trade['amount']
    
    return final_trades

def place_order(symbol, amount, is_live=False, dry_run=False):
    """Place a buy order for the specified amount"""
    if dry_run:
        return True
        
    sys.stderr = NullWriter()
    
    config = get_ib_config(is_live)
    ib = IB()
    try:
        ib.connect(config['host'], config['port'], clientId=config['client_id'] + 1, timeout=10)
        ib.reqMarketDataType(4)
        
        # Find contract
        matches = ib.reqMatchingSymbols(symbol)
        stocks = [cd for cd in matches if cd.contract.secType == 'STK']
        
        if not stocks:
            return False
        
        contract = stocks[0].contract
        qualified = ib.qualifyContracts(contract)
        
        if not qualified:
            return False
        
        contract = qualified[0]
        
        # Get current price
        ticker = ib.reqMktData(contract, '', False, False)
        ib.sleep(2)
        
        price = None
        for p in [ticker.ask, ticker.bid, ticker.midpoint(), ticker.last, ticker.close]:
            if p and p > 0:
                price = float(p)
                break
        
        if not price:
            # Try historical data
            bars = ib.reqHistoricalData(
                contract, '', '2 D', '1 day', 'TRADES', True, 1
            )
            if bars:
                price = float(bars[-1].close)
        
        if not price:
            return False
        
        # Calculate order
        quantity = max(1, int(amount / price))
        limit_price = round(price * 1.005, 2)  # 0.5% above market
        
        # Place order
        order = LimitOrder('BUY', quantity, limit_price)
        order.tif = 'DAY'
        order.outsideRth = False
        
        trade = ib.placeOrder(contract, order)
        ib.sleep(1)
        
        ib.disconnect()
        return True
        
    except Exception:
        return False
    finally:
        sys.stderr = original_stderr
        if ib.isConnected():
            ib.disconnect()

def show_usage():
    print("Usage: python3 rebalancer.py <command> [--live] [--dry-run]")
    print("Commands:")
    print("  status     - Show current portfolio status")
    print("  plan       - Show rebalancing plan")
    print("  rebalance  - Execute rebalancing trades")
    print("Flags:")
    print("  --live     - Use live trading (default: paper trading)")
    print("  --dry-run  - Simulate trades without executing")
    print()
    print("Examples:")
    print("  python3 rebalancer.py status              # Paper trading status")
    print("  python3 rebalancer.py status --live       # Live trading status")
    print("  python3 rebalancer.py plan --live         # Live trading plan")
    print("  python3 rebalancer.py rebalance --dry-run # Test trades on paper")
    print("  python3 rebalancer.py rebalance --live    # Execute on live account")

def main():
    if len(sys.argv) < 2:
        show_usage()
        return
    
    command = sys.argv[1].lower()
    is_live = '--live' in sys.argv
    dry_run = '--dry-run' in sys.argv
    
    if command not in ['status', 'plan', 'rebalance']:
        show_usage()
        return
    
    # Show trading mode
    mode = "LIVE TRADING" if is_live else "PAPER TRADING"
    if dry_run:
        mode += " (DRY RUN)"
    print(f"Mode: {mode}")
    print()
    
    # Get current portfolio state
    positions, cash = get_portfolio_data(is_live)
    
    # Calculate totals
    total_invested = sum(positions.values())
    
    # Show basic info
    print(f"Cash Available: CHF {cash:,.0f}")
    print(f"Portfolio Value: CHF {total_invested:,.0f}")
    print()
    
    # Show current positions if any
    if positions:
        print("Current Allocation:")
        for symbol, value in positions.items():
            current_pct = (value / total_invested * 100) if total_invested > 0 else 0
            target_pct = TARGET_ALLOCATION[symbol]
            print(f"{symbol:<6} CHF {value:>6,.0f} ({current_pct:>4.1f}% vs {target_pct:>4.1f}% target)")
        print()
    
    # Calculate and show rebalancing plan
    if command in ['plan', 'rebalance']:
        trades = calculate_rebalancing_plan(positions, cash)
        
        if trades:
            print("Rebalancing Plan:")
            for trade in trades:
                print(f"  {trade['symbol']:<6} CHF {trade['amount']:>6,.0f} "
                      f"({trade['current_pct']:.1f}% → {trade['target_pct']:.1f}%)")
            
            # Execute trades if requested
            if command == 'rebalance':
                print()
                if dry_run:
                    print("DRY RUN - would execute trades above")
                else:
                    # Safety confirmation for live trading
                    if is_live:
                        print("⚠️  WARNING: This will place REAL orders on your LIVE account!")
                        confirm = input("Type 'YES' to confirm: ")
                        if confirm != 'YES':
                            print("Aborted")
                            return
                    
                    print("Executing trades...")
                    success_count = 0
                    
                    for trade in trades:
                        if place_order(trade['symbol'], trade['amount'], is_live, dry_run):
                            success_count += 1
                        else:
                            print(f"  Failed to place order for {trade['symbol']}")
                    
                    print(f"Successfully placed {success_count}/{len(trades)} orders")
        else:
            print(f"No trades needed (all below CHF {MIN_TRADE:,} minimum)")

if __name__ == "__main__":
    main()