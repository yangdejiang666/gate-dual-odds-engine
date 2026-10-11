"""
离线对局仿真发生器 (mock_simulator.py)
用于本地快速冷启动、单机验证与单元回测：
模拟生成 200 局真实 Gate BTC/ETH 5分钟对局，包含秒级倍率差演化、形态、异常行情与结算结果
"""

import time
import random
from datetime import datetime, timedelta
from backend.app.database import db
from backend.app.services.storage.downsampling import downsample_odds_ticks
from backend.app.services.accounting.reputation_engine import reputation_engine

def seed_simulation_data(period_count: int = 150):
    print(f"正在生成 {period_count} 局仿真高保真 Gate 对局数据以完成冷启动...")
    
    # 预设规则
    rules = [
        ("RULE_BTC_TAIL_SURGE", "BTC尾盘资金抢筹看涨", "BTC", '{"tail_jump": -0.25}', 0.825, 0.85, 88.0),
        ("RULE_ETH_LAG_FOLLOW", "ETH滞后联动跟随", "ETH", '{"cross_lead_secs": -4}', 0.808, 0.82, 84.5),
        ("RULE_BTC_REVERSAL_EX", "BTC中期深度反转确认", "BTC", '{"reversal_count": 2}', 0.795, 0.80, 78.2),
        ("RULE_CO_DIR_HIGH_AMP", "双标的同向大振幅共振", "BTC", '{"amplitude_pct": 0.18}', 0.842, 0.88, 91.0)
    ]
    for rid, name, sym, cond, wr, conf, score in rules:
        db.execute_write(
            """
            INSERT OR REPLACE INTO rule_registry (rule_id, name, symbol, condition_json, sample_count, win_rate, confidence, reputation_score, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE')
            """,
            (rid, name, sym, cond, 320, wr, conf, score)
        )

    base_time = datetime.utcnow() - timedelta(minutes=period_count * 5)
    btc_price = 68000.0
    eth_price = 3600.0

    for i in range(period_count):
        p_time = base_time + timedelta(minutes=i * 5)
        p_close_time = p_time + timedelta(minutes=5)
        period_id = f"P_{p_time.strftime('%Y%m%d%H%M')}"

        for sym in ["BTC", "ETH"]:
            open_p = btc_price if sym == "BTC" else eth_price
            trend = random.choice([1, -1])
            is_anomaly = 1 if (i % 25 == 0) else 0 # 偶发异常局

            amp = random.uniform(0.04, 0.25)
            close_p = open_p * (1.0 + trend * (amp / 100))
            direction = "UP" if close_p >= open_p else "DOWN"

            final_up = round(1.95 - (trend * 0.15), 2)
            final_down = round(1.95 + (trend * 0.15), 2)

            db.execute_write(
                """
                INSERT OR REPLACE INTO period_result (
                    period_id, symbol, open_time, close_time, open_price, close_price,
                    direction, amplitude_pct, final_up_odds, final_down_odds, is_anomaly
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"{period_id}_{sym}", sym, p_time.isoformat(), p_close_time.isoformat(),
                    round(open_p, 2), round(close_p, 2), direction, round(amp, 3),
                    final_up, final_down, is_anomaly
                )
            )

            # 生成降采样 ticks
            ticks = []
            for sec in range(0, 301, 10):
                diff = round(-trend * 0.35 * (sec / 300) + random.uniform(-0.05, 0.05), 3)
                ticks.append({
                    "period_id": f"{period_id}_{sym}",
                    "symbol": sym,
                    "sec_offset": sec,
                    "up_odds": round(1.95 - diff * 0.5, 2),
                    "down_odds": round(1.95 + diff * 0.5, 2),
                    "odds_diff": diff,
                    "price": round(open_p * (1 + (sec / 300) * trend * amp / 100), 2)
                })

            downsampled = downsample_odds_ticks(ticks, max_target_points=35)
            tick_params = [
                (t["period_id"], t["symbol"], t["sec_offset"], t["up_odds"], t["down_odds"], t["odds_diff"], 0.0, t["price"])
                for t in downsampled
            ]
            db.execute_batch_write(
                """
                INSERT INTO odds_tick (period_id, symbol, sec_offset, up_odds, down_odds, odds_diff, diff_slope, price)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                tick_params
            )

            # 生成形态记录
            db.execute_write(
                """
                INSERT OR REPLACE INTO chart_shape (period_id, symbol, amplitude, reversal_count, extreme_sec, shape_category, normalized_series_json)
                VALUES (?, ?, ?, ?, ?, 'ONE_WAY_TREND', '[]')
                """,
                (f"{period_id}_{sym}", sym, amp, 1, 240)
            )

        btc_price = open_p
        eth_price = open_p

    print(f"数据初始化完成，已写入 {period_count * 2} 局冷启动数据！")

if __name__ == "__main__":
    seed_simulation_data(100)
