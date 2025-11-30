"""FastAPI server for Polymarket Agentic Terminal"""

import asyncio
import os
from contextlib import asynccontextmanager
from typing import List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import structlog

from rai_algo.polymarket.orchestrator import AgentOrchestrator
from rai_algo.polymarket.models import (
    Opportunity, StrategyBlueprint, Position, Trade, TraderProfile
)
from rai_algo.polymarket.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

# Global orchestrator instance
orchestrator: Optional[AgentOrchestrator] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown"""
    global orchestrator
    
    # Startup
    logger.info("Starting Polymarket Agentic Terminal API")
    orchestrator = AgentOrchestrator()
    await orchestrator.initialize()
    
    # Start orchestrator in background
    orchestrator_task = asyncio.create_task(orchestrator.start())
    
    yield
    
    # Shutdown
    logger.info("Shutting down Polymarket Agentic Terminal API")
    if orchestrator:
        await orchestrator.stop()
    if orchestrator_task:
        orchestrator_task.cancel()
        try:
            await orchestrator_task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="Polymarket Agentic Terminal API",
    description="API for Polymarket autonomous trading system",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
# Allow Vercel frontend and localhost for development
allowed_origins = [
    "http://localhost:3000",
    "http://localhost:3001",
]

# Add all Vercel domains (preview and production)
# Vercel uses *.vercel.app for preview deployments
# We'll use a regex pattern or allow all Vercel domains
import re
vercel_pattern = re.compile(r"https://.*\.vercel\.app$")

# Add custom Vercel domain if set
if os.getenv("VERCEL_URL"):
    allowed_origins.append(f"https://{os.getenv('VERCEL_URL')}")

# Add production domain if set
if os.getenv("FRONTEND_URL"):
    allowed_origins.append(os.getenv("FRONTEND_URL"))

# For Railway deployment, we'll allow all origins in production
# but you can restrict this to your specific Vercel domain
if os.getenv("RAILWAY_ENVIRONMENT") == "production":
    # In production, allow all Vercel domains
    # You can also set FRONTEND_URL to your specific Vercel domain
    pass

# More permissive CORS for Vercel deployments
# In production, you may want to restrict this to your specific domain
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins if allowed_origins else ["*"],  # Fallback to allow all if needed
    allow_origin_regex=r"https://.*\.vercel\.app",  # Allow all Vercel preview deployments
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# WebSocket connections
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
    
    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning(f"Error broadcasting to WebSocket: {e}")


manager = ConnectionManager()


# Subscribe to orchestrator events
if orchestrator:
    async def on_opportunity(data):
        await manager.broadcast({"type": "opportunity", "data": data})
    
    async def on_trade(data):
        await manager.broadcast({"type": "trade_executed", "data": data})
    
    async def on_strategy(data):
        await manager.broadcast({"type": "strategy_generated", "data": data})


# API Models
class StatusResponse(BaseModel):
    running: bool
    opportunities: int
    strategies: int
    positions: int
    trades: int
    statistics: dict


class OpportunityResponse(BaseModel):
    opportunities: List[dict]


class StrategyResponse(BaseModel):
    strategies: List[dict]


# API Endpoints
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "Polymarket Agentic Terminal",
        "version": "1.0.0",
        "status": "operational"
    }


@app.get("/api/polymarket/status", response_model=StatusResponse)
async def get_status():
    """Get system status"""
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")
    
    status = orchestrator.get_status()
    return StatusResponse(**status)


@app.get("/api/polymarket/opportunities", response_model=OpportunityResponse)
async def get_opportunities(
    min_score: Optional[float] = 0.7,
    limit: int = 100
):
    """Get recent opportunities"""
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")
    
    opportunities = orchestrator.scanner.get_opportunities(
        min_score=min_score,
        limit=limit
    )
    
    return OpportunityResponse(
        opportunities=[o.dict() for o in opportunities]
    )


@app.get("/api/polymarket/strategies", response_model=StrategyResponse)
async def get_strategies():
    """Get all strategies"""
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")
    
    strategies = orchestrator.strategy_generator.get_strategies()
    
    return StrategyResponse(
        strategies=[s.dict() for s in strategies]
    )


@app.get("/api/polymarket/positions")
async def get_positions():
    """Get current positions"""
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")
    
    positions = list(orchestrator.demo_trader.positions.values())
    
    return {
        "positions": [p.dict() for p in positions]
    }


@app.get("/api/polymarket/trades")
async def get_trades(limit: int = 100):
    """Get trade history"""
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")
    
    trades = orchestrator.demo_trader.trade_history[-limit:]
    
    return {
        "trades": [t.dict() for t in trades]
    }


@app.get("/api/polymarket/stats")
async def get_stats():
    """Get trading statistics"""
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")
    
    stats = orchestrator.demo_trader.get_statistics()
    risk_metrics = orchestrator.risk_manager.get_risk_metrics()
    
    return {
        "statistics": stats,
        "risk_metrics": risk_metrics
    }


@app.post("/api/polymarket/traders/track")
async def add_tracked_trader(address: str, username: Optional[str] = None):
    """Add trader address to tracking list"""
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")
    
    if hasattr(orchestrator, 'trader_tracker'):
        await orchestrator.trader_tracker.add_tracked_address(address, username)
        return {"status": "success", "address": address}
    else:
        raise HTTPException(status_code=501, detail="Trader tracking not implemented")


@app.get("/api/polymarket/traders")
async def get_traders(min_trades: int = 10, min_win_rate: float = 0.6):
    """Get tracked traders"""
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")
    
    if hasattr(orchestrator, 'trader_tracker'):
        traders = orchestrator.trader_tracker.get_top_traders(
            min_trades=min_trades,
            min_win_rate=min_win_rate
        )
        return {"traders": [t.dict() for t in traders]}
    else:
        raise HTTPException(status_code=501, detail="Trader tracking not implemented")


# WebSocket endpoint
@app.websocket("/ws/polymarket")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for real-time updates"""
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive and send periodic updates
            await asyncio.sleep(1)
            if orchestrator:
                status = orchestrator.get_status()
                await websocket.send_json({
                    "type": "status_update",
                    "data": status
                })
    except WebSocketDisconnect:
        manager.disconnect(websocket)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api_server_polymarket:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )

