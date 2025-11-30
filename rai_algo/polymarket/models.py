"""Data models for Polymarket trading system"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class MarketStatus(str, Enum):
    """Market status types"""
    OPEN = "open"
    CLOSED = "closed"
    RESOLVED = "resolved"


class OrderSide(str, Enum):
    """Order side types"""
    YES = "YES"
    NO = "NO"


class OrderType(str, Enum):
    """Order type"""
    LIMIT = "LIMIT"
    MARKET = "MARKET"


class PositionSide(str, Enum):
    """Position side"""
    LONG = "LONG"
    SHORT = "SHORT"


class OpportunityType(str, Enum):
    """Types of trading opportunities"""
    ARBITRAGE = "arbitrage"
    NEWS_GAP = "news_gap"
    PROBABILITY_EDGE = "probability_edge"
    TIME_DECAY = "time_decay"
    LIQUIDITY = "liquidity"
    TRADER_SIGNAL = "trader_signal"
    SOCIAL_SENTIMENT = "social_sentiment"
    BREAKING_NEWS = "breaking_news"


class StrategyType(str, Enum):
    """Strategy types"""
    ARBITRAGE = "arbitrage"
    NEWS_DRIVEN = "news_driven"
    PROBABILITY_EDGE = "probability_edge"
    TIME_DECAY = "time_decay"
    LIQUIDITY = "liquidity"
    TRADER_FOLLOWING = "trader_following"
    SOCIAL_SENTIMENT = "social_sentiment"


# Market Data Models
class Market(BaseModel):
    """Polymarket market data"""
    id: str
    question: str
    description: Optional[str] = None
    slug: str
    end_date_iso: Optional[datetime] = None
    start_date_iso: Optional[datetime] = None
    image: Optional[str] = None
    icon: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    liquidity: Decimal = Decimal("0")
    volume: Decimal = Decimal("0")
    status: MarketStatus = MarketStatus.OPEN
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        json_encoders = {
            Decimal: str,
            datetime: lambda v: v.isoformat() if v else None,
        }


class OrderBookEntry(BaseModel):
    """Order book entry"""
    price: Decimal
    size: Decimal
    
    class Config:
        json_encoders = {Decimal: str}


class OrderBook(BaseModel):
    """Market order book"""
    market_id: str
    yes_bids: List[OrderBookEntry] = Field(default_factory=list)
    yes_asks: List[OrderBookEntry] = Field(default_factory=list)
    no_bids: List[OrderBookEntry] = Field(default_factory=list)
    no_asks: List[OrderBookEntry] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    def get_best_yes_price(self) -> Optional[Decimal]:
        """Get best YES price (highest bid)"""
        if self.yes_bids:
            return max(bid.price for bid in self.yes_bids)
        return None
    
    def get_best_no_price(self) -> Optional[Decimal]:
        """Get best NO price (highest bid)"""
        if self.no_bids:
            return max(bid.price for bid in self.no_bids)
        return None
    
    def get_arbitrage_opportunity(self) -> Optional[Decimal]:
        """Calculate arbitrage opportunity (YES + NO should sum to ~1.0)"""
        yes_price = self.get_best_yes_price()
        no_price = self.get_best_no_price()
        if yes_price and no_price:
            total = yes_price + no_price
            if total < Decimal("0.98"):  # Arbitrage opportunity
                return Decimal("1.0") - total
        return None
    
    class Config:
        json_encoders = {Decimal: str, datetime: lambda v: v.isoformat()}


# Opportunity Models
class Opportunity(BaseModel):
    """Trading opportunity"""
    id: str = Field(default_factory=lambda: f"opp_{datetime.utcnow().timestamp()}")
    market_id: str
    market: Optional[Market] = None
    opportunity_type: OpportunityType
    side: OrderSide
    score: float = Field(ge=0.0, le=1.0)  # Confidence score 0-1
    expected_return: float = Field(default=0.0)
    risk_level: str = "medium"  # low, medium, high
    entry_price: Decimal
    target_price: Optional[Decimal] = None
    stop_loss: Optional[Decimal] = None
    reasoning: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)
    detected_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    
    class Config:
        json_encoders = {Decimal: str, datetime: lambda v: v.isoformat()}


# Strategy Models
class StrategyBlueprint(BaseModel):
    """Strategy blueprint for autonomous generation"""
    name: str
    description: str
    strategy_type: StrategyType
    parameters: Dict[str, Any] = Field(default_factory=dict)
    entry_rules: Dict[str, List[str]] = Field(default_factory=dict)
    exit_rules: Dict[str, List[str]] = Field(default_factory=dict)
    risk_management: Dict[str, float] = Field(default_factory=dict)
    test_results: Optional[Dict[str, float]] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


# Trading Models
class Order(BaseModel):
    """Trading order"""
    id: Optional[str] = None
    market_id: str
    side: OrderSide
    order_type: OrderType = OrderType.LIMIT
    price: Decimal
    size: Decimal
    filled_size: Decimal = Decimal("0")
    status: str = "pending"  # pending, filled, cancelled, partial
    created_at: datetime = Field(default_factory=datetime.utcnow)
    filled_at: Optional[datetime] = None
    
    class Config:
        json_encoders = {Decimal: str, datetime: lambda v: v.isoformat()}


class Position(BaseModel):
    """Trading position"""
    id: str
    market_id: str
    market: Optional[Market] = None
    side: PositionSide
    size: Decimal
    entry_price: Decimal
    current_price: Decimal
    strategy_id: Optional[str] = None
    strategy_name: Optional[str] = None
    unrealized_pnl: Decimal = Decimal("0")
    realized_pnl: Decimal = Decimal("0")
    stop_loss: Optional[Decimal] = None
    take_profit: Optional[Decimal] = None
    opened_at: datetime = Field(default_factory=datetime.utcnow)
    closed_at: Optional[datetime] = None
    
    def update_pnl(self, current_price: Decimal) -> None:
        """Update unrealized PnL"""
        self.current_price = current_price
        if self.side == PositionSide.LONG:
            self.unrealized_pnl = (current_price - self.entry_price) * self.size
        else:  # SHORT
            self.unrealized_pnl = (self.entry_price - current_price) * self.size
    
    class Config:
        json_encoders = {Decimal: str, datetime: lambda v: v.isoformat()}


class Trade(BaseModel):
    """Executed trade"""
    id: str
    market_id: str
    side: OrderSide
    price: Decimal
    size: Decimal
    strategy_id: Optional[str] = None
    pnl: Decimal = Decimal("0")
    executed_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_encoders = {Decimal: str, datetime: lambda v: v.isoformat()}


# Trader Tracking Models
class TraderProfile(BaseModel):
    """Profile of a tracked trader/insider"""
    address: str
    username: Optional[str] = None
    total_trades: int = 0
    win_rate: float = 0.0
    total_pnl: Decimal = Decimal("0")
    avg_position_size: Decimal = Decimal("0")
    preferred_markets: List[str] = Field(default_factory=list)
    risk_score: float = 0.0  # 0-1, how risky their trades are
    reliability_score: float = 0.0  # 0-1, how reliable their signals are
    last_seen: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_encoders = {Decimal: str, datetime: lambda v: v.isoformat()}


class TraderSignal(BaseModel):
    """Signal from a tracked trader"""
    trader_address: str
    market_id: str
    side: OrderSide
    size: Decimal
    price: Decimal
    timestamp: datetime
    confidence: float = Field(ge=0.0, le=1.0)
    
    class Config:
        json_encoders = {Decimal: str, datetime: lambda v: v.isoformat()}


# Social Media Models
class SentimentType(str, Enum):
    """Sentiment classification"""
    VERY_BULLISH = "very_bullish"
    BULLISH = "bullish"
    NEUTRAL = "neutral"
    BEARISH = "bearish"
    VERY_BEARISH = "very_bearish"


class SocialPlatform(str, Enum):
    """Social media platforms"""
    TWITTER = "twitter"
    X = "x"
    REDDIT = "reddit"
    DISCORD = "discord"
    TELEGRAM = "telegram"


class Tweet(BaseModel):
    """Twitter/X tweet data"""
    id: str
    text: str
    author_id: str
    author_username: str
    author_name: Optional[str] = None
    author_followers: int = 0
    author_verified: bool = False
    created_at: datetime
    retweet_count: int = 0
    like_count: int = 0
    reply_count: int = 0
    quote_count: int = 0
    url: Optional[str] = None
    in_reply_to_tweet_id: Optional[str] = None
    referenced_tweets: List[Dict[str, Any]] = Field(default_factory=list)
    hashtags: List[str] = Field(default_factory=list)
    mentions: List[str] = Field(default_factory=list)
    urls: List[str] = Field(default_factory=list)
    media_urls: List[str] = Field(default_factory=list)
    lang: Optional[str] = None
    
    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class SentimentAnalysis(BaseModel):
    """Sentiment analysis result"""
    sentiment: SentimentType
    score: float = Field(ge=-1.0, le=1.0)  # -1 (very bearish) to 1 (very bullish)
    confidence: float = Field(ge=0.0, le=1.0)
    positive_score: float = 0.0
    negative_score: float = 0.0
    neutral_score: float = 0.0
    key_phrases: List[str] = Field(default_factory=list)
    entities: List[Dict[str, Any]] = Field(default_factory=list)
    
    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class SocialSignal(BaseModel):
    """Social media signal for trading"""
    id: str = Field(default_factory=lambda: f"signal_{datetime.utcnow().timestamp()}")
    platform: SocialPlatform
    source_id: str  # Tweet ID, post ID, etc.
    source_url: Optional[str] = None
    content: str
    author_id: str
    author_username: str
    author_influence_score: float = 0.0  # 0-1 based on followers, engagement, etc.
    created_at: datetime
    sentiment: SentimentAnalysis
    market_ids: List[str] = Field(default_factory=list)  # Linked markets
    keywords: List[str] = Field(default_factory=list)
    relevance_score: float = Field(ge=0.0, le=1.0)  # How relevant to Polymarket
    engagement_score: float = 0.0  # Likes, retweets, etc. normalized
    is_breaking_news: bool = False
    is_market_announcement: bool = False
    is_influencer_signal: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class SocialMediaAccount(BaseModel):
    """Tracked social media account"""
    platform: SocialPlatform
    account_id: str
    username: str
    name: Optional[str] = None
    followers: int = 0
    following: int = 0
    verified: bool = False
    influence_score: float = 0.0
    reliability_score: float = 0.0  # How reliable their signals are
    preferred_topics: List[str] = Field(default_factory=list)
    is_tracked: bool = True
    last_activity: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}

