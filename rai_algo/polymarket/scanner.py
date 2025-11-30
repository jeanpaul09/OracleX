"""Market Scanner Agent - Continuously scans markets for opportunities"""

import asyncio
from typing import List, Optional
from datetime import datetime, timedelta
from decimal import Decimal
import structlog

from .models import Market, OrderBook, Opportunity, OpportunityType, OrderSide
from .client import PolymarketClient
from .config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


class MarketScannerAgent:
    """Continuously scans Polymarket for trading opportunities"""
    
    def __init__(self, client: PolymarketClient):
        self.client = client
        self.running = False
        self.scan_interval = settings.scan_interval_seconds
        self.opportunities: List[Opportunity] = []
        self.scanned_markets: set = set()
        self.last_scan: Optional[datetime] = None
    
    async def start(self) -> None:
        """Start scanning loop"""
        self.running = True
        logger.info("Market Scanner Agent started")
        
        while self.running:
            try:
                await self.scan_markets()
                await asyncio.sleep(self.scan_interval)
            except Exception as e:
                logger.error(f"Error in scan loop: {e}")
                await asyncio.sleep(self.scan_interval)
    
    async def stop(self) -> None:
        """Stop scanning"""
        self.running = False
        logger.info("Market Scanner Agent stopped")
    
    async def scan_markets(self) -> None:
        """Scan all active markets"""
        logger.info("Starting market scan")
        
        # Get active markets
        markets = await self.client.get_markets(
            filters={"status": "open"},
            limit=1000
        )
        
        logger.info(f"Scanning {len(markets)} markets")
        
        # Analyze each market
        tasks = [self.analyze_market(market) for market in markets[:100]]  # Limit concurrent
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        opportunities_found = sum(
            1 for r in results if isinstance(r, list) and len(r) > 0
        )
        
        self.last_scan = datetime.utcnow()
        logger.info(f"Scan complete: {opportunities_found} markets with opportunities")
    
    async def analyze_market(self, market: Market) -> List[Opportunity]:
        """Analyze single market for opportunities"""
        opportunities = []
        
        try:
            # Skip if recently scanned
            if market.id in self.scanned_markets:
                return opportunities
            
            # Get orderbook
            orderbook = await self.client.get_orderbook(market.id)
            if not orderbook:
                return opportunities
            
            # Check for arbitrage
            arb_opp = await self.check_arbitrage(market, orderbook)
            if arb_opp:
                opportunities.append(arb_opp)
            
            # Check for time decay
            time_decay_opp = await self.check_time_decay(market, orderbook)
            if time_decay_opp:
                opportunities.append(time_decay_opp)
            
            # Check for liquidity opportunities
            liquidity_opp = await self.check_liquidity(market, orderbook)
            if liquidity_opp:
                opportunities.append(liquidity_opp)
            
            # Store opportunities
            if opportunities:
                self.opportunities.extend(opportunities)
                self.scanned_markets.add(market.id)
                logger.info(
                    f"Found {len(opportunities)} opportunities in market {market.id[:8]}"
                )
            
        except Exception as e:
            logger.warning(f"Error analyzing market {market.id}: {e}")
        
        return opportunities
    
    async def check_arbitrage(
        self, market: Market, orderbook: OrderBook
    ) -> Optional[Opportunity]:
        """Check for arbitrage opportunity (YES + NO < 0.98)"""
        arb_value = orderbook.get_arbitrage_opportunity()
        
        if arb_value and arb_value > Decimal("0.02"):  # At least 2% edge
            score = float(arb_value) * 10  # Scale to 0-1
            score = min(score, 1.0)
            
            # Determine which side to take
            yes_price = orderbook.get_best_yes_price()
            no_price = orderbook.get_best_no_price()
            
            if yes_price and no_price:
                # Buy the cheaper side
                if yes_price < no_price:
                    side = OrderSide.YES
                    entry_price = yes_price
                else:
                    side = OrderSide.NO
                    entry_price = no_price
                
                return Opportunity(
                    market_id=market.id,
                    market=market,
                    opportunity_type=OpportunityType.ARBITRAGE,
                    side=side,
                    score=score,
                    expected_return=float(arb_value),
                    risk_level="low",
                    entry_price=entry_price,
                    target_price=Decimal("0.5"),  # Target middle price
                    reasoning=f"Arbitrage opportunity: YES+NO sum = {1.0 - arb_value:.4f}, edge = {arb_value:.4f}",
                    metadata={
                        "arbitrage_value": str(arb_value),
                        "yes_price": str(yes_price),
                        "no_price": str(no_price),
                    }
                )
        
        return None
    
    async def check_time_decay(
        self, market: Market, orderbook: OrderBook
    ) -> Optional[Opportunity]:
        """Check for time decay opportunity (approaching resolution)"""
        if not market.end_date_iso:
            return None
        
        time_until_resolution = market.end_date_iso - datetime.utcnow()
        
        # Look for markets resolving within 24 hours
        if timedelta(hours=0) < time_until_resolution < timedelta(hours=24):
            yes_price = orderbook.get_best_yes_price()
            no_price = orderbook.get_best_no_price()
            
            if yes_price and no_price:
                # If one side is heavily favored (>80%), time decay opportunity
                if yes_price > Decimal("0.8"):
                    score = 0.7  # Moderate confidence
                    return Opportunity(
                        market_id=market.id,
                        market=market,
                        opportunity_type=OpportunityType.TIME_DECAY,
                        side=OrderSide.YES,
                        score=score,
                        expected_return=0.15,
                        risk_level="medium",
                        entry_price=yes_price,
                        target_price=Decimal("1.0"),
                        reasoning=f"Time decay: Market resolves in {time_until_resolution}, YES at {yes_price:.4f}",
                        expires_at=market.end_date_iso,
                        metadata={
                            "hours_until_resolution": time_until_resolution.total_seconds() / 3600,
                            "current_yes_price": str(yes_price),
                        }
                    )
                elif no_price > Decimal("0.8"):
                    score = 0.7
                    return Opportunity(
                        market_id=market.id,
                        market=market,
                        opportunity_type=OpportunityType.TIME_DECAY,
                        side=OrderSide.NO,
                        score=score,
                        expected_return=0.15,
                        risk_level="medium",
                        entry_price=no_price,
                        target_price=Decimal("1.0"),
                        reasoning=f"Time decay: Market resolves in {time_until_resolution}, NO at {no_price:.4f}",
                        expires_at=market.end_date_iso,
                        metadata={
                            "hours_until_resolution": time_until_resolution.total_seconds() / 3600,
                            "current_no_price": str(no_price),
                        }
                    )
        
        return None
    
    async def check_liquidity(
        self, market: Market, orderbook: OrderBook
    ) -> Optional[Opportunity]:
        """Check for liquidity-based opportunities"""
        # Low liquidity markets may have price inefficiencies
        if market.liquidity < Decimal("1000"):  # Low liquidity threshold
            yes_price = orderbook.get_best_yes_price()
            no_price = orderbook.get_best_no_price()
            
            if yes_price and no_price:
                # If prices are far from 0.5, might be mispriced
                if abs(float(yes_price) - 0.5) > 0.2:
                    score = 0.6  # Lower confidence for liquidity plays
                    side = OrderSide.YES if yes_price < Decimal("0.3") else OrderSide.NO
                    
                    return Opportunity(
                        market_id=market.id,
                        market=market,
                        opportunity_type=OpportunityType.LIQUIDITY,
                        side=side,
                        score=score,
                        expected_return=0.10,
                        risk_level="high",
                        entry_price=yes_price if side == OrderSide.YES else no_price,
                        reasoning=f"Low liquidity market ({market.liquidity}) with potential mispricing",
                        metadata={
                            "liquidity": str(market.liquidity),
                            "yes_price": str(yes_price),
                            "no_price": str(no_price),
                        }
                    )
        
        return None
    
    def get_opportunities(
        self,
        min_score: Optional[float] = None,
        opportunity_type: Optional[OpportunityType] = None,
        limit: int = 100
    ) -> List[Opportunity]:
        """Get filtered opportunities"""
        opportunities = self.opportunities
        
        if min_score:
            opportunities = [o for o in opportunities if o.score >= min_score]
        
        if opportunity_type:
            opportunities = [o for o in opportunities if o.opportunity_type == opportunity_type]
        
        # Sort by score descending
        opportunities.sort(key=lambda x: x.score, reverse=True)
        
        return opportunities[:limit]
    
    def clear_old_opportunities(self, max_age_hours: int = 24) -> None:
        """Clear opportunities older than max_age_hours"""
        cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)
        self.opportunities = [
            o for o in self.opportunities
            if o.detected_at > cutoff or (o.expires_at and o.expires_at > datetime.utcnow())
        ]

