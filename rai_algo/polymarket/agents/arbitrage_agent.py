"""Arbitrage Agent - Finds price discrepancies"""

import asyncio
from typing import List, Optional
from decimal import Decimal
import structlog

from ..models import Market, OrderBook, Opportunity, OpportunityType, OrderSide
from ..client import PolymarketClient

logger = structlog.get_logger(__name__)


class ArbitrageAgent:
    """Specialized agent for finding arbitrage opportunities"""
    
    def __init__(self, client: PolymarketClient):
        self.client = client
        self.opportunities: List[Opportunity] = []
        self.running = False
    
    async def start(self) -> None:
        """Start arbitrage scanning"""
        self.running = True
        logger.info("Arbitrage Agent started")
        
        while self.running:
            try:
                await self.scan_arbitrage()
                await asyncio.sleep(30)  # Scan every 30 seconds
            except Exception as e:
                logger.error(f"Error in arbitrage scan: {e}")
                await asyncio.sleep(30)
    
    async def stop(self) -> None:
        """Stop arbitrage agent"""
        self.running = False
        logger.info("Arbitrage Agent stopped")
    
    async def scan_arbitrage(self) -> None:
        """Scan for arbitrage opportunities"""
        # Get active markets
        markets = await self.client.get_markets(limit=500)
        
        tasks = [self._check_market_arbitrage(market) for market in markets]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        opportunities_found = sum(
            1 for r in results if isinstance(r, Opportunity) and r is not None
        )
        
        if opportunities_found > 0:
            logger.info(f"Found {opportunities_found} arbitrage opportunities")
    
    async def _check_market_arbitrage(self, market: Market) -> Optional[Opportunity]:
        """Check single market for arbitrage"""
        try:
            orderbook = await self.client.get_orderbook(market.id)
            if not orderbook:
                return None
            
            arb_value = orderbook.get_arbitrage_opportunity()
            if arb_value and arb_value > Decimal("0.01"):  # At least 1% edge
                yes_price = orderbook.get_best_yes_price()
                no_price = orderbook.get_best_no_price()
                
                if yes_price and no_price:
                    # Determine best side
                    if yes_price < no_price:
                        side = OrderSide.YES
                        entry_price = yes_price
                    else:
                        side = OrderSide.NO
                        entry_price = no_price
                    
                    score = min(float(arb_value) * 20, 1.0)  # Scale to 0-1
                    
                    opportunity = Opportunity(
                        market_id=market.id,
                        market=market,
                        opportunity_type=OpportunityType.ARBITRAGE,
                        side=side,
                        score=score,
                        expected_return=float(arb_value),
                        risk_level="low",
                        entry_price=entry_price,
                        target_price=Decimal("0.5"),
                        reasoning=f"Arbitrage: YES+NO={1.0-arb_value:.4f}, edge={arb_value:.4%}",
                        metadata={
                            "arbitrage_value": str(arb_value),
                            "yes_price": str(yes_price),
                            "no_price": str(no_price),
                        }
                    )
                    
                    self.opportunities.append(opportunity)
                    return opportunity
        
        except Exception as e:
            logger.warning(f"Error checking arbitrage for {market.id}: {e}")
        
        return None
    
    def get_opportunities(self, min_score: float = 0.5) -> List[Opportunity]:
        """Get arbitrage opportunities"""
        return [
            o for o in self.opportunities
            if o.score >= min_score
        ]

