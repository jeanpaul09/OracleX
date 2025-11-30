"""Georestriction bypass system for Polymarket"""

import asyncio
import random
import time
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import httpx
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
import structlog

from .config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


class ProxyManager:
    """Manages proxy rotation and health checks"""
    
    def __init__(self):
        self.proxies: List[Dict[str, str]] = []
        self.current_proxy_index = 0
        self.proxy_health: Dict[str, Dict[str, Any]] = {}
        self.last_health_check: Dict[str, datetime] = {}
        self.health_check_interval = timedelta(minutes=5)
    
    async def initialize(self) -> None:
        """Initialize proxy pool"""
        if not settings.proxy_provider:
            logger.warning("No proxy provider configured, using direct connection")
            return
        
        # Load proxies from provider
        await self._load_proxies()
        logger.info(f"Initialized {len(self.proxies)} proxies")
    
    async def _load_proxies(self) -> None:
        """Load proxies from configured provider"""
        # This would integrate with actual proxy providers
        # For now, placeholder structure
        if settings.proxy_provider == "smartproxy":
            # SmartProxy API integration would go here
            pass
        elif settings.proxy_provider == "brightdata":
            # BrightData API integration would go here
            pass
    
    async def get_proxy(self) -> Optional[Dict[str, str]]:
        """Get next healthy proxy"""
        if not self.proxies:
            return None
        
        # Rotate to next proxy
        self.current_proxy_index = (self.current_proxy_index + 1) % len(self.proxies)
        proxy = self.proxies[self.current_proxy_index]
        
        # Check health if needed
        proxy_key = f"{proxy.get('host')}:{proxy.get('port')}"
        if await self._needs_health_check(proxy_key):
            is_healthy = await self._check_proxy_health(proxy)
            if not is_healthy:
                # Try next proxy
                return await self.get_proxy()
        
        return proxy
    
    async def _needs_health_check(self, proxy_key: str) -> bool:
        """Check if proxy needs health check"""
        last_check = self.last_health_check.get(proxy_key)
        if not last_check:
            return True
        return datetime.utcnow() - last_check > self.health_check_interval
    
    async def _check_proxy_health(self, proxy: Dict[str, str]) -> bool:
        """Check if proxy is healthy"""
        proxy_key = f"{proxy.get('host')}:{proxy.get('port')}"
        try:
            async with httpx.AsyncClient(
                proxies=f"http://{proxy.get('host')}:{proxy.get('port')}",
                timeout=10.0
            ) as client:
                response = await client.get("https://api.ipify.org?format=json", timeout=5.0)
                if response.status_code == 200:
                    self.proxy_health[proxy_key] = {
                        "healthy": True,
                        "last_check": datetime.utcnow(),
                        "ip": response.json().get("ip")
                    }
                    self.last_health_check[proxy_key] = datetime.utcnow()
                    return True
        except Exception as e:
            logger.warning(f"Proxy health check failed: {e}")
        
        self.proxy_health[proxy_key] = {
            "healthy": False,
            "last_check": datetime.utcnow()
        }
        self.last_health_check[proxy_key] = datetime.utcnow()
        return False
    
    async def mark_proxy_unhealthy(self, proxy: Dict[str, str]) -> None:
        """Mark proxy as unhealthy"""
        proxy_key = f"{proxy.get('host')}:{proxy.get('port')}"
        self.proxy_health[proxy_key] = {
            "healthy": False,
            "last_check": datetime.utcnow()
        }
        logger.warning(f"Marked proxy {proxy_key} as unhealthy")


class VPNManager:
    """Manages VPN connections"""
    
    def __init__(self):
        self.connected = False
        self.current_server: Optional[str] = None
    
    async def connect(self, country: Optional[str] = None) -> bool:
        """Connect to VPN"""
        if not settings.vpn_provider:
            return False
        
        # VPN API integration would go here
        # For now, placeholder
        self.connected = True
        logger.info(f"Connected to VPN: {country or 'auto'}")
        return True
    
    async def disconnect(self) -> None:
        """Disconnect from VPN"""
        self.connected = False
        self.current_server = None
        logger.info("Disconnected from VPN")
    
    async def rotate_server(self) -> bool:
        """Rotate to different VPN server"""
        await self.disconnect()
        return await self.connect()


