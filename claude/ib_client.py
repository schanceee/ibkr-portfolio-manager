#!/usr/bin/env python3
"""Interactive Brokers client wrapper with enhanced error handling"""

import logging
import time
import math
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from ib_insync import *

logger = logging.getLogger(__name__)

@dataclass
class Position:
    symbol: str
    quantity: float
    market_price: float
    market_value: float
    currency: str
    contract: Contract

@dataclass
class TradeResult:
    symbol: str
    action: str
    quantity: int
    price: float
    estimated_value: float
    order_id: int
    status: str

class IBClient:
    def __init__(self, host: str, port: int, client_id: int, timeout: int = 30):
        self.host = host
        self.port = port
        self.client_id = client_id
        self.timeout = timeout
        self.ib = IB()
        self.connected = False

    def connect(self, retries: int = 3) -> bool:
        """Connect to IB with retry logic"""
        for attempt in range(retries):
            try:
                if self.connected:
                    self.disconnect()
                
                self.ib.connect(self.host, self.port, clientId=self.client_id + attempt, timeout=self.timeout)
                self.ib.reqMarketDataType(4)  # Delayed data
                self.connected = True
                logger.info(f"Connected to IB on attempt {attempt + 1}")
                return True
                
            except Exception as e:
                logger.warning(f"Connection attempt {attempt + 1} failed: {e}")
                time.sleep(2)
        
        logger.error(f"Failed to connect after {retries} attempts")
        return False

    def disconnect(self):
        """Safely disconnect from IB"""
        if self.connected and self.ib.isConnected():
            self.ib.disconnect()
            self.connected = False
            logger.info("Disconnected from IB")

    def get_portfolio_positions(self) -> List[Position]:
        """Get current portfolio positions"""
        if not self.connected:
            raise RuntimeError("Not connected to IB")
        
        positions = []
        ib_positions = self.ib.positions()
        
        for pos in ib_positions:
            if pos.position != 0:  # Only active positions
                # Get current market data
                ticker = self.ib.reqMktData(pos.contract, '', False, False)
                self.ib.sleep(1)
                
                market_price = self._get_market_price(ticker, pos.contract)
                if market_price:
                    market_value = abs(pos.position) * market_price
                    
                    position = Position(
                        symbol=pos.contract.symbol,
                        quantity=pos.position,
                        market_price=market_price,
                        market_value=market_value,
                        currency=pos.contract.currency,
                        contract=pos.contract
                    )
                    positions.append(position)
                    
        logger.info(f"Retrieved {len(positions)} positions")
        return positions

    def get_account_cash(self) -> float:
        """Get available CHF cash in account"""
        if not self.connected:
            raise RuntimeError("Not connected to IB")
            
        account_values = self.ib.accountValues()
        chf_cash = 0.0
        
        # Look for CHF cash balances
        for av in account_values:
            if av.tag == 'CashBalance' and av.currency == 'CHF':
                chf_cash = float(av.value)
                break
        
        # If no CashBalance found, try other tags
        if chf_cash == 0:
            for av in account_values:
                if av.tag in ['TotalCashValue', 'AvailableFunds'] and av.currency == 'CHF':
                    chf_cash = float(av.value)
                    break
                
        return chf_cash

    def find_contract(self, symbol: str) -> Optional[Contract]:
        """Find and qualify contract for symbol"""
        try:
            matches = self.ib.reqMatchingSymbols(symbol)
            if not matches:
                return None
            
            # Filter for stocks and find best match
            stocks = [cd for cd in matches if cd.contract.secType == 'STK']
            if not stocks:
                return None
            
            # Prefer major exchanges and CHF/EUR currencies
            def priority_score(cd):
                c = cd.contract
                score = 0
                if c.primaryExchange in ['XETRA', 'SWX', 'NYSE', 'NASDAQ']:
                    score += 10
                if c.currency in ['CHF', 'EUR', 'USD']:
                    score += 5
                return score
            
            best_match = max(stocks, key=priority_score)
            contract = best_match.contract
            
            # Qualify the contract
            qualified = self.ib.qualifyContracts(contract)
            return qualified[0] if qualified else None
            
        except Exception as e:
            logger.error(f"Error finding contract for {symbol}: {e}")
            return None

    def _get_market_price(self, ticker: Ticker, contract: Contract) -> Optional[float]:
        """Get market price from ticker or historical data"""
        # Try live data first
        for price in [ticker.ask, ticker.bid, ticker.midpoint(), ticker.last, ticker.close]:
            if price and price > 0:
                return float(price)
        
        # Fallback to historical data
        try:
            bars = self.ib.reqHistoricalData(
                contract,
                endDateTime='',
                durationStr='5 D',
                barSizeSetting='1 day',
                whatToShow='TRADES',
                useRTH=True,
                formatDate=1
            )
            if bars:
                return float(bars[-1].close)
        except Exception as e:
            logger.warning(f"Could not get historical price for {contract.symbol}: {e}")
        
        return None

    def place_buy_order(self, contract: Contract, chf_amount: float, price_padding: float = 0.005) -> Optional[TradeResult]:
        """Place a buy order for specified CHF amount"""
        try:
            # Get current price
            ticker = self.ib.reqMktData(contract, '', False, False)
            self.ib.sleep(2)
            
            market_price = self._get_market_price(ticker, contract)
            if not market_price:
                logger.error(f"No market price available for {contract.symbol}")
                return None
            
            # Calculate order parameters
            quantity = max(1, math.floor(chf_amount / market_price))
            limit_price = round(market_price * (1 + price_padding), 2)
            estimated_value = quantity * limit_price
            
            # Create and place order
            order = LimitOrder('BUY', quantity, limit_price)
            order.tif = 'DAY'
            order.outsideRth = False
            
            trade = self.ib.placeOrder(contract, order)
            self.ib.sleep(1)
            
            result = TradeResult(
                symbol=contract.symbol,
                action='BUY',
                quantity=quantity,
                price=limit_price,
                estimated_value=estimated_value,
                order_id=trade.order.orderId,
                status=trade.orderStatus.status
            )
            
            logger.info(f"Placed order: BUY {quantity} {contract.symbol} @ {limit_price}")
            return result
            
        except Exception as e:
            logger.error(f"Error placing buy order for {contract.symbol}: {e}")
            return None