"""Agent Orchestrator - Coordinates all agents"""

import asyncio
from typing import List, Dict, Optional, Any
from datetime import datetime
import structlog
import redis.asyncio as redis
from collections import deque

from .models import Opportunity, StrategyBlueprint, Position, Trade
from .client import PolymarketClient
from .scanner import MarketScannerAgent
from .demo_trader import DemoTrader
from .strategy_generator import StrategyGeneratorAgent
from .config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


class AgentOrchestrator:
    """Orchestrates all agents and manages shared knowledge"""
    
    def __init__(self):
        self.client = PolymarketClient()
        self.scanner = MarketScannerAgent(self.client)
        self.demo_trader = DemoTrader(self.client)
        self.strategy_generator = StrategyGeneratorAgent(self.client, self.demo_trader)
        
        # Knowledge base (in-memory, can be replaced with Redis/PostgreSQL)
        self.opportunities: deque = deque(maxlen=1000)
        self.strategies: Dict[str, StrategyBlueprint] = {}
        self.positions: Dict[str, Position] = {}
        self.trades: deque = deque(maxlen=10000)
        
        # Message bus (in-memory pub/sub)
        self.subscribers: Dict[str, List[callable]] = {}
        
        # Redis connection (optional)
        self.redis_client: Optional[redis.Redis] = None
        
        self.running = False
    
    async def initialize(self) -> None:
        """Initialize orchestrator and all agents"""
        logger.info("Initializing Agent Orchestrator")
        
        # Initialize client
        await self.client.initialize()
        
        # Initialize Redis if configured
        try:
            self.redis_client = await redis.from_url(
                settings.redis_url,
                decode_responses=True
            )
            await self.redis_client.ping()
            logger.info("Redis connected")
        except Exception as e:
            logger.warning(f"Redis not available: {e}, using in-memory storage")
        
        logger.info("Agent Orchestrator initialized")
    
    async def start(self) -> None:
        """Start orchestrator and all agents"""
        self.running = True
        logger.info("Starting Agent Orchestrator")
        
        # Start scanner agent
        scanner_task = asyncio.create_task(self.scanner.start())
        
        # Start position updater
        position_updater_task = asyncio.create_task(self._update_positions_loop())
        
        # Start opportunity processor
        opportunity_processor_task = asyncio.create_task(self._process_opportunities_loop())
        
        # Start strategy generator (periodic)
        strategy_generator_task = asyncio.create_task(self._generate_strategies_loop())
        
        try:
            await asyncio.gather(
                scanner_task,
                position_updater_task,
                opportunity_processor_task,
                strategy_generator_task,
                return_exceptions=True
            )
        except Exception as e:
            logger.error(f"Error in orchestrator: {e}")
        finally:
            await self.stop()
    
    async def stop(self) -> None:
        """Stop orchestrator and all agents"""
        self.running = False
        logger.info("Stopping Agent Orchestrator")
        
        await self.scanner.stop()
        await self.client.shutdown()
        
        if self.redis_client:
            await self.redis_client.close()
        
        logger.info("Agent Orchestrator stopped")
    
    async def _update_positions_loop(self) -> None:
        """Continuously update positions"""
        while self.running:
            try:
                await self.demo_trader.update_positions()
                await asyncio.sleep(10)  # Update every 10 seconds
            except Exception as e:
                logger.error(f"Error updating positions: {e}")
                await asyncio.sleep(10)
    
    async def _process_opportunities_loop(self) -> None:
        """Process opportunities from scanner"""
        while self.running:
            try:
                # Get new opportunities from scanner
                opportunities = self.scanner.get_opportunities(
                    min_score=settings.opportunity_score_threshold
                )
                
                for opportunity in opportunities:
                    # Check if already processed
                    if any(o.id == opportunity.id for o in self.opportunities):
                        continue
                    
                    # Store opportunity
                    self.opportunities.append(opportunity)
                    await self._store_opportunity(opportunity)
                    
                    # Publish to subscribers
                    await self._publish("opportunity", opportunity.dict())
                    
                    # Auto-trade if enabled and criteria met
                    if opportunity.score >= 0.8:  # High confidence
                        await self._consider_trading(opportunity)
                
                await asyncio.sleep(5)  # Check every 5 seconds
            
            except Exception as e:
                logger.error(f"Error processing opportunities: {e}")
                await asyncio.sleep(5)
    
    async def _generate_strategies_loop(self) -> None:
        """Periodically generate new strategies"""
        while self.running:
            try:
                # Generate strategy every hour
                await asyncio.sleep(3600)
                
                if len(self.strategy_generator.strategies) < 10:  # Max 10 strategies
                    # Get market data
                    markets = await self.client.get_markets(limit=100)
                    
                    # Get opportunities
                    opportunities = list(self.opportunities)[-50:]  # Last 50
                    
                    # Generate strategy
                    from .models import StrategyType
                    strategy_types = [
                        StrategyType.ARBITRAGE,
                        StrategyType.PROBABILITY_EDGE,
                        StrategyType.TIME_DECAY,
                    ]
                    
                    for strategy_type in strategy_types:
                        strategy = await self.strategy_generator.generate_strategy(
                            strategy_type=strategy_type,
                            market_data=markets,
                            opportunities=opportunities
                        )
                        
                        if strategy:
                            self.strategies[strategy.name] = strategy
                            await self._store_strategy(strategy)
                            await self._publish("strategy_generated", strategy.dict())
            
            except Exception as e:
                logger.error(f"Error generating strategies: {e}")
    
    async def _consider_trading(self, opportunity: Opportunity) -> None:
        """Consider trading an opportunity"""
        try:
            # Check if we have open positions limit
            if len(self.demo_trader.positions) >= settings.max_concurrent_positions:
                return
            
            # Select best strategy for this opportunity
            strategy = self._select_strategy(opportunity)
            
            if strategy:
                # Calculate position size
                position_size = self._calculate_position_size(opportunity, strategy)
                
                # Place order
                order = await self.demo_trader.place_order(
                    opportunity=opportunity,
                    position_size_pct=position_size,
                    strategy_id=strategy.name,
                    strategy_name=strategy.name
                )
                
                if order:
                    await self._publish("trade_executed", {
                        "order_id": order.id,
                        "opportunity_id": opportunity.id,
                        "strategy": strategy.name
                    })
        
        except Exception as e:
            logger.error(f"Error considering trade: {e}")
    
    def _select_strategy(self, opportunity: Opportunity) -> Optional[StrategyBlueprint]:
        """Select best strategy for opportunity"""
        # Get strategies matching opportunity type
        matching_strategies = [
            s for s in self.strategies.values()
            if s.strategy_type.value in opportunity.opportunity_type.value
        ]
        
        if not matching_strategies:
            # Use best overall strategy
            matching_strategies = list(self.strategies.values())
        
        if not matching_strategies:
            return None
        
        # Sort by performance
        matching_strategies.sort(
            key=lambda s: s.test_results.get("win_rate", 0) if s.test_results else 0,
            reverse=True
        )
        
        return matching_strategies[0]
    
    def _calculate_position_size(
        self, opportunity: Opportunity, strategy: StrategyBlueprint
    ) -> float:
        """Calculate position size based on risk management"""
        # Get max position size from strategy or settings
        max_size = strategy.risk_management.get(
            "max_position_size",
            settings.max_position_size
        )
        
        # Adjust based on opportunity score
        adjusted_size = max_size * opportunity.score
        
        return min(adjusted_size, max_size)
    
    async def _store_opportunity(self, opportunity: Opportunity) -> None:
        """Store opportunity in knowledge base"""
        if self.redis_client:
            await self.redis_client.setex(
                f"opportunity:{opportunity.id}",
                3600,  # 1 hour TTL
                opportunity.json()
            )
    
    async def _store_strategy(self, strategy: StrategyBlueprint) -> None:
        """Store strategy in knowledge base"""
        if self.redis_client:
            await self.redis_client.set(
                f"strategy:{strategy.name}",
                strategy.json()
            )
    
    async def _publish(self, event_type: str, data: Any) -> None:
        """Publish event to message bus"""
        if self.redis_client:
            await self.redis_client.publish(
                f"events:{event_type}",
                str(data) if not isinstance(data, dict) else str(data)
            )
        
        # Notify in-memory subscribers
        subscribers = self.subscribers.get(event_type, [])
        for callback in subscribers:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(data)
                else:
                    callback(data)
            except Exception as e:
                logger.error(f"Error in subscriber callback: {e}")
    
    def subscribe(self, event_type: str, callback: callable) -> None:
        """Subscribe to event type"""
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(callback)
    
    def get_status(self) -> Dict[str, Any]:
        """Get orchestrator status"""
        stats = self.demo_trader.get_statistics()
        return {
            "running": self.running,
            "opportunities": len(self.opportunities),
            "strategies": len(self.strategies),
            "positions": len(self.demo_trader.positions),
            "trades": len(self.demo_trader.trade_history),
            "statistics": stats,
        }

