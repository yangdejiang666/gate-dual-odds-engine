"""
协同计算引擎与实盘数据摄入测试 (test_coordinator_and_ingest.py)
验证：
1. 真实数据包（包含 MM:SS 倒计时、看涨/看跌份额价、买方配比 B %、价差超额）经协调器处理
2. odds_tick 落库与双品种特征计算
3. 状态机跨局切换与 period_result 自动落地
4. 信号生成与事后核算闭环
"""

import sys
from pathlib import Path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.app.database import db
from backend.app.services.engine.coordinator import engine_coordinator
from backend.app.models.schemas import ActionEnum

def test_realtime_coordinator_tick_pipeline():
    # 模拟真实 Gate 盘面 BTC 数据包
    payload_btc = {
        "symbol": "BTC",
        "period_id": "P_TEST_001_BTC",
        "countdown_str": "02:15", # 135s -> sec_offset = 165 (进入 T_work 决策窗口)
        "target_price": 83008.45,
        "current_price": 83025.10,
        "price_diff": 16.65,
        "call_price": 0.98,
        "put_price": 0.03,
        "b_ratio": "B 68.27%"
    }

    payload_eth = {
        "symbol": "ETH",
        "period_id": "P_TEST_001_ETH",
        "countdown_str": "02:15",
        "target_price": 2502.24,
        "current_price": 2503.10,
        "price_diff": 0.86,
        "call_price": 0.85,
        "put_price": 0.15,
        "b_ratio": "B 62.10%"
    }

    # 执行摄入
    res_btc = engine_coordinator.process_tick(payload_btc)
    res_eth = engine_coordinator.process_tick(payload_eth)

    # 验证下发字段与结构完整性
    assert res_btc["symbol"] == "BTC"
    assert res_btc["remaining_sec"] == 135
    assert res_btc["sec_offset"] == 165
    assert res_btc["timing_window"] == "T_WORK"
    assert "signal" in res_btc
    assert "btc" in res_btc
    assert "eth" in res_btc
    assert res_btc["btc"]["call_price"] == 0.98

    # 验证 odds_tick 表中有记录
    ticks = db.execute_read("SELECT * FROM odds_tick WHERE period_id = ? AND symbol = ?", ("P_TEST_001_BTC", "BTC"))
    assert len(ticks) >= 1
    assert ticks[-1]["call_price"] == 0.98
    print("test_realtime_coordinator_tick_pipeline passed!")

def test_period_settlement_and_accounting():
    # 模拟对局结束 (切换新期号触发结算)
    payload_new_period = {
        "symbol": "BTC",
        "period_id": "P_TEST_002_BTC", # 期号变化，驱动上一局 P_TEST_001_BTC 自动进入 RESULT 并结算
        "countdown_str": "04:59",
        "target_price": 83030.00,
        "current_price": 83030.00,
        "price_diff": 0.0,
        "call_price": 0.50,
        "put_price": 0.50,
        "b_ratio": "B 50.00%"
    }

    engine_coordinator.process_tick(payload_new_period)

    # 验证上一局是否已落地 period_result 表
    results = db.execute_read("SELECT * FROM period_result WHERE period_id = ?", ("P_TEST_001_BTC",))
    assert len(results) >= 1
    assert results[0]["direction"] in ["UP", "DOWN"]
    print("test_period_settlement_and_accounting passed!")

if __name__ == "__main__":
    test_realtime_coordinator_tick_pipeline()
    test_period_settlement_and_accounting()
