"""One-click trading system with order templates and quick execution"""

from typing import Dict, Any, Optional, List
from decimal import Decimal
from datetime import datetime
import structlog

from .models import Order, OrderSide, OrderType
from .client import PolymarketClient

logger = structlog.get_logger(__name__)


class OrderTemplate:
    """Template for quick order placement"""
    
    def __init__(
        self,
        name: str,
        market_id: str,
        side: OrderSide,
        order_type: OrderType = OrderType.LIMIT,
        size: Optional[Decimal] = None,
        price_offset_pct: Optional[Decimal] = None,
        use_best_price: bool = True
    ):
        self.name = name
        self.market_id = market_id
        self.side = side
        self.order_type = order_type
        self.size = size or Decimal("1.0")
        self.price_offset_pct = price_offset_pct or Decimal("0")
        self.use_best_price = use_best_price
        self.created_at = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert template to dictionary"""
        return {
            "name": self.name,
            "market_id": self.market_id,
            "side": self.side.value,
            "order_type": self.order_type.value,
            "size": str(self.size),
            "price_offset_pct": str(self.price_offset_pct),
            "use_best_price": self.use_best_price
        }


class OneClickTrader:
    """One-click trading system"""
    
    def __init__(self, client: PolymarketClient):
        self.client = client
        self.templates: Dict[str, OrderTemplate] = {}
        self.recent_orders: List[Order] = []
        self.max_recent_orders = 50
    
    def create_template(
        self,
        name: str,
        market_id: str,
        side: OrderSide,
        size: Decimal,
        order_type: OrderType = OrderType.LIMIT,
        price_offset_pct: Decimal = Decimal("0"),
        use_best_price: bool = True
    ) -> OrderTemplate:
        """Create a new order template"""
        template = OrderTemplate(
            name=name,
            market_id=market_id,
            side=side,
            order_type=order_type,
            size=size,
            price_offset_pct=price_offset_pct,
            use_best_price=use_best_price
        )
        self.templates[name] = template
        logger.info(f"Created order template: {name}")
        return template
    
    def get_template(self, name: str) -> Optional[OrderTemplate]:
        """Get template by name"""
        return self.templates.get(name)
    
    def list_templates(self) -> List[Dict[str, Any]]:
        """List all templates"""
        return [template.to_dict() for template in self.templates.values()]
    
    def delete_template(self, name: str) -> bool:
        """Delete a template"""
        if name in self.templates:
            del self.templates[name]
            logger.info(f"Deleted template: {name}")
            return True
        return False
    
    async def execute_template(
        self,
        template_name: str,
        size_override: Optional[Decimal] = None,
        price_override: Optional[Decimal] = None
    ) -> Optional[Dict[str, Any]]:
        """Execute an order using a template"""
        template = self.get_template(template_name)
        if not template:
            logger.error(f"Template not found: {template_name}")
            return None
        
        # Get orderbook to determine best price
        orderbook = await self.client.get_orderbook(template.market_id)
        if not orderbook:
            logger.error(f"Failed to get orderbook for market: {template.market_id}")
            return None
        
        # Determine price
        if price_override:
            price = price_override
        elif template.use_best_price:
            if template.side == OrderSide.YES:
                best_price = orderbook.get_best_yes_price()
            else:
                best_price = orderbook.get_best_no_price()
            
            if not best_price:
                logger.error("No best price available")
                return None
            
            # Apply offset
            if template.side == OrderSide.YES:
                # For YES buy, use best ask (or bid if selling)
                price = best_price * (1 + template.price_offset_pct / 100)
            else:
                price = best_price * (1 + template.price_offset_pct / 100)
        else:
            logger.error("Price must be specified if not using best price")
            return None
        
        # Determine size
        size = size_override or template.size
        
        # Create order
        order = Order(
            market_id=template.market_id,
            side=template.side,
            order_type=template.order_type,
            price=price,
            size=size
        )
        
        # Place order
        try:
            result = await self.client.place_order(order)
            
            # Track recent orders
            self.recent_orders.insert(0, order)
            if len(self.recent_orders) > self.max_recent_orders:
                self.recent_orders.pop()
            
            logger.info(f"Executed template {template_name}: {result}")
            return result
        except Exception as e:
            logger.error(f"Failed to execute template {template_name}: {e}")
            return None
    
    async def quick_buy(
        self,
        market_id: str,
        size: Decimal,
        side: OrderSide = OrderSide.YES,
        use_market_order: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Quick buy with best available price"""
        orderbook = await self.client.get_orderbook(market_id)
        if not orderbook:
            return None
        
        if side == OrderSide.YES:
            best_price = orderbook.get_best_yes_price()
        else:
            best_price = orderbook.get_best_no_price()
        
        if not best_price:
            return None
        
        order = Order(
            market_id=market_id,
            side=side,
            order_type=OrderType.MARKET if use_market_order else OrderType.LIMIT,
            price=best_price,
            size=size
        )
        
        try:
            result = await self.client.place_order(order)
            self.recent_orders.insert(0, order)
            if len(self.recent_orders) > self.max_recent_orders:
                self.recent_orders.pop()
            return result
        except Exception as e:
            logger.error(f"Quick buy failed: {e}")
            return None
    
    async def quick_sell(
        self,
        market_id: str,
        size: Decimal,
        side: OrderSide = OrderSide.YES,
        use_market_order: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Quick sell with best available price"""
        orderbook = await self.client.get_orderbook(market_id)
        if not orderbook:
            return None
        
        if side == OrderSide.YES:
            best_price = orderbook.get_best_yes_price()
        else:
            best_price = orderbook.get_best_no_price()
        
        if not best_price:
            return None
        
        order = Order(
            market_id=market_id,
            side=OrderSide.NO if side == OrderSide.YES else OrderSide.YES,
            order_type=OrderType.MARKET if use_market_order else OrderType.LIMIT,
            price=best_price,
            size=size
        )
        
        try:
            result = await self.client.place_order(order)
            self.recent_orders.insert(0, order)
            if len(self.recent_orders) > self.max_recent_orders:
                self.recent_orders.pop()
            return result
        except Exception as e:
            logger.error(f"Quick sell failed: {e}")
            return None
    
    def get_recent_orders(self, limit: int = 10) -> List[Order]:
        """Get recent orders"""
        return self.recent_orders[:limit]
    
    def clear_recent_orders(self) -> None:
        """Clear recent orders history"""
        self.recent_orders.clear()

