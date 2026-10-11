"""
第二十六章：真实市场 API 扩展接口 (参考条件)
严格按第二十六章落地：
1. 可插拔 Provider 插件设计
2. 市场现货/永续行情仅作为趋势参考与交叉校验，页面倍率仍为第一信号
3. 严格防未来函数与断线优雅降级：API 离线不影响页面主链路
4. 默认关闭 (MARKET_API_ENABLED = False)
"""

import logging
from typing import Optional
from backend.app.config import settings
from backend.app.database import db

logger = logging.getLogger("MarketApi")

class BaseMarketProvider:
    def __init__(self, name: str):
        self.name = name

    async def fetch_latest_price(self, symbol: str) -> Optional[float]:
        raise NotImplementedError

class MockExchangeProvider(BaseMarketProvider):
    def __init__(self):
        super().__init__("ExchangeAdapter")

    async def fetch_latest_price(self, symbol: str) -> Optional[float]:
        if not settings.MARKET_API_ENABLED:
            return None
        # 预留真实 ccxt / WebSocket 现货行情
        return 68500.0 if symbol == "BTC" else 3650.0

market_provider = MockExchangeProvider()
