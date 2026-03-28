from ib_insync import *

HOST, PORT, CID = '127.0.0.1', 7497, 101  # 7496 for live
ib = IB(); ib.connect(HOST, PORT, clientId=CID)

# use the lightweight positions API
ib.reqPositions()
ib.sleep(1)  # brief pause for data to arrive
positions = ib.positions()

print(f"Got {len(positions)} raw positions")
for acc, c, qty, avgCost in positions:
    print(acc, c.secType, c.localSymbol or c.symbol, c.exchange, c.currency, qty, avgCost)

ib.disconnect()
