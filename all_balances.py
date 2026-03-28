from ib_insync import *

ib = IB()
ib.connect('127.0.0.1', 7497, clientId=111)  # 7496 if live

# 1) Cash by currency
summary = ib.accountSummary()
#print(summary)
print("\n-- Cash by currency --")
for row in summary:
    # print(row)
    #print("\n")
    if row.tag == 'CashBalance':
        print(f"{row.currency:>5}: {row.value}")

# 2) All positions
ib.reqPositions()
ib.sleep(1)  # short pause to receive positions
positions = ib.positions()

print("\n-- Positions --")
for account, contract, qty, avgCost in positions:
    sym = contract.localSymbol or contract.symbol
    print(f"{sym:<12} {contract.currency:<4} {qty}")
    
ib.disconnect()
