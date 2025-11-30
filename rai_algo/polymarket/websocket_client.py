"""WebSocket client for real-time Polymarket data"""

import asyncio
import json
from typing import Dict, Any, Optional, Callable, List
from decimal import Decimal
from datetime import datetime
import structlog
from websockets.client import connect
from websockets.exceptions import ConnectionClosed

from .models import Market, OrderBook, OrderBookEntry
from .geobypass import GeoBypass
from .config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


class PolymarketWebSocketClient:
    """WebSocket client for real-time Polymarket data"""
    
    def __init__(self):
        self.geobypass = GeoBypass()
        self.ws_url = "wss://clob.polymarket.com/ws"
        self.websocket = None
        self.connected = False
        self.subscriptions: Dict[str, List[Callable]] = {}
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 10
        self.reconnect_delay = 5
        
    async def initialize(self) -> None:
        """Initialize WebSocket connection"""
        await self.geobypass.initialize()
        await self.connect()
    
    async def connect(self) -> None:
        """Connect to WebSocket"""
        try:
            self.websocket = await connect(
                self.ws_url,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=10
            )
            self.connected = True
            self.reconnect_attempts = 0
            logger.info("WebSocket connected to Polymarket")
            
            # Start message handler
            asyncio.create_task(self._message_handler())
            
        except Exception as e:
            logger.error(f"WebSocket connection failed: {e}")
            await self._reconnect()
    
    async def _reconnect(self) -> None:
        """Reconnect to WebSocket"""
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            logger.error("Max reconnect attempts reached")
            return
        
        self.reconnect_attempts += 1
        delay = self.reconnect_delay * self.reconnect_attempts
        logger.info(f"Reconnecting in {delay} seconds (attempt {self.reconnect_attempts})")
        
        await asyncio.sleep(delay)
        await self.connect()
    
    async def _message_handler(self) -> None:
        """Handle incoming WebSocket messages"""
        try:
            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    await self._process_message(data)
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse message: {e}")
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
        except ConnectionClosed:
            logger.warning("WebSocket connection closed")
            self.connected = False
            await self._reconnect()
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            self.connected = False
            await self._reconnect()
    
    async def _process_message(self, data: Dict[str, Any]) -> None:
        """Process incoming message and trigger callbacks"""
        msg_type = data.get("type")
        channel = data.get("channel")
        
        if channel in self.subscriptions:
            for callback in self.subscriptions[channel]:
                try:
                    await callback(data)
                except Exception as e:
                    logger.error(f"Callback error: {e}")
    
    async def subscribe_market_data(
        self,
        market_id: str,
        callback: Callable[[Dict[str, Any]], None]
    ) -> None:
        """Subscribe to market data updates"""
        channel = f"market:{market_id}"
        if channel not in self.subscriptions:
            self.subscriptions[channel] = []
        self.subscriptions[channel].append(callback)
        
        if self.connected and self.websocket:
            subscribe_msg = {
                "type": "subscribe",
                "channel": channel,
                "market": market_id
            }
            await self.websocket.send(json.dumps(subscribe_msg))
            logger.info(f"Subscribed to market data: {market_id}")
    
    async def subscribe_orderbook(
        self,
        market_id: str,
        callback: Callable[[OrderBook], None]
    ) -> None:
        """Subscribe to orderbook updates"""
        channel = f"orderbook:{market_id}"
        
        async def orderbook_callback(data: Dict[str, Any]) -> None:
            """Convert WebSocket data to OrderBook model"""
            try:
                orderbook_data = data.get("data", {})
                
                def parse_entries(entries: List[List]) -> List[OrderBookEntry]:
                    return [
                        OrderBookEntry(
                            price=Decimal(str(entry[0])),
                            size=Decimal(str(entry[1]))
                        )
                        for entry in entries
                    ]
                
                orderbook = OrderBook(
                    market_id=market_id,
                    yes_bids=parse_entries(orderbook_data.get("yesBids", [])),
                    yes_asks=parse_entries(orderbook_data.get("yesAsks", [])),
                    no_bids=parse_entries(orderbook_data.get("noBids", [])),
                    no_asks=parse_entries(orderbook_data.get("noAsks", [])),
                )
                await callback(orderbook)
            except Exception as e:
                logger.error(f"Error parsing orderbook: {e}")
        
        if channel not in self.subscriptions:
            self.subscriptions[channel] = []
        self.subscriptions[channel].append(orderbook_callback)
        
        if self.connected and self.websocket:
            subscribe_msg = {
                "type": "subscribe",
                "channel": channel,
                "market": market_id
            }
            await self.websocket.send(json.dumps(subscribe_msg))
            logger.info(f"Subscribed to orderbook: {market_id}")
    
    async def subscribe_trades(
        self,
        market_id: str,
        callback: Callable[[Dict[str, Any]], None]
    ) -> None:
        """Subscribe to trade updates"""
        channel = f"trades:{market_id}"
        if channel not in self.subscriptions:
            self.subscriptions[channel] = []
        self.subscriptions[channel].append(callback)
        
        if self.connected and self.websocket:
            subscribe_msg = {
                "type": "subscribe",
                "channel": channel,
                "market": market_id
            }
            await self.websocket.send(json.dumps(subscribe_msg))
            logger.info(f"Subscribed to trades: {market_id}")
    
    async def subscribe_positions(
        self,
        callback: Callable[[Dict[str, Any]], None]
    ) -> None:
        """Subscribe to position updates"""
        channel = "positions"
        if channel not in self.subscriptions:
            self.subscriptions[channel] = []
        self.subscriptions[channel].append(callback)
        
        if self.connected and self.websocket:
            subscribe_msg = {
                "type": "subscribe",
                "channel": channel
            }
            await self.websocket.send(json.dumps(subscribe_msg))
            logger.info("Subscribed to positions")
    
    async def unsubscribe(self, channel: str) -> None:
        """Unsubscribe from a channel"""
        if channel in self.subscriptions:
            del self.subscriptions[channel]
        
        if self.connected and self.websocket:
            unsubscribe_msg = {
                "type": "unsubscribe",
                "channel": channel
            }
            await self.websocket.send(json.dumps(unsubscribe_msg))
            logger.info(f"Unsubscribed from: {channel}")
    
    async def close(self) -> None:
        """Close WebSocket connection"""
        if self.websocket:
            await self.websocket.close()
        self.connected = False
        self.subscriptions.clear()
        logger.info("WebSocket connection closed")
    
    async def shutdown(self) -> None:
        """Shutdown WebSocket client"""
        await self.close()
        await self.geobypass.shutdown()

