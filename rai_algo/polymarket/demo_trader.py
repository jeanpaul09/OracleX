"""Demo Trading System - Virtual capital trading"""

import asyncio
from typing import List, Optional, Dict
from datetime import datetime
from decimal import Decimal
import structlog

from .models import (
    Order, OrderSide, OrderType, Position, PositionSide, Trade,
    Opportunity, StrategyBlueprint
)
from .client import PolymarketClient
from .config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


class DemoTrader:
    """Demo/paper trading system with virtual capital"""
    
    def __init__(self, client: PolymarketClient):
        self.client = client
        self.capital = Decimal(str(settings.initial_capital))
        self.initial_capital = Decimal(str(settings.initial_capital))
        self.positions: Dict[str, Position] = {}
        self.orders: Dict[str, Order] = {}
        self.trade_history: List[Trade] = []
        self.closed_positions: List[Position] = []
    
    def get_balance(self) -> Decimal:
        """Get current balance"""
        return self.capital
    
    def get_equity(self) -> Decimal:
        """Get total equity (capital + unrealized PnL)"""
        unrealized_pnl = sum(
            pos.unrealized_pnl for pos in self.positions.values()
        )
        return self.capital + unrealized_pnl
    
    def get_realized_pnl(self) -> Decimal:
        """Get total realized PnL"""
        return sum(trade.pnl for trade in self.trade_history)
    
    def get_unrealized_pnl(self) -> Decimal:
        """Get total unrealized PnL"""
        return sum(pos.unrealized_pnl for pos in self.positions.values())
    
    def get_total_pnl(self) -> Decimal:
        """Get total PnL (realized + unrealized)"""
        return self.get_realized_pnl() + self.get_unrealized_pnl()
    
    def get_roi(self) -> float:
        """Get return on investment percentage"""
        if self.initial_capital == 0:
            return 0.0
        return float((self.get_equity() - self.initial_capital) / self.initial_capital * 100)
    
    async def place_order(
        self,
        opportunity: Opportunity,
        position_size_pct: float = 0.1,
        strategy_id: Optional[str] = None,
        strategy_name: Optional[str] = None
    ) -> Optional[Order]:
        """Place order based on opportunity"""
        # Calculate position size
        equity = self.get_equity()
        position_value = equity * Decimal(str(position_size_pct))
        
        # Calculate number of shares
        size = position_value / opportunity.entry_price
        
        # Check if we have enough capital
        if position_value > self.capital:
            logger.warning(f"Insufficient capital: need {position_value}, have {self.capital}")
            return None
        
        # Create order
        order = Order(
            id=f"order_{datetime.utcnow().timestamp()}",
            market_id=opportunity.market_id,
            side=opportunity.side,
            order_type=OrderType.LIMIT,
            price=opportunity.entry_price,
            size=size,
        )
        
        # Execute order (demo mode - instant fill)
        await self._execute_order(order, opportunity, strategy_id, strategy_name)
        
        return order
    
    async def _execute_order(
        self,
        order: Order,
        opportunity: Opportunity,
        strategy_id: Optional[str] = None,
        strategy_name: Optional[str] = None
    ) -> None:
        """Execute order (demo mode - instant fill)"""
        order.status = "filled"
        order.filled_size = order.size
        order.filled_at = datetime.utcnow()
        
        # Deduct capital
        cost = order.price * order.size
        self.capital -= cost
        
        # Create or update position
        position_id = f"{order.market_id}_{order.side.value}"
        
        if position_id in self.positions:
            # Update existing position
            position = self.positions[position_id]
            # Average entry price
            total_cost = (position.entry_price * position.size) + cost
            total_size = position.size + order.size
            position.entry_price = total_cost / total_size
            position.size = total_size
        else:
            # Create new position
            position = Position(
                id=position_id,
                market_id=order.market_id,
                side=PositionSide.LONG if order.side == OrderSide.YES else PositionSide.SHORT,
                size=order.size,
                entry_price=order.price,
                current_price=order.price,
                strategy_id=strategy_id,
                strategy_name=strategy_name,
                stop_loss=opportunity.stop_loss,
                take_profit=opportunity.target_price,
            )
            self.positions[position_id] = position
        
        # Update PnL
        position.update_pnl(order.price)
        
        # Record trade
        trade = Trade(
            id=f"trade_{datetime.utcnow().timestamp()}",
            market_id=order.market_id,
            side=order.side,
            price=order.price,
            size=order.size,
            strategy_id=strategy_id,
        )
        self.trade_history.append(trade)
        
        logger.info(
            f"Order executed: {order.side.value} {order.size} @ {order.price} "
            f"(Capital: {self.capital:.2f})"
        )
    
    async def update_positions(self) -> None:
        """Update all positions with current market prices"""
        for position_id, position in list(self.positions.items()):
            try:
                # Get current market price
                orderbook = await self.client.get_orderbook(position.market_id)
                if not orderbook:
                    continue
                
                # Get current price based on side
                if position.side == PositionSide.LONG:
                    current_price = orderbook.get_best_yes_price()
                else:
                    current_price = orderbook.get_best_no_price()
                
                if current_price:
                    position.update_pnl(current_price)
                    
                    # Check stop loss / take profit
                    await self._check_exit_conditions(position, current_price)
            
            except Exception as e:
                logger.warning(f"Error updating position {position_id}: {e}")
    
    async def _check_exit_conditions(
        self, position: Position, current_price: Decimal
    ) -> None:
        """Check if position should be closed (stop loss, take profit)"""
        should_close = False
        reason = ""
        
        # Check stop loss
        if position.stop_loss:
            if position.side == PositionSide.LONG:
                if current_price <= position.stop_loss:
                    should_close = True
                    reason = "stop_loss"
            else:  # SHORT
                if current_price >= position.stop_loss:
                    should_close = True
                    reason = "stop_loss"
        
        # Check take profit
        if position.take_profit:
            if position.side == PositionSide.LONG:
                if current_price >= position.take_profit:
                    should_close = True
                    reason = "take_profit"
            else:  # SHORT
                if current_price <= position.take_profit:
                    should_close = True
                    reason = "take_profit"
        
        if should_close:
            await self.close_position(position.id, reason)
    
    async def close_position(
        self, position_id: str, reason: str = "manual"
    ) -> Optional[Position]:
        """Close position"""
        if position_id not in self.positions:
            return None
        
        position = self.positions[position_id]
        
        # Get current price
        orderbook = await self.client.get_orderbook(position.market_id)
        if not orderbook:
            return None
        
        if position.side == PositionSide.LONG:
            exit_price = orderbook.get_best_yes_price()
        else:
            exit_price = orderbook.get_best_no_price()
        
        if not exit_price:
            return None
        
        # Calculate realized PnL
        if position.side == PositionSide.LONG:
            realized_pnl = (exit_price - position.entry_price) * position.size
        else:  # SHORT
            realized_pnl = (position.entry_price - exit_price) * position.size
        
        position.realized_pnl = realized_pnl
        position.current_price = exit_price
        position.closed_at = datetime.utcnow()
        
        # Return capital
        proceeds = exit_price * position.size
        self.capital += proceeds
        
        # Record trade
        trade = Trade(
            id=f"trade_{datetime.utcnow().timestamp()}",
            market_id=position.market_id,
            side=OrderSide.YES if position.side == PositionSide.LONG else OrderSide.NO,
            price=exit_price,
            size=position.size,
            strategy_id=position.strategy_id,
            pnl=realized_pnl,
        )
        self.trade_history.append(trade)
        
        # Move to closed positions
        self.closed_positions.append(position)
        del self.positions[position_id]
        
        logger.info(
            f"Position closed: {position_id} @ {exit_price} "
            f"(PnL: {realized_pnl:.2f}, Reason: {reason})"
        )
        
        return position
    
    def get_statistics(self) -> Dict:
        """Get trading statistics"""
        total_trades = len(self.trade_history)
        winning_trades = [t for t in self.trade_history if t.pnl > 0]
        losing_trades = [t for t in self.trade_history if t.pnl < 0]
        
        win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0.0
        
        avg_win = (
            sum(t.pnl for t in winning_trades) / len(winning_trades)
            if winning_trades else Decimal("0")
        )
        avg_loss = (
            sum(t.pnl for t in losing_trades) / len(losing_trades)
            if losing_trades else Decimal("0")
        )
        
        return {
            "capital": float(self.capital),
            "equity": float(self.get_equity()),
            "initial_capital": float(self.initial_capital),
            "total_pnl": float(self.get_total_pnl()),
            "realized_pnl": float(self.get_realized_pnl()),
            "unrealized_pnl": float(self.get_unrealized_pnl()),
            "roi": self.get_roi(),
            "total_trades": total_trades,
            "win_rate": win_rate,
            "avg_win": float(avg_win),
            "avg_loss": float(avg_loss),
            "open_positions": len(self.positions),
            "closed_positions": len(self.closed_positions),
        }

