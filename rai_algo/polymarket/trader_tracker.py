"""Trader Tracking System - Tracks SOLID traders and insiders"""

import asyncio
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from decimal import Decimal
import structlog

from .models import TraderProfile, TraderSignal, OrderSide, Position, Trade
from .client import PolymarketClient
from .config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


class TraderTracker:
    """Tracks and analyzes trader behavior to identify insiders/SOLID traders"""
    
    def __init__(self, client: PolymarketClient):
        self.client = client
        self.traders: Dict[str, TraderProfile] = {}
        self.signals: List[TraderSignal] = []
        self.tracked_addresses: List[str] = []  # Addresses to track
        self.running = False
    
    async def initialize(self) -> None:
        """Initialize trader tracker"""
        # Load tracked addresses (could be from config, database, etc.)
        # For now, empty list - addresses can be added via API
        logger.info("Trader Tracker initialized")
    
    async def start(self) -> None:
        """Start tracking loop"""
        self.running = True
        logger.info("Trader Tracker started")
        
        while self.running:
            try:
                await self._scan_trader_activity()
                await asyncio.sleep(60)  # Scan every minute
            except Exception as e:
                logger.error(f"Error in trader tracking: {e}")
                await asyncio.sleep(60)
    
    async def stop(self) -> None:
        """Stop tracking"""
        self.running = False
        logger.info("Trader Tracker stopped")
    
    async def add_tracked_address(self, address: str, username: Optional[str] = None) -> None:
        """Add address to tracking list"""
        if address not in self.tracked_addresses:
            self.tracked_addresses.append(address)
            logger.info(f"Added tracked address: {address}")
        
        # Initialize profile if not exists
        if address not in self.traders:
            self.traders[address] = TraderProfile(
                address=address,
                username=username
            )
    
    async def _scan_trader_activity(self) -> None:
        """Scan for activity from tracked traders"""
        for address in self.tracked_addresses:
            try:
                await self._analyze_trader(address)
            except Exception as e:
                logger.warning(f"Error analyzing trader {address}: {e}")
    
    async def _analyze_trader(self, address: str) -> None:
        """Analyze trader's recent activity"""
        # In a real implementation, this would query Polymarket's API
        # for trades/positions by this address
        
        # For now, simulate or use available data
        # This would need Polymarket's on-chain data or API endpoints
        
        profile = self.traders.get(address)
        if not profile:
            profile = TraderProfile(address=address)
            self.traders[address] = profile
        
        # Update last seen
        profile.last_seen = datetime.utcnow()
        
        # Calculate metrics (would use real data)
        # profile.total_trades = ...
        # profile.win_rate = ...
        # profile.total_pnl = ...
    
    async def detect_signal(
        self, address: str, market_id: str, side: OrderSide, size: Decimal, price: Decimal
    ) -> Optional[TraderSignal]:
        """Detect and record a signal from a tracked trader"""
        profile = self.traders.get(address)
        if not profile:
            return None
        
        # Calculate confidence based on trader's track record
        confidence = self._calculate_confidence(profile)
        
        signal = TraderSignal(
            trader_address=address,
            market_id=market_id,
            side=side,
            size=size,
            price=price,
            timestamp=datetime.utcnow(),
            confidence=confidence
        )
        
        self.signals.append(signal)
        logger.info(
            f"Signal detected: {address[:8]}... {side.value} {market_id[:8]} "
            f"(Confidence: {confidence:.2%})"
        )
        
        return signal
    
    def _calculate_confidence(self, profile: TraderProfile) -> float:
        """Calculate confidence in trader's signal"""
        # Base confidence on win rate and reliability
        base_confidence = profile.win_rate * profile.reliability_score
        
        # Boost for high PnL traders
        if profile.total_pnl > 0:
            pnl_boost = min(float(profile.total_pnl) / 10000, 0.2)  # Max 20% boost
            base_confidence += pnl_boost
        
        # Reduce for risky traders
        if profile.risk_score > 0.7:
            base_confidence *= 0.8
        
        return min(base_confidence, 1.0)
    
    def get_top_traders(
        self, min_trades: int = 10, min_win_rate: float = 0.6
    ) -> List[TraderProfile]:
        """Get top performing traders"""
        traders = [
            t for t in self.traders.values()
            if t.total_trades >= min_trades and t.win_rate >= min_win_rate
        ]
        
        # Sort by reliability score
        traders.sort(key=lambda x: x.reliability_score, reverse=True)
        
        return traders
    
    def get_recent_signals(
        self, hours: int = 24, min_confidence: float = 0.7
    ) -> List[TraderSignal]:
        """Get recent signals from tracked traders"""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        
        signals = [
            s for s in self.signals
            if s.timestamp > cutoff and s.confidence >= min_confidence
        ]
        
        # Sort by confidence
        signals.sort(key=lambda x: x.confidence, reverse=True)
        
        return signals
    
    async def update_trader_metrics(
        self, address: str, trade: Trade, outcome: Optional[bool] = None
    ) -> None:
        """Update trader metrics based on trade outcome"""
        profile = self.traders.get(address)
        if not profile:
            return
        
        profile.total_trades += 1
        
        if outcome is not None:
            # Update win rate
            if outcome:
                wins = profile.win_rate * (profile.total_trades - 1) + 1
            else:
                wins = profile.win_rate * (profile.total_trades - 1)
            profile.win_rate = wins / profile.total_trades
        
        # Update PnL
        profile.total_pnl += trade.pnl
        
        # Update reliability score (based on consistency)
        if profile.total_trades > 10:
            # Reliability increases with more trades and higher win rate
            profile.reliability_score = min(
                profile.win_rate * (1 + profile.total_trades / 100),
                1.0
            )
        
        # Update preferred markets
        if trade.market_id not in profile.preferred_markets:
            profile.preferred_markets.append(trade.market_id)
            # Keep only last 10
            profile.preferred_markets = profile.preferred_markets[-10:]
        
        logger.debug(f"Updated metrics for {address[:8]}: Win Rate={profile.win_rate:.2%}")

