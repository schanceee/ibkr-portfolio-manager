# Portfolio Rebalancer

Automatically rebalance your ETF portfolio using Interactive Brokers API. Only makes trades ≥ CHF 1,000 to minimize fees.

## Files

- `config.py` - Portfolio allocation and settings
- `rebalancer.py` - Main script
- `README.md` - This file

## Setup

1. **Install dependencies:**
   ```bash
   pip install ib_insync
   ```

2. **Configure Interactive Brokers:**
   - **Paper Trading:** TWS/Gateway on port 7497
   - **Live Trading:** TWS/Gateway on port 7496
   - Enable API in Global Configuration → API → Settings
   - Add `127.0.0.1` to trusted IPs

3. **Edit portfolio allocation in `config.py`:**
   ```python
   TARGET_ALLOCATION = {
       "SUSW": 50.0,   # 50%
       "XDWT": 20.0,   # 20%
       "CHDVD": 10.0,  # 10%
       "XDWH": 10.0,   # 10%
       "CHSPI": 5.0,   # 5%
       "NUKL": 5.0,    # 5%
   }
   ```

## Usage

### Basic Commands

```bash
# Check portfolio status
python3 rebalancer.py status

# See rebalancing plan
python3 rebalancer.py plan

# Execute trades (with confirmation)
python3 rebalancer.py rebalance
```

### Trading Modes

**Paper Trading (default):**
```bash
python3 rebalancer.py status                  # Paper account
python3 rebalancer.py plan                    # Paper plan
python3 rebalancer.py rebalance --dry-run     # Test run
```

**Live Trading:**
```bash
python3 rebalancer.py status --live           # Live account
python3 rebalancer.py plan --live             # Live plan  
python3 rebalancer.py rebalance --live --dry-run  # Safe test
python3 rebalancer.py rebalance --live        # Real trades ⚠️
```

### Safety Features

- `--dry-run` - Shows what would happen without executing
- `--live` - Requires typing "YES" to confirm real trades
- CHF 1,000 minimum trade size (configurable in `config.py`)
- Clear mode indication (PAPER/LIVE TRADING)

## How It Works

1. **Detects cash:** Automatically finds your CHF cash balance
2. **Reads positions:** Gets current holdings in your target allocation
3. **Calculates weights:** Shows current % vs target % for each position
4. **Plans trades:** Only suggests trades ≥ CHF 1,000 to minimize fees
5. **Executes orders:** Places limit orders 0.5% above market price

## Example Output

```
Mode: PAPER TRADING

Cash Available: CHF 12,169
Portfolio Value: CHF 15,194

Current Allocation:
SUSW   CHF  6,472 (42.6% vs 50.0% target)
XDWT   CHF  3,401 (22.4% vs 20.0% target)
XDWH   CHF  2,655 (17.5% vs 10.0% target)
NUKL   CHF  2,661 (17.5% vs  5.0% target)

Rebalancing Plan:
  CHDVD  CHF  2,736 (0.0% → 10.0%)
  SUSW   CHF  1,131 (42.6% → 50.0%)
```

## Monthly Workflow

1. **Transfer money** to your IB account
2. **Check status:** `python3 rebalancer.py status --live`
3. **Review plan:** `python3 rebalancer.py plan --live`
4. **Test safely:** `python3 rebalancer.py rebalance --live --dry-run`
5. **Execute:** `python3 rebalancer.py rebalance --live`

## Configuration

### Portfolio Allocation
Edit percentages in `config.py`. Must sum to 100%.

### Trade Settings
```python
MIN_TRADE = 1000  # Minimum CHF per trade
```

### IB Connection
```python
IB_LIVE_PORT = 7496      # Live trading
IB_PAPER_PORT = 7497     # Paper trading
```

## Troubleshooting

**"Failed to connect to IB"**
- Check TWS/Gateway is running
- Verify API is enabled
- Confirm correct port (7496 live, 7497 paper)

**"No market data permissions"**
- Normal - script uses portfolio values directly
- Enable delayed data in TWS for better price discovery

**"No trades needed"**
- All required investments are below CHF 1,000 minimum
- Consider transferring more money or lowering `MIN_TRADE`

## Safety Notes

- Always test with `--dry-run` first
- Paper trading is the default (safer)
- Live trading requires explicit `--live` flag and confirmation
- Script only makes BUY orders (no selling)
- Orders are DAY orders with 0.5% price padding

## File Structure

```
portfolio-rebalancer/
├── config.py           # Settings and allocation
├── rebalancer.py       # Main script
├── README.md          # This file
├── portfolio_state.json     # Auto-created state file
└── rebalancing_history.json # Auto-created history
```