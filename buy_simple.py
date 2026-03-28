#!/usr/bin/env python3
import sys, math
from ib_insync import *

HOST, PORT, CID = '127.0.0.1', 7497, 500   # 7496 live
PRICE_PAD = 0.001  # 0.5% above reference

def ref_price(t: Ticker):
    for p in (t.ask, t.midpoint(), t.last, t.close):
        if p and p > 0: return float(p)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 buy_simple.py <TICKER> <CHF_AMOUNT>")
        sys.exit(1)

    symbol = sys.argv[1]
    chf_amount = float(sys.argv[2])

    ib = IB(); ib.connect(HOST, PORT, clientId=CID)
    ib.reqMarketDataType(4)  # delayed quotes ok in Paper

    # 1) find conId from symbol
    matches = ib.reqMatchingSymbols(symbol)
    stocks = [cd.contract for cd in matches if cd.contract.secType == 'STK']
    if not stocks:
        raise RuntimeError(f"No stock contracts found for {symbol}")
    conid = stocks[0].conId  # pick the first match

    # 2) build contract from conId
    ct = Contract(conId=conid, secType='STK')
    [ct] = ib.qualifyContracts(ct)

    # 3) get price
    tkr = ib.reqMktData(ct, '', False, False)
    ib.sleep(1.0)

    px = ref_price(tkr)
    if not px:
        # Fallback: use the last daily close (usually available even w/o live data)
        bars = ib.reqHistoricalData(
          ct,
          endDateTime='',
          durationStr='2 D',
          barSizeSetting='1 day',
          whatToShow='TRADES',
          useRTH=False,
          formatDate=1
        )
        if bars:
          px = float(bars[-1].close)
        else:
          ib.disconnect()
          raise RuntimeError("No quote and no historical close available (enable delayed data in TWS).")

    # 4) size order
    qty = max(1, math.floor(chf_amount / px))
    limit_px = round(px * (1 + PRICE_PAD), 2)

    # 5) place order
    trade = ib.placeOrder(ct, LimitOrder('BUY', qty, limit_px))
    ib.sleep(1.0)

    print(f"Resolved {symbol} → conId={ct.conId}, {ct.exchange or ct.primaryExchange}, {ct.currency}")
    print(f"Placed BUY {qty} @ {limit_px} (ref {px:.4f}, pad {int(PRICE_PAD*10000)}bps) | status={trade.orderStatus.status}")

    ib.disconnect()
