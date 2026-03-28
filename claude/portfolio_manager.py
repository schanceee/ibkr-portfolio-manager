#!/usr/bin/env python3
"""Simple portfolio management logic"""

import json
from datetime import datetime
from typing import Dict, List, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
from ib_client import Position

@dataclass
class RebalanceAction:
    symbol: str
    current_weight: float
    target_weight: float
    current_value: float
    target_value: float
    required_investment: float

@dataclass
class PortfolioState:
    total_value: float
    cash_balance: float
    positions: Dict[str, float]
    last_updated: str

class PortfolioManager:
    def __init__(self, config: dict, target_allocation: dict, state_file: str, history_file: str):
        self.config = config
        self.target_allocation = target_allocation
        self.state_file = state_file
        self.state = self._load_state()

    def _load_state(self) -> PortfolioState:
        if Path(self.state_file).exists():
            try:
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                # Clean old format
                if 'accumulated_budget' in data:
                    del data['accumulated_budget']
                return PortfolioState(**data)
            except:
                pass
        
        return PortfolioState(
            total_value=0.0,
            cash_balance=0.0,
            positions={},
            last_updated=datetime.now().isoformat()
        )

    def _save_state(self):
        try:
            with open(self.state_file, 'w') as f:
                json.dump(asdict(self.state), f, indent=2)
        except:
            pass

    def update_portfolio_state(self, positions: List[Position], cash_balance: float):
        position_values = {}
        managed_value = 0
        
        # Only track target allocation positions
        for pos in positions:
            base_symbol = pos.symbol.split()[0] if ' ' in pos.symbol else pos.symbol
            if base_symbol in self.target_allocation:
                chf_value = pos.market_value  # Treat EUR as CHF for simplicity
                position_values[base_symbol] = position_values.get(base_symbol, 0) + chf_value
                managed_value += chf_value

        # Initialize missing positions
        for symbol in self.target_allocation:
            if symbol not in position_values:
                position_values[symbol] = 0.0

        self.state.positions = position_values
        self.state.cash_balance = cash_balance
        self.state.total_value = managed_value + cash_balance
        self.state.last_updated = datetime.now().isoformat()

    def calculate_rebalancing_needs(self) -> List[RebalanceAction]:
        actions = []
        invested_value = self.state.total_value - self.state.cash_balance
        
        for symbol, target_weight in self.target_allocation.items():
            current_value = self.state.positions.get(symbol, 0.0)
            current_weight = (current_value / invested_value * 100) if invested_value > 0 else 0.0
            
            target_value = self.state.total_value * (target_weight / 100)
            required_investment = max(0, target_value - current_value)
            
            action = RebalanceAction(
                symbol=symbol,
                current_weight=current_weight,
                target_weight=target_weight,
                current_value=current_value,
                target_value=target_value,
                required_investment=required_investment
            )
            actions.append(action)
        
        # Sort by largest investment needed
        actions.sort(key=lambda x: x.required_investment, reverse=True)
        return actions

    def get_rebalancing_plan(self) -> Tuple[List[RebalanceAction], float]:
        actions = self.calculate_rebalancing_needs()
        available_cash = self.state.cash_balance
        min_trade = self.config['minimum_trade_amount']
        
        plan = []
        remaining_cash = available_cash
        
        print("Rebalancing Plan:")
        
        for action in actions:
            if action.required_investment < min_trade:
                continue
                
            trade_amount = min(action.required_investment, remaining_cash)
            
            if trade_amount >= min_trade:
                action.required_investment = trade_amount
                plan.append(action)
                remaining_cash -= trade_amount
                print(f"  {action.symbol:<6} CHF {trade_amount:>6,.0f} ({action.current_weight:.1f}% → {action.target_weight:.1f}%)")
        
        if not plan:
            print("  No trades needed (all below CHF 1,000 minimum)")
            
        budget_used = available_cash - remaining_cash
        return plan, budget_used

    def execute_rebalancing_plan(self, plan: List[RebalanceAction], ib_client, dry_run: bool = False) -> bool:
        if not plan:
            return True
            
        for action in plan:
            contract = ib_client.find_contract(action.symbol)
            if contract:
                result = ib_client.place_buy_order(contract, action.required_investment, self.config['price_padding'])
                if not result:
                    print(f"Failed to place order for {action.symbol}")
                    return False
        
        if not dry_run:
            self._save_state()
        
        return True

    def get_portfolio_summary(self) -> dict:
        summary = {
            'total_value': self.state.total_value,
            'cash_balance': self.state.cash_balance,
            'invested_value': self.state.total_value - self.state.cash_balance,
            'last_updated': self.state.last_updated,
            'positions': {}
        }
        
        invested_value = self.state.total_value - self.state.cash_balance
        for symbol in self.target_allocation:
            value = self.state.positions.get(symbol, 0.0)
            weight = (value / invested_value * 100) if invested_value > 0 else 0
            target_weight = self.target_allocation[symbol]
            
            summary['positions'][symbol] = {
                'value': value,
                'current_weight': weight,
                'target_weight': target_weight,
                'deviation': weight - target_weight
            }
        
        return summary