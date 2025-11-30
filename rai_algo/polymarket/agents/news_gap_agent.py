"""News Gap Agent - Identifies markets mispriced relative to news"""

import asyncio
import feedparser
from typing import List, Optional, Dict
from datetime import datetime
from decimal import Decimal
import structlog

from ..models import Market, Opportunity, OpportunityType, OrderSide
from ..client import PolymarketClient
from ..config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


class NewsGapAgent:
    """Agent that identifies markets mispriced relative to news/events"""
    
    def __init__(self, client: PolymarketClient):
        self.client = client
        self.opportunities: List[Opportunity] = []
        self.news_sources: List[str] = []
        self.running = False
    
    async def initialize(self) -> None:
        """Initialize news sources"""
        # Add news sources (RSS feeds, APIs, etc.)
        self.news_sources = [
            "https://feeds.feedburner.com/oreilly/radar",  # Example
            # Add more news sources
        ]
        logger.info(f"News Gap Agent initialized with {len(self.news_sources)} sources")
    
    async def start(self) -> None:
        """Start news monitoring"""
        self.running = True
        logger.info("News Gap Agent started")
        
        while self.running:
            try:
                await self.scan_news()
                await asyncio.sleep(300)  # Scan every 5 minutes
            except Exception as e:
                logger.error(f"Error in news scan: {e}")
                await asyncio.sleep(300)
    
    async def stop(self) -> None:
        """Stop news agent"""
        self.running = False
        logger.info("News Gap Agent stopped")
    
    async def scan_news(self) -> None:
        """Scan news sources for relevant events"""
        for source in self.news_sources:
            try:
                feed = feedparser.parse(source)
                for entry in feed.entries[:10]:  # Last 10 entries
                    await self._process_news_item(entry)
            except Exception as e:
                logger.warning(f"Error parsing news source {source}: {e}")
    
    async def _process_news_item(self, entry: Dict) -> None:
        """Process a news item and find related markets"""
        # Extract keywords from news
        title = entry.get("title", "")
        summary = entry.get("summary", "")
        text = f"{title} {summary}".lower()
        
        # Find related markets
        markets = await self.client.get_markets(limit=200)
        
        for market in markets:
            # Simple keyword matching (could use LLM for better matching)
            if self._is_relevant(market, text):
                await self._analyze_news_gap(market, entry)
    
    def _is_relevant(self, market: Market, news_text: str) -> bool:
        """Check if market is relevant to news"""
        market_text = f"{market.question} {market.description or ''}".lower()
        
        # Extract keywords from market
        market_keywords = set(market_text.split())
        news_keywords = set(news_text.split())
        
        # Check for overlap
        overlap = market_keywords.intersection(news_keywords)
        return len(overlap) >= 3  # At least 3 common keywords
    
    async def _analyze_news_gap(self, market: Market, news_item: Dict) -> None:
        """Analyze if market is mispriced relative to news"""
        try:
            # Get current market price
            orderbook = await self.client.get_orderbook(market.id)
            if not orderbook:
                return
            
            yes_price = orderbook.get_best_yes_price()
            if not yes_price:
                return
            
            # Use LLM to determine "true" probability from news
            true_probability = await self._calculate_true_probability(market, news_item)
            
            if true_probability:
                # Calculate gap
                gap = abs(float(yes_price) - true_probability)
                
                if gap > 0.15:  # Significant gap
                    # Determine direction
                    if true_probability > float(yes_price):
                        side = OrderSide.YES
                        expected_return = gap
                    else:
                        side = OrderSide.NO
                        expected_return = gap
                    
                    score = min(gap * 3, 1.0)  # Scale to 0-1
                    
                    opportunity = Opportunity(
                        market_id=market.id,
                        market=market,
                        opportunity_type=OpportunityType.NEWS_GAP,
                        side=side,
                        score=score,
                        expected_return=expected_return,
                        risk_level="medium",
                        entry_price=yes_price if side == OrderSide.YES else (Decimal("1") - yes_price),
                        reasoning=f"News gap: Market price={yes_price:.4f}, True prob={true_probability:.4f}, Gap={gap:.4%}",
                        metadata={
                            "news_title": news_item.get("title", ""),
                            "true_probability": true_probability,
                            "market_price": str(yes_price),
                        }
                    )
                    
                    self.opportunities.append(opportunity)
                    logger.info(
                        f"News gap found: {market.id[:8]} {side.value} "
                        f"(Gap: {gap:.2%})"
                    )
        
        except Exception as e:
            logger.warning(f"Error analyzing news gap: {e}")
    
    async def _calculate_true_probability(
        self, market: Market, news_item: Dict
    ) -> Optional[float]:
        """Use LLM to calculate true probability from news"""
        prompt = f"""Given this market and news, what is the true probability the outcome will be YES?

Market: {market.question}
Description: {market.description or 'N/A'}

News:
Title: {news_item.get('title', '')}
Summary: {news_item.get('summary', '')}

Respond with ONLY a number between 0.0 and 1.0 representing the probability."""

        try:
            if settings.llm_provider == "anthropic" and settings.anthropic_api_key:
                from anthropic import Anthropic
                client = Anthropic(api_key=settings.anthropic_api_key)
                response = await asyncio.to_thread(
                    client.messages.create,
                    model=settings.llm_model,
                    max_tokens=50,
                    messages=[{"role": "user", "content": prompt}]
                )
                text = response.content[0].text.strip()
            elif settings.llm_provider == "openai" and settings.openai_api_key:
                from openai import AsyncOpenAI
                client = AsyncOpenAI(api_key=settings.openai_api_key)
                response = await client.chat.completions.create(
                    model=settings.llm_model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=50
                )
                text = response.choices[0].message.content.strip()
            else:
                return None
            
            # Extract number
            try:
                prob = float(text)
                return max(0.0, min(1.0, prob))  # Clamp to 0-1
            except ValueError:
                return None
        
        except Exception as e:
            logger.warning(f"Error calculating true probability: {e}")
            return None
    
    def get_opportunities(self, min_score: float = 0.6) -> List[Opportunity]:
        """Get news gap opportunities"""
        return [
            o for o in self.opportunities
            if o.score >= min_score
        ]

