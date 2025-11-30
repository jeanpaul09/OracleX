"""Strategy Generator Agent - Autonomously creates trading strategies"""

import asyncio
import json
from typing import List, Optional, Dict, Any
from datetime import datetime
import structlog

from .models import StrategyBlueprint, StrategyType, Market, Opportunity
from .client import PolymarketClient
from .demo_trader import DemoTrader
from .config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


class StrategyGeneratorAgent:
    """Autonomously generates and tests trading strategies"""
    
    def __init__(self, client: PolymarketClient, demo_trader: DemoTrader):
        self.client = client
        self.demo_trader = demo_trader
        self.strategies: Dict[str, StrategyBlueprint] = {}
        self.running = False
    
    async def generate_strategy(
        self,
        strategy_type: StrategyType,
        market_data: Optional[List[Market]] = None,
        opportunities: Optional[List[Opportunity]] = None
    ) -> Optional[StrategyBlueprint]:
        """Generate a new strategy using LLM reasoning"""
        logger.info(f"Generating {strategy_type.value} strategy")
        
        # Build context for LLM
        context = self._build_context(strategy_type, market_data, opportunities)
        
        # Generate strategy using LLM
        strategy_json = await self._llm_generate_strategy(strategy_type, context)
        
        if not strategy_json:
            return None
        
        try:
            # Parse strategy blueprint
            strategy = StrategyBlueprint(**strategy_json)
            strategy.strategy_type = strategy_type
            
            # Test strategy
            test_results = await self._test_strategy(strategy)
            strategy.test_results = test_results
            
            # Only keep strategies that meet minimum criteria
            if self._meets_criteria(strategy):
                self.strategies[strategy.name] = strategy
                logger.info(
                    f"Strategy generated: {strategy.name} "
                    f"(Win Rate: {test_results.get('win_rate', 0):.2%}, "
                    f"ROI: {test_results.get('total_return', 0):.2%})"
                )
                return strategy
            else:
                logger.info(f"Strategy {strategy.name} did not meet criteria")
                return None
        
        except Exception as e:
            logger.error(f"Error generating strategy: {e}")
            return None
    
    def _build_context(
        self,
        strategy_type: StrategyType,
        market_data: Optional[List[Market]],
        opportunities: Optional[List[Opportunity]]
    ) -> str:
        """Build context string for LLM"""
        context_parts = [
            f"Strategy Type: {strategy_type.value}",
            f"Current Settings:",
            f"  - Max Position Size: {settings.max_position_size}",
            f"  - Stop Loss: {settings.stop_loss_pct}",
            f"  - Take Profit: {settings.take_profit_pct}",
        ]
        
        if market_data:
            context_parts.append(f"\nMarket Data: {len(market_data)} markets analyzed")
            # Add sample market info
            for market in market_data[:5]:
                context_parts.append(
                    f"  - {market.question[:50]}: "
                    f"Liquidity={market.liquidity}, Volume={market.volume}"
                )
        
        if opportunities:
            context_parts.append(f"\nOpportunities: {len(opportunities)} found")
            for opp in opportunities[:5]:
                context_parts.append(
                    f"  - {opp.opportunity_type.value}: "
                    f"Score={opp.score:.2f}, Expected Return={opp.expected_return:.2%}"
                )
        
        return "\n".join(context_parts)
    
    async def _llm_generate_strategy(
        self, strategy_type: StrategyType, context: str
    ) -> Optional[Dict[str, Any]]:
        """Use LLM to generate strategy blueprint"""
        prompt = f"""You are an expert trading strategy developer for prediction markets (Polymarket).

Create a trading strategy blueprint in JSON format based on the following:

Strategy Type: {strategy_type.value}
Context:
{context}

Generate a strategy that:
1. Has clear entry and exit rules
2. Includes risk management parameters
3. Is specific and actionable
4. Has a descriptive name and explanation

Return ONLY valid JSON in this exact format:
{{
  "name": "strategy_name",
  "description": "Strategy description",
  "parameters": {{"param1": value1}},
  "entry_rules": {{
    "YES": ["condition1", "condition2"],
    "NO": ["condition1"]
  }},
  "exit_rules": {{
    "YES": ["exit_condition"],
    "NO": ["exit_condition"]
  }},
  "risk_management": {{
    "stop_loss_pct": 0.1,
    "take_profit_pct": 0.2,
    "max_position_size": 0.2,
    "max_drawdown": 0.2
  }}
}}

Be creative but realistic. Focus on {strategy_type.value} strategies."""

        try:
            if settings.llm_provider == "anthropic" and settings.anthropic_api_key:
                from anthropic import Anthropic
                client = Anthropic(api_key=settings.anthropic_api_key)
                response = await asyncio.to_thread(
                    client.messages.create,
                    model=settings.llm_model,
                    max_tokens=2000,
                    messages=[{"role": "user", "content": prompt}]
                )
                content = response.content[0].text
            elif settings.llm_provider == "openai" and settings.openai_api_key:
                from openai import AsyncOpenAI
                client = AsyncOpenAI(api_key=settings.openai_api_key)
                response = await client.chat.completions.create(
                    model=settings.llm_model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=2000
                )
                content = response.choices[0].message.content
            else:
                logger.warning("No LLM provider configured, using default strategy")
                return self._default_strategy(strategy_type)
            
            # Extract JSON from response
            json_str = self._extract_json(content)
            return json.loads(json_str)
        
        except Exception as e:
            logger.error(f"Error calling LLM: {e}")
            return self._default_strategy(strategy_type)
    
    def _extract_json(self, text: str) -> str:
        """Extract JSON from LLM response"""
        # Try to find JSON block
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return text[start:end]
        return text
    
    def _default_strategy(self, strategy_type: StrategyType) -> Dict[str, Any]:
        """Generate default strategy if LLM fails"""
        return {
            "name": f"default_{strategy_type.value}_strategy",
            "description": f"Default {strategy_type.value} strategy",
            "parameters": {},
            "entry_rules": {
                "YES": ["score > 0.7", "liquidity > 1000"],
                "NO": ["score > 0.7", "liquidity > 1000"]
            },
            "exit_rules": {
                "YES": ["take_profit OR stop_loss"],
                "NO": ["take_profit OR stop_loss"]
            },
            "risk_management": {
                "stop_loss_pct": settings.stop_loss_pct,
                "take_profit_pct": settings.take_profit_pct,
                "max_position_size": settings.max_position_size,
                "max_drawdown": settings.max_drawdown
            }
        }
    
    async def _test_strategy(
        self, strategy: StrategyBlueprint
    ) -> Dict[str, float]:
        """Test strategy on historical/demo data"""
        # In a real implementation, this would backtest on historical data
        # For now, simulate test results
        
        # Simulate backtesting
        await asyncio.sleep(1)  # Simulate computation
        
        # Return simulated results
        # In production, this would run actual backtests
        return {
            "win_rate": 0.60 + (hash(strategy.name) % 20) / 100,  # 0.60-0.80
            "total_return": 0.10 + (hash(strategy.name) % 15) / 100,  # 0.10-0.25
            "sharpe_ratio": 1.2 + (hash(strategy.name) % 10) / 10,  # 1.2-2.2
            "max_drawdown": 0.08 + (hash(strategy.name) % 10) / 100,  # 0.08-0.18
            "total_trades": 50 + (hash(strategy.name) % 50),  # 50-100
        }
    
    def _meets_criteria(self, strategy: StrategyBlueprint) -> bool:
        """Check if strategy meets minimum criteria"""
        if not strategy.test_results:
            return False
        
        results = strategy.test_results
        return (
            results.get("win_rate", 0) >= settings.min_win_rate and
            results.get("total_return", 0) > 0.05 and  # At least 5% return
            results.get("max_drawdown", 1.0) < settings.max_drawdown
        )
    
    def get_strategies(
        self,
        strategy_type: Optional[StrategyType] = None,
        min_win_rate: Optional[float] = None
    ) -> List[StrategyBlueprint]:
        """Get filtered strategies"""
        strategies = list(self.strategies.values())
        
        if strategy_type:
            strategies = [s for s in strategies if s.strategy_type == strategy_type]
        
        if min_win_rate and strategies:
            strategies = [
                s for s in strategies
                if s.test_results and s.test_results.get("win_rate", 0) >= min_win_rate
            ]
        
        # Sort by performance
        strategies.sort(
            key=lambda s: s.test_results.get("total_return", 0) if s.test_results else 0,
            reverse=True
        )
        
        return strategies
    
    def get_strategy(self, name: str) -> Optional[StrategyBlueprint]:
        """Get strategy by name"""
        return self.strategies.get(name)

