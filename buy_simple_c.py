#!/usr/bin/env python3
# buy_simple.py - Fixed version
import sys, math, time
from ib_insync import *
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

HOST, PORT, CID = '127.0.0.1', 7497, 500   # 7496 for live trading
PRICE_PAD = 0.005  # 0.5% above reference price
MAX_RETRIES = 3
SLEEP_TIME = 2.0

def ref_price(t: Ticker):
    """Get reference price from ticker data"""
    for p in (t.ask, t.bid, t.midpoint(), t.last, t.close):
        if p and p > 0: 
            return float(p)
    return None

def get_historical_price(ib, contract):
    """Fallback to get historical price if no live data"""
    try:
        bars = ib.reqHistoricalData(
            contract,
            endDateTime='',
            durationStr='5 D',  # Look back further
            barSizeSetting='1 day',
            whatToShow='TRADES',
            useRTH=True,
            formatDate=1
        )
        if bars and len(bars) > 0:
            return float(bars[-1].close)
    except Exception as e:
        logger.error(f"Error getting historical data: {e}")
    return None

def find_best_contract(ib, symbol):
    """Find the best contract match for a symbol"""
    try:
        matches = ib.reqMatchingSymbols(symbol)
        if not matches:
            raise RuntimeError(f"No matches found for symbol {symbol}")
        
        # Filter for stocks and sort by relevance
        stocks = [cd for cd in matches if cd.contract.secType == 'STK']
        if not stocks:
            raise RuntimeError(f"No stock contracts found for {symbol}")
        
        # Prefer primary exchanges and major currencies
        def contract_priority(cd):
            c = cd.contract
            score = 0
            if c.primaryExchange in ['XETRA', 'SWX', 'NYSE', 'NASDAQ']:
                score += 10
            if c.currency in ['CHF', 'EUR', 'USD']:
                score += 5
            if c.exchange == c.primaryExchange:
                score += 3
            return score
        
        best_match = max(stocks, key=contract_priority)
        return best_match.contract
    except Exception as e:
        logger.error(f"Error finding contract for {symbol}: {e}")
        raise

def main():
    if len(sys.argv) < 3:
        print("Usage: python3 buy_simple.py <TICKER> <CHF_AMOUNT> [--dry-run]")
        sys.exit(1)

    symbol = sys.argv[1].upper()
    chf_amount = float(sys.argv[2])
    dry_run = '--dry-run' in sys.argv

    if chf_amount <= 0:
        raise ValueError("CHF amount must be positive")

    logger.info(f"{'DRY RUN: ' if dry_run else ''}Buying {symbol} for CHF {chf_amount}")

    ib = IB()
    
    try:
        # Connect with retry logic
        connected = False
        for attempt in range(MAX_RETRIES):
            try:
                ib.connect(HOST, PORT, clientId=CID + attempt)
                connected = True
                break
            except Exception as e:
                logger.warning(f"Connection attempt {attempt + 1} failed: {e}")
                time.sleep(1)
        
        if not connected:
            raise RuntimeError(f"Failed to connect after {MAX_RETRIES} attempts")

        ib.reqMarketDataType(4)  # delayed data for paper trading
        
        # Find and qualify contract
        contract = find_best_contract(ib, symbol)
        qualified_contracts = ib.qualifyContracts(contract)
        
        if not qualified_contracts:
            raise RuntimeError(f"Could not qualify contract for {symbol}")
        
        ct = qualified_contracts[0]
        logger.info(f"Qualified contract: {ct.symbol} ({ct.conId}) on {ct.exchange or ct.primaryExchange}")

        # Get market data
        ticker = ib.reqMktData(ct, '', False, False)
        ib.sleep(SLEEP_TIME)

        # Get reference price
        px = ref_price(ticker)
        
        if not px:
            logger.warning("No live price data, trying historical data...")
            px = get_historical_price(ib, ct)
            
        if not px:
            raise RuntimeError(f"No price data available for {symbol}")

        logger.info(f"Reference price: {px:.4f} {ct.currency}")

        # Calculate order details
        qty = max(1, math.floor(chf_amount / px))
        limit_px = round(px * (1 + PRICE_PAD), 2)
        estimated_cost = qty * limit_px

        logger.info(f"Order details: BUY {qty} @ {limit_px} (estimated cost: {estimated_cost:.2f} {ct.currency})")

        if not dry_run:
            # Place order
            order = LimitOrder('BUY', qty, limit_px)
            order.tif = 'DAY'  # Good for day
            order.outsideRth = False  # Only during regular trading hours
            
            trade = ib.placeOrder(ct, order)
            ib.sleep(1.0)

            print(f"SUCCESS: Placed BUY {qty} {symbol} @ {limit_px} | Order ID: {trade.order.orderId} | Status: {trade.orderStatus.status}")
        else:
            print(f"DRY RUN: Would place BUY {qty} {symbol} @ {limit_px}")

    except Exception as e:
        logger.error(f"Error: {e}")
        raise
    finally:
        if ib.isConnected():
            ib.disconnect()

if __name__ == "__main__":
    main()

