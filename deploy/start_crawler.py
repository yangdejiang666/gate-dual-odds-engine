"""
独立抓取与识别守护进程
按第四、五、六、二十一章落地
"""

import time
import asyncio
import logging
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.app.config import settings
from backend.app.database import db
from backend.app.services.crawler.browser_manager import browser_manager
from backend.app.services.crawler.state_machine import PeriodStateMachine
from backend.app.services.collector.feature_extractor import feature_extractor
from backend.app.services.collector.cross_analyzer import cross_analyzer
from backend.app.services.engine.cascade_model import cascade_engine
from backend.app.services.accounting.decision_guard import decision_guard

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("CrawlerDaemon")

async def run_crawler_daemon():
    logger.info("启动 Gate BTC/ETH 抓取守护进程...")
    await browser_manager.initialize()

    sm_btc = PeriodStateMachine("BTC")
    sm_eth = PeriodStateMachine("ETH")

    # 注册入库与特征增量回调
    def on_tick(symbol, period_id, sec_offset, up_odds, down_odds, price):
        diff = round(down_odds - up_odds, 4)
        db.execute_write(
            """
            INSERT INTO odds_tick (period_id, symbol, sec_offset, up_odds, down_odds, odds_diff, price)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (period_id, symbol, sec_offset, up_odds, down_odds, diff, price)
        )

    sm_btc.on_tick_sample = on_tick
    sm_eth.on_tick_sample = on_tick

    # 循环常驻运行
    while True:
        await asyncio.sleep(settings.CRAWLER_SAMPLE_INTERVAL_SEC)
        # 心跳注入
        await browser_manager.send_heartbeat()

if __name__ == "__main__":
    asyncio.run(run_crawler_daemon())
