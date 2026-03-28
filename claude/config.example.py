# config.example.py
# Copy this file to config.py and adjust to your own allocation before running.

TARGET_ALLOCATION = {
    "ACWI": 40.0,   # 40% — Global equities ETF (example)
    "AGG":  20.0,   # 20% — US bonds ETF (example)
    "VNQ":  15.0,   # 15% — Real estate ETF (example)
    "GLD":  15.0,   # 15% — Gold ETF (example)
    "CASH": 10.0,   # 10% — Cash / money market (example)
}

# IB connection settings (defaults work for most setups)
IB_LIVE_PORT  = 7496      # TWS live trading port
IB_PAPER_PORT = 7497      # TWS paper trading port
IB_HOST       = '127.0.0.1'
IB_CLIENT_ID  = 500

MIN_TRADE = 500  # Minimum order size in CHF
