"""Polymarket API client"""

import asyncio
from typing import List, Optional, Dict, Any
from decimal import Decimal
import httpx
import structlog
from datetime import datetime

from .models import Market, OrderBook, OrderBookEntry, Order, Position
from .geobypass import GeoBypass
from .config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


class PolymarketClient:
    """Client for Polymarket API with geobypass"""
    
    def __init__(self):
        self.geobypass = GeoBypass()
        self.base_url = settings.polymarket_api_url
        self.api_key = settings.polymarket_api_key
        self.private_key = settings.polymarket_private_key
        self._client: Optional[httpx.AsyncClient] = None
    
    async def initialize(self) -> None:
        """Initialize client"""
        await self.geobypass.initialize()
        self._client = await self.geobypass.get_http_client()
        logger.info("Polymarket client initialized")
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        retries: int = 3
    ) -> Dict[str, Any]:
        """Make API request with retry and geoblock handling"""
        url = f"{self.base_url}{endpoint}"
        
        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        for attempt in range(retries):
            try:
                if not self._client:
                    self._client = await self.geobypass.get_http_client()
                
                response = await self._client.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json_data,
                    headers=headers,
                    timeout=30.0
                )
                
                # Check for geoblock
                if await self.geobypass.check_geoblock(response):
                    logger.warning(f"Geoblock detected on attempt {attempt + 1}")
                    await self.geobypass.handle_geoblock()
                    self._client = await self.geobypass.get_http_client()
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    continue
                
                response.raise_for_status()
                return response.json()
            
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 403:
                    await self.geobypass.handle_geoblock()
                    self._client = await self.geobypass.get_http_client()
                    if attempt < retries - 1:
                        await asyncio.sleep(2 ** attempt)
                        continue
                logger.error(f"HTTP error: {e}")
                raise
            
            except Exception as e:
                logger.error(f"Request error: {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise
        
        raise Exception("Max retries exceeded")
    
    async def get_markets(
        self,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Market]:
        """Get markets"""
        params = {
            "limit": limit,
            "offset": offset,
        }
        if filters:
            params.update(filters)
        
        try:
            data = await self._request("GET", "/markets", params=params)
            markets = []
            for market_data in data.get("data", []):
                try:
                    market = Market(
                        id=market_data.get("id", ""),
                        question=market_data.get("question", ""),
                        description=market_data.get("description"),
                        slug=market_data.get("slug", ""),
                        end_date_iso=datetime.fromisoformat(market_data["endDateISO"]) if market_data.get("endDateISO") else None,
                        start_date_iso=datetime.fromisoformat(market_data["startDateISO"]) if market_data.get("startDateISO") else None,
                        image=market_data.get("image"),
                        icon=market_data.get("icon"),
                        tags=market_data.get("tags", []),
                        liquidity=Decimal(str(market_data.get("liquidity", 0))),
                        volume=Decimal(str(market_data.get("volume", 0))),
                        status=market_data.get("status", "open"),
                    )
                    markets.append(market)
                except Exception as e:
                    logger.warning(f"Error parsing market: {e}")
                    continue
            
            return markets
        
        except Exception as e:
            logger.error(f"Error fetching markets: {e}")
            return []
    
    async def get_market(self, market_id: str) -> Optional[Market]:
        """Get single market by ID"""
        try:
            data = await self._request("GET", f"/markets/{market_id}")
            market_data = data.get("data", {})
            return Market(
                id=market_data.get("id", ""),
                question=market_data.get("question", ""),
                description=market_data.get("description"),
                slug=market_data.get("slug", ""),
                end_date_iso=datetime.fromisoformat(market_data["endDateISO"]) if market_data.get("endDateISO") else None,
                start_date_iso=datetime.fromisoformat(market_data["startDateISO"]) if market_data.get("startDateISO") else None,
                image=market_data.get("image"),
                icon=market_data.get("icon"),
                tags=market_data.get("tags", []),
                liquidity=Decimal(str(market_data.get("liquidity", 0))),
                volume=Decimal(str(market_data.get("volume", 0))),
                status=market_data.get("status", "open"),
            )
        except Exception as e:
            logger.error(f"Error fetching market {market_id}: {e}")
            return None
    
    async def get_orderbook(self, market_id: str) -> Optional[OrderBook]:
        """Get order book for market"""
        try:
            data = await self._request("GET", f"/markets/{market_id}/orderbook")
            orderbook_data = data.get("data", {})
            
            def parse_entries(entries: List[Dict]) -> List[OrderBookEntry]:
                return [
                    OrderBookEntry(
                        price=Decimal(str(entry[0])),
                        size=Decimal(str(entry[1]))
                    )
                    for entry in entries
                ]
            
            return OrderBook(
                market_id=market_id,
                yes_bids=parse_entries(orderbook_data.get("yesBids", [])),
                yes_asks=parse_entries(orderbook_data.get("yesAsks", [])),
                no_bids=parse_entries(orderbook_data.get("noBids", [])),
                no_asks=parse_entries(orderbook_data.get("noAsks", [])),
            )
        except Exception as e:
            logger.error(f"Error fetching orderbook for {market_id}: {e}")
            return None
    
    async def place_order(self, order: Order) -> Dict[str, Any]:
        """Place order on Polymarket"""
        if settings.demo_mode:
            logger.info(f"DEMO MODE: Would place order {order.id}")
            return {"status": "demo", "order_id": order.id}
        
        try:
            order_data = {
                "marketId": order.market_id,
                "side": order.side.value,
                "type": order.order_type.value,
                "price": str(order.price),
                "size": str(order.size),
            }
            
            data = await self._request("POST", "/orders", json_data=order_data)
            return data
        except Exception as e:
            logger.error(f"Error placing order: {e}")
            raise
    
    async def get_positions(self) -> List[Position]:
        """Get current positions"""
        try:
            data = await self._request("GET", "/positions")
            positions = []
            for pos_data in data.get("data", []):
                try:
                    position = Position(
                        id=pos_data.get("id", ""),
                        market_id=pos_data.get("marketId", ""),
                        side=pos_data.get("side", "LONG"),
                        size=Decimal(str(pos_data.get("size", 0))),
                        entry_price=Decimal(str(pos_data.get("entryPrice", 0))),
                        current_price=Decimal(str(pos_data.get("currentPrice", 0))),
                    )
                    position.update_pnl(position.current_price)
                    positions.append(position)
                except Exception as e:
                    logger.warning(f"Error parsing position: {e}")
                    continue
            
            return positions
        except Exception as e:
            logger.error(f"Error fetching positions: {e}")
            return []
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel order"""
        try:
            await self._request("DELETE", f"/orders/{order_id}")
            return True
        except Exception as e:
            logger.error(f"Error cancelling order {order_id}: {e}")
            return False
    
    async def shutdown(self) -> None:
        """Shutdown client"""
        if self._client:
            await self._client.aclose()
        await self.geobypass.shutdown()
        logger.info("Polymarket client shut down")

