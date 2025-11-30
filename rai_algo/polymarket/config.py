"""Configuration management for Polymarket system"""

import os
from typing import Optional, List
from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings"""
    
    # Polymarket API
    polymarket_api_url: str = "https://clob.polymarket.com"
    polymarket_api_key: Optional[str] = None
    polymarket_private_key: Optional[str] = None
    
    # Proxy Configuration
    proxy_provider: Optional[str] = None
    proxy_api_key: Optional[str] = None
    proxy_username: Optional[str] = None
    proxy_password: Optional[str] = None
    
    # VPN Configuration
    vpn_provider: Optional[str] = None
    vpn_api_key: Optional[str] = None
    
    # Database
    database_url: str = "postgresql+asyncpg://user:password@localhost:5432/polymarket"
    redis_url: str = "redis://localhost:6379/0"
    
    # LLM Configuration
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    llm_provider: str = "anthropic"
    llm_model: str = "claude-3-5-sonnet-20241022"
    
    # Trading Configuration
    demo_mode: bool = True
    initial_capital: float = 10000.0
    max_position_size: float = 0.2
    max_drawdown: float = 0.2
    min_win_rate: float = 0.55
    
    # Risk Management
    stop_loss_pct: float = 0.1
    take_profit_pct: float = 0.2
    max_portfolio_risk: float = 0.3
    
    # Agent Configuration
    scan_interval_seconds: int = 30
    opportunity_score_threshold: float = 0.7
    max_concurrent_positions: int = 10
    
    # Social Media / X (Twitter) Configuration
    twitter_bearer_token: Optional[str] = None
    twitter_api_key: Optional[str] = None
    twitter_api_secret: Optional[str] = None
    twitter_access_token: Optional[str] = None
    twitter_access_token_secret: Optional[str] = None
    twitter_client_id: Optional[str] = None
    twitter_client_secret: Optional[str] = None
    social_scan_interval_seconds: int = 60
    social_sentiment_threshold: float = 0.6
    tracked_accounts: List[str] = Field(default_factory=lambda: [
        "Polymarket",
        "polymarket",
        "PolymarketHQ"
    ])
    tracked_keywords: List[str] = Field(default_factory=lambda: [
        "polymarket",
        "prediction market",
        "forecast market",
        "betting market"
    ])
    max_tweets_per_scan: int = 100
    enable_sentiment_analysis: bool = True
    enable_market_linking: bool = True
    
    # Logging
    log_level: str = "INFO"
    log_file: str = "logs/polymarket.log"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()

