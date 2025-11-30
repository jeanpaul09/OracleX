"""Enhanced orderbook processing with depth analysis and advanced metrics"""

from typing import List, Optional, Dict, Any
from decimal import Decimal
from datetime import datetime
import structlog

from .models import OrderBook, OrderBookEntry

logger = structlog.get_logger(__name__)


class EnhancedOrderBook:
    """Enhanced orderbook with advanced analysis capabilities"""
    
    def __init__(self, orderbook: OrderBook):
        self.orderbook = orderbook
        self.timestamp = datetime.utcnow()
    
    def get_best_bid_ask(self, side: str = "YES") -> Dict[str, Optional[Decimal]]:
        """Get best bid and ask prices"""
        if side.upper() == "YES":
            best_bid = max((bid.price for bid in self.orderbook.yes_bids), default=None)
            best_ask = min((ask.price for ask in self.orderbook.yes_asks), default=None)
        else:
            best_bid = max((bid.price for bid in self.orderbook.no_bids), default=None)
            best_ask = min((ask.price for ask in self.orderbook.no_asks), default=None)
        
        return {
            "best_bid": best_bid,
            "best_ask": best_ask,
            "spread": best_ask - best_bid if (best_bid and best_ask) else None,
            "mid_price": (best_bid + best_ask) / 2 if (best_bid and best_ask) else None
        }
    
    def get_spread(self, side: str = "YES") -> Optional[Decimal]:
        """Calculate bid-ask spread"""
        best = self.get_best_bid_ask(side)
        return best.get("spread")
    
    def get_spread_percentage(self, side: str = "YES") -> Optional[Decimal]:
        """Calculate spread as percentage of mid price"""
        best = self.get_best_bid_ask(side)
        spread = best.get("spread")
        mid_price = best.get("mid_price")
        
        if spread and mid_price and mid_price > 0:
            return (spread / mid_price) * 100
        return None
    
    def get_depth(self, side: str = "YES", levels: int = 10) -> Dict[str, List[Dict[str, Decimal]]]:
        """Get orderbook depth for specified levels"""
        if side.upper() == "YES":
            bids = sorted(self.orderbook.yes_bids, key=lambda x: x.price, reverse=True)[:levels]
            asks = sorted(self.orderbook.yes_asks, key=lambda x: x.price)[:levels]
        else:
            bids = sorted(self.orderbook.no_bids, key=lambda x: x.price, reverse=True)[:levels]
            asks = sorted(self.orderbook.no_asks, key=lambda x: x.price)[:levels]
        
        return {
            "bids": [{"price": bid.price, "size": bid.size} for bid in bids],
            "asks": [{"price": ask.price, "size": ask.size} for ask in asks]
        }
    
    def get_liquidity(self, side: str = "YES", depth_pct: Decimal = Decimal("0.05")) -> Dict[str, Decimal]:
        """Calculate liquidity within price depth percentage"""
        best = self.get_best_bid_ask(side)
        mid_price = best.get("mid_price")
        
        if not mid_price:
            return {"bid_liquidity": Decimal("0"), "ask_liquidity": Decimal("0")}
        
        price_range = mid_price * depth_pct
        lower_bound = mid_price - price_range
        upper_bound = mid_price + price_range
        
        if side.upper() == "YES":
            bid_liquidity = sum(
                bid.size for bid in self.orderbook.yes_bids
                if lower_bound <= bid.price <= upper_bound
            )
            ask_liquidity = sum(
                ask.size for ask in self.orderbook.yes_asks
                if lower_bound <= ask.price <= upper_bound
            )
        else:
            bid_liquidity = sum(
                bid.size for bid in self.orderbook.no_bids
                if lower_bound <= bid.price <= upper_bound
            )
            ask_liquidity = sum(
                ask.size for ask in self.orderbook.no_asks
                if lower_bound <= ask.price <= upper_bound
            )
        
        return {
            "bid_liquidity": bid_liquidity,
            "ask_liquidity": ask_liquidity,
            "total_liquidity": bid_liquidity + ask_liquidity
        }
    
    def get_arbitrage_opportunity(self) -> Optional[Dict[str, Any]]:
        """Detect arbitrage opportunities (YES + NO should sum to ~1.0)"""
        yes_best = self.get_best_bid_ask("YES")
        no_best = self.get_best_bid_ask("NO")
        
        yes_mid = yes_best.get("mid_price")
        no_mid = no_best.get("mid_price")
        
        if yes_mid and no_mid:
            total = yes_mid + no_mid
            
            # Arbitrage opportunity if sum < 0.98 or > 1.02
            if total < Decimal("0.98"):
                opportunity = Decimal("1.0") - total
                return {
                    "type": "buy_arbitrage",
                    "opportunity_pct": opportunity * 100,
                    "yes_price": yes_mid,
                    "no_price": no_mid,
                    "total": total,
                    "profit_potential": opportunity
                }
            elif total > Decimal("1.02"):
                opportunity = total - Decimal("1.0")
                return {
                    "type": "sell_arbitrage",
                    "opportunity_pct": opportunity * 100,
                    "yes_price": yes_mid,
                    "no_price": no_mid,
                    "total": total,
                    "profit_potential": opportunity
                }
        
        return None
    
    def get_imbalance(self, side: str = "YES") -> Decimal:
        """Calculate orderbook imbalance (bid size vs ask size)"""
        if side.upper() == "YES":
            total_bid_size = sum(bid.size for bid in self.orderbook.yes_bids)
            total_ask_size = sum(ask.size for ask in self.orderbook.yes_asks)
        else:
            total_bid_size = sum(bid.size for bid in self.orderbook.no_bids)
            total_ask_size = sum(ask.size for ask in self.orderbook.no_asks)
        
        total_size = total_bid_size + total_ask_size
        if total_size == 0:
            return Decimal("0")
        
        # Imbalance: positive = more bids (bullish), negative = more asks (bearish)
        imbalance = (total_bid_size - total_ask_size) / total_size
        return imbalance
    
    def get_market_impact(self, side: str = "YES", size: Decimal = Decimal("1.0")) -> Dict[str, Decimal]:
        """Estimate market impact for a trade of given size"""
        if side.upper() == "YES":
            asks = sorted(self.orderbook.yes_asks, key=lambda x: x.price)
        else:
            asks = sorted(self.orderbook.no_asks, key=lambda x: x.price)
        
        remaining_size = size
        total_cost = Decimal("0")
        levels_consumed = 0
        
        for ask in asks:
            if remaining_size <= 0:
                break
            
            size_to_take = min(remaining_size, ask.size)
            total_cost += size_to_take * ask.price
            remaining_size -= size_to_take
            levels_consumed += 1
        
        avg_price = total_cost / size if size > 0 else Decimal("0")
        best = self.get_best_bid_ask(side)
        best_ask = best.get("best_ask")
        
        price_impact = (avg_price - best_ask) / best_ask * 100 if best_ask else Decimal("0")
        
        return {
            "average_price": avg_price,
            "price_impact_pct": price_impact,
            "levels_consumed": levels_consumed,
            "total_cost": total_cost
        }
    
    def get_orderbook_summary(self) -> Dict[str, Any]:
        """Get comprehensive orderbook summary"""
        yes_best = self.get_best_bid_ask("YES")
        no_best = self.get_best_bid_ask("NO")
        
        yes_liquidity = self.get_liquidity("YES")
        no_liquidity = self.get_liquidity("NO")
        
        arbitrage = self.get_arbitrage_opportunity()
        
        return {
            "market_id": self.orderbook.market_id,
            "timestamp": self.timestamp.isoformat(),
            "yes": {
                "best_bid": str(yes_best.get("best_bid")) if yes_best.get("best_bid") else None,
                "best_ask": str(yes_best.get("best_ask")) if yes_best.get("best_ask") else None,
                "spread": str(yes_best.get("spread")) if yes_best.get("spread") else None,
                "spread_pct": str(self.get_spread_percentage("YES")) if self.get_spread_percentage("YES") else None,
                "mid_price": str(yes_best.get("mid_price")) if yes_best.get("mid_price") else None,
                "liquidity": {
                    "bid": str(yes_liquidity["bid_liquidity"]),
                    "ask": str(yes_liquidity["ask_liquidity"]),
                    "total": str(yes_liquidity["total_liquidity"])
                },
                "imbalance": str(self.get_imbalance("YES"))
            },
            "no": {
                "best_bid": str(no_best.get("best_bid")) if no_best.get("best_bid") else None,
                "best_ask": str(no_best.get("best_ask")) if no_best.get("best_ask") else None,
                "spread": str(no_best.get("spread")) if no_best.get("spread") else None,
                "spread_pct": str(self.get_spread_percentage("NO")) if self.get_spread_percentage("NO") else None,
                "mid_price": str(no_best.get("mid_price")) if no_best.get("mid_price") else None,
                "liquidity": {
                    "bid": str(no_liquidity["bid_liquidity"]),
                    "ask": str(no_liquidity["ask_liquidity"]),
                    "total": str(no_liquidity["total_liquidity"])
                },
                "imbalance": str(self.get_imbalance("NO"))
            },
            "arbitrage": arbitrage,
            "depth_levels": {
                "yes": self.get_depth("YES", 5),
                "no": self.get_depth("NO", 5)
            }
        }

