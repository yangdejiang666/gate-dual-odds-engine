"""
实时计算引擎协同调度器 (Realtime Engine Coordinator)
严格按第二、六、七、八、九、十四、十五、二十三、二十四、二十五章落地：
1. 状态机驱动: WAITING -> RUNNING -> SETTLING -> RESULT
2. 数据存储: 秒级落地 odds_tick、局结算落地 period_result 与 chart_shape
3. 联动计算: BTC 与 ETH 跨标的秒级对齐与特征提取 (cross_analyzer)
4. 级联漏斗预测: 规则过滤 -> 核心预测 -> 置信度校准 (Platt Scaling)
5. 约束过滤: 联动一致性过滤 (Chapter 14) + 时间片约束 T_early/T_cutoff (Chapter 25)
6. 异常局隔离: 极值插针、单边被动异动检测 (anomaly_detector)
7. 信号核算与信誉闭环: 胜负核算 (settlement_service) + 动态信用分 (reputation_engine)
"""

import time
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from backend.app.database import db
from backend.app.config import settings
from backend.app.models.schemas import ActionEnum, DirectionEnum, CrossStateEnum, StateMachineState
from backend.app.services.crawler.recognition import recognizer, RecognitionResult
from backend.app.services.crawler.state_machine import PeriodStateMachine
from backend.app.services.collector.feature_extractor import feature_extractor
from backend.app.services.collector.cross_analyzer import cross_analyzer
from backend.app.services.engine.cascade_model import cascade_engine
from backend.app.services.accounting.decision_guard import decision_guard
from backend.app.services.accounting.settlement_service import settlement_service
from backend.app.services.accounting.reputation_engine import reputation_engine
from backend.app.services.accounting.anomaly_detector import anomaly_detector

logger = logging.getLogger("EngineCoordinator")