class StealthBrowser:
    """Browser with anti-detection features"""
    
    def __init__(self, proxy_manager: ProxyManager):
        self.proxy_manager = proxy_manager
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.playwright = None
    
    async def initialize(self) -> None:
        """Initialize browser"""
        self.playwright = await async_playwright().start()
        
        proxy = await self.proxy_manager.get_proxy()
        browser_args = [
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
            "--no-sandbox",
            "--disable-setuid-sandbox",
        ]
        
        proxy_config = None
        if proxy:
            proxy_config = {
                "server": f"http://{proxy.get('host')}:{proxy.get('port')}",
                "username": proxy.get("username"),
                "password": proxy.get("password"),
            }
        
        self.browser = await self.playwright.chromium.launch(
            headless=True,
            args=browser_args,
            proxy=proxy_config
        )
        
        # Create context with randomized fingerprint
        self.context = await self.browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=self._random_user_agent(),
            locale="en-US",
            timezone_id="America/New_York",
        )
        
        # Add stealth scripts
        self.page = await self.context.new_page()
        await self._inject_stealth_scripts()
        
        logger.info("Stealth browser initialized")
    
    def _random_user_agent(self) -> str:
        """Generate random user agent"""
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        ]
        return random.choice(user_agents)
    
    async def _inject_stealth_scripts(self) -> None:
        """Inject anti-detection scripts"""
        if not self.page:
            return
        
        # Remove webdriver property
        await self.page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)
        
        # Override permissions
        await self.page.add_init_script("""
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
        """)
    
    async def navigate(self, url: str) -> None:
        """Navigate to URL"""
        if not self.page:
            await self.initialize()
        
        if self.page:
            await self.page.goto(url, wait_until="networkidle")
    
    async def close(self) -> None:
        """Close browser"""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        logger.info("Stealth browser closed")
    
    async def rotate_proxy(self) -> None:
        """Rotate to new proxy"""
        await self.close()
        await self.initialize()


class GeoBypass:
    """Main geobypass coordinator"""
    
    def __init__(self):
        self.proxy_manager = ProxyManager()
        self.vpn_manager = VPNManager()
        self.stealth_browser = StealthBrowser(self.proxy_manager)
        self.enabled = True
    
    async def initialize(self) -> None:
        """Initialize geobypass system"""
        await self.proxy_manager.initialize()
        if settings.vpn_provider:
            await self.vpn_manager.connect()
        await self.stealth_browser.initialize()
        logger.info("Geobypass system initialized")
    
    async def get_http_client(self) -> httpx.AsyncClient:
        """Get HTTP client with proxy"""
        proxy = await self.proxy_manager.get_proxy()
        proxies = None
        if proxy:
            proxies = f"http://{proxy.get('username')}:{proxy.get('password')}@{proxy.get('host')}:{proxy.get('port')}"
        
        return httpx.AsyncClient(
            proxies=proxies,
            timeout=30.0,
            follow_redirects=True
        )
    
    async def check_geoblock(self, response: httpx.Response) -> bool:
        """Check if response indicates geoblock"""
        if response.status_code == 403:
            return True
        if "georestricted" in response.text.lower() or "not available" in response.text.lower():
            return True
        return False
    
    async def handle_geoblock(self) -> None:
        """Handle detected geoblock"""
        logger.warning("Geoblock detected, rotating proxy")
        await self.proxy_manager.mark_proxy_unhealthy(
            await self.proxy_manager.get_proxy() or {}
        )
        await self.stealth_browser.rotate_proxy()
        if settings.vpn_provider:
            await self.vpn_manager.rotate_server()
    
    async def shutdown(self) -> None:
        """Shutdown geobypass system"""
        await self.stealth_browser.close()
        await self.vpn_manager.disconnect()
        logger.info("Geobypass system shut down")