class RealtimeEngineCoordinator:
    def __init__(self):
        self.state_machines: Dict[str, PeriodStateMachine] = {
            "BTC": PeriodStateMachine("BTC"),
            "ETH": PeriodStateMachine("ETH")
        }
        self.ticks_buffer: Dict[str, List[Dict[str, Any]]] = {
            "BTC": [],
            "ETH": []
        }
        self.open_prices: Dict[str, float] = {
            "BTC": 83000.0,
            "ETH": 2500.0
        }
        self.last_logged_signal_period: Dict[str, str] = {
            "BTC": "",
            "ETH": ""
        }
        self.latest_market_cache: Dict[str, Any] = {
            "btc": {
                "target_price": 83008.45,
                "current_price": 83022.04,
                "price_diff": 13.59,
                "call_price": 0.98,
                "put_price": 0.03,
                "b_ratio": "B 68.27%",
                "odds_diff": -0.95
            },
            "eth": {
                "target_price": 2502.24,
                "current_price": 2502.31,
                "price_diff": 0.07,
                "call_price": 0.78,
                "put_price": 0.23,
                "b_ratio": "B 34.07%",
                "odds_diff": -0.55
            }
        }
        
        # 绑定状态机生命周期回调
        for sym in ["BTC", "ETH"]:
            sm = self.state_machines[sym]
            sm.on_period_start = self._handle_period_start
            sm.on_period_settle = self._handle_period_settle
            sm.on_tick_sample = self._handle_tick_sample

    def _handle_period_start(self, symbol: str, period_id: str):
        logger.info(f"[{symbol}] 开启新对局缓冲: {period_id}")
        self.ticks_buffer[symbol] = []
        self.last_logged_signal_period[symbol] = ""

    def _handle_period_settle(self, symbol: str, period_id: str):
        """局结算落地：写入 period_result、chart_shape，并核算信号与更新信誉"""
        ticks = self.ticks_buffer[symbol]
        if not ticks:
            logger.warning(f"[{symbol}] 结算时无 tick 缓冲数据: {period_id}")
            return

        open_p = self.open_prices[symbol] or ticks[0].get("price", 1.0)
        close_p = ticks[-1].get("price", open_p)
        actual_direction = DirectionEnum.UP.value if close_p >= open_p else DirectionEnum.DOWN.value

        prices = [t.get("price") or open_p for t in ticks]
        max_p, min_p = max(prices), min(prices)
        amplitude_pct = round(((max_p - min_p) / max(0.01, open_p)) * 100, 4)

        # 异常局检测 (第二十四章)
        is_anomaly, anomaly_type = anomaly_detector.detect_period_anomaly(ticks, open_p)
        anomaly_val = 1 if is_anomaly else 0

        final_up_odds = ticks[-1].get("up_odds", 1.95)
        final_down_odds = ticks[-1].get("down_odds", 1.95)

        # 写入 period_result 表
        try:
            db.execute_write(
                """
                INSERT OR REPLACE INTO period_result 
                (period_id, symbol, open_time, close_time, open_price, close_price, direction, amplitude_pct, final_up_odds, final_down_odds, is_anomaly, anomaly_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    period_id, symbol,
                    ticks[0].get("timestamp", datetime.utcnow().isoformat()),
                    ticks[-1].get("timestamp", datetime.utcnow().isoformat()),
                    open_p, close_p, actual_direction, amplitude_pct,
                    final_up_odds, final_down_odds, anomaly_val, anomaly_type
                )
            )
        except Exception as e:
            logger.error(f"写入 period_result 失败: {e}")

        # 形态归类与 chart_shape 落库
        try:
            diffs = [t["odds_diff"] for t in ticks]
            crosses = 0
            for i in range(1, len(diffs)):
                if (diffs[i - 1] > 0 and diffs[i] <= 0) or (diffs[i - 1] < 0 and diffs[i] >= 0):
                    crosses += 1
            tail_jump = (diffs[-1] - diffs[0]) if len(diffs) > 1 else 0.0
            shape_cat = feature_extractor.classify_shape(diffs, crosses, tail_jump)

            db.execute_write(
                """
                INSERT OR REPLACE INTO chart_shape
                (period_id, symbol, amplitude, reversal_count, extreme_sec, shape_category, normalized_series_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (period_id, symbol, amplitude_pct, crosses, 150, shape_cat.value, json.dumps(diffs[:40]))
            )
        except Exception as e:
            logger.error(f"写入 chart_shape 失败: {e}")

        # 核算本局已发出的信号并更新信誉评分 (第二十三章)
        try:
            rows = db.execute_read(
                "SELECT signal_id, action FROM signal_log WHERE period_id = ? AND symbol = ? AND outcome IS NULL",
                (period_id, symbol)
            )
            for r in rows:
                sig_id = r["signal_id"]
                outcome = settlement_service.settle_signal(sig_id, actual_direction)
                is_hit = (outcome == "HIT")
                # 更新规则信誉
                reputation_engine.update_rule_reputation(f"RULE_{symbol}_HIGH_CONF_B90", is_hit)
        except Exception as e:
            logger.error(f"核算信号失败: {e}")

    def _handle_tick_sample(self, symbol: str, period_id: str, sec_offset: int, up_odds: float, down_odds: float, price: float):
        # 由 process_tick 统一处理入库
        pass

    def process_tick(self, payload: dict) -> dict:
        """
        核心处理入口：
        接收实时探针/爬虫 payload，执行清洗、入库、特征提取、双品种联动、级联模型与风控
        """
        symbol = payload.get("symbol", "BTC").upper()
        if symbol not in ["BTC", "ETH"]:
            symbol = "BTC"

        # 1. 页面识别层校验 (第四章)
        parsed: RecognitionResult = recognizer.adjudicate(symbol, payload)
        sec_offset = max(0, min(300, 300 - parsed.remaining_sec))

        if self.open_prices[symbol] is None or parsed.remaining_sec >= 295:
            self.open_prices[symbol] = parsed.target_price or parsed.current_price

        # 2. 状态机驱动 (第六章)
        sm = self.state_machines[symbol]
        sm.update(
            recognized_period_id=parsed.period_id,
            remaining_sec=parsed.remaining_sec,
            current_price=parsed.current_price,
            up_odds=parsed.up_odds,
            down_odds=parsed.down_odds
        )

        # 3. 构造 Tick 记录
        now_iso = datetime.utcnow().isoformat()
        tick_record = {
            "period_id": parsed.period_id,
            "symbol": symbol,
            "sec_offset": sec_offset,
            "up_odds": parsed.up_odds,
            "down_odds": parsed.down_odds,
            "odds_diff": parsed.odds_diff,
            "price": parsed.current_price,
            "call_price": parsed.call_price,
            "put_price": parsed.put_price,
            "b_ratio": parsed.b_ratio,
            "target_price": parsed.target_price,
            "timestamp": now_iso
        }
        self.ticks_buffer[symbol].append(tick_record)
        if len(self.ticks_buffer[symbol]) > 300:
            self.ticks_buffer[symbol].pop(0)

        # 4. 落库 odds_tick (第八章)
        try:
            db.execute_write(
                """
                INSERT INTO odds_tick 
                (period_id, symbol, sec_offset, up_odds, down_odds, odds_diff, price, call_price, put_price, b_ratio, target_price)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    parsed.period_id, symbol, sec_offset,
                    parsed.up_odds, parsed.down_odds, parsed.odds_diff,
                    parsed.current_price, parsed.call_price, parsed.put_price,
                    parsed.b_ratio, parsed.target_price
                )
            )
        except Exception as e:
            logger.error(f"插入 odds_tick 异常: {e}")

        # 5. 更新本地盘面缓存
        sym_key = symbol.lower()
        b_ratio_str = f"B {round(parsed.b_ratio * 100, 2)}%" if isinstance(parsed.b_ratio, (int, float)) else str(parsed.b_ratio)
        self.latest_market_cache[sym_key] = {
            "target_price": parsed.target_price,
            "current_price": parsed.current_price,
            "price_diff": parsed.price_diff,
            "call_price": parsed.call_price,
            "put_price": parsed.put_price,
            "b_ratio": b_ratio_str,
            "odds_diff": parsed.odds_diff
        }

        # 6. 特征工程 (第七、十二、十三章)
        open_p = self.open_prices[symbol] or parsed.target_price or parsed.current_price
        features = feature_extractor.extract_period_features(self.ticks_buffer[symbol], open_p)

        # 7. 双标的联动分析 (第十四章)
        peer_symbol = "ETH" if symbol == "BTC" else "BTC"
        peer_ticks = self.ticks_buffer[peer_symbol]
        cross_features = cross_analyzer.compute_cross_features(
            current_symbol=symbol,
            current_ticks=self.ticks_buffer[symbol],
            peer_ticks=peer_ticks
        )

        # 8. 级联模型预测 (第十五章)
        candidate_action, raw_p, calib_conf, hit_rules = cascade_engine.predict(
            symbol=symbol,
            features=features,
            cross_features=cross_features
        )

        # 9. 联动一致性过滤 (第 14.5 节)
        try:
            cross_state_enum = CrossStateEnum(cross_features.get("cross_state", "UNKNOWN"))
        except Exception:
            cross_state_enum = CrossStateEnum.UNKNOWN
        
        filtered_action, calib_conf, cross_msg = cross_analyzer.apply_consistency_filter(
            proposed_action=candidate_action,
            calibrated_conf=calib_conf,
            cross_state=cross_state_enum,
            peer_dir=cross_features.get("peer_same_period_dir", 0)
        )

        # 10. 时间窗口与执行保护约束 (第二十五章)
        final_action, timing_msg = decision_guard.check_timing_constraints(
            sec_offset=sec_offset,
            proposed_action=filtered_action
        )

        # 确定时间窗口标签
        if sec_offset < settings.T_EARLY_SEC:
            timing_window = "T_EARLY"
        elif sec_offset > settings.T_CUTOFF_SEC:
            timing_window = "T_CUTOFF"
        else:
            timing_window = "T_WORK"

        # 生成操作建议
        if final_action == ActionEnum.CALL:
            advice = f"建议跟投看涨 (置信度: {int(calib_conf * 100)}%)"
        elif final_action == ActionEnum.PUT:
            advice = f"建议跟投看跌 (置信度: {int(calib_conf * 100)}%)"
        else:
            reason = timing_msg or cross_msg or "置信度不足 80% 或未触发特征"
            advice = f"保持观望 ({reason})"

        # 11. 信号落账登记 (第二十三章)
        if final_action != ActionEnum.STAND_BY and self.last_logged_signal_period[symbol] != parsed.period_id:
            sig_id = f"SIG_{parsed.period_id}_{symbol}_{sec_offset}"
            try:
                db.execute_write(
                    """
                    INSERT OR REPLACE INTO signal_log
                    (signal_id, period_id, symbol, sec_offset, action, raw_prob, calibrated_conf, rule_hits, cross_state, advice)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        sig_id, parsed.period_id, symbol, sec_offset,
                        final_action.value, raw_p, calib_conf,
                        json.dumps(hit_rules), cross_features.get("cross_state", "UNKNOWN"), advice
                    )
                )
                self.last_logged_signal_period[symbol] = parsed.period_id
            except Exception as e:
                logger.error(f"记录 signal_log 失败: {e}")

        # 12. 组装下发与广播报文
        result_payload = {
            "period_id": parsed.period_id,
            "remaining_sec": parsed.remaining_sec,
            "sec_offset": sec_offset,
            "timing_window": timing_window,
            "symbol": symbol,
            "btc": self.latest_market_cache["btc"],
            "eth": self.latest_market_cache["eth"],
            "signal": {
                "action": final_action.value,
                "raw_prob": raw_p,
                "calibrated_conf": calib_conf,
                "advice": advice,
                "cross_state": cross_features.get("cross_state", "UNKNOWN"),
                "order_ratio_diff": cross_features.get("order_ratio_diff", 0.0),
                "hit_rules": hit_rules
            }
        }
        return result_payload

engine_coordinator = RealtimeEngineCoordinator()
