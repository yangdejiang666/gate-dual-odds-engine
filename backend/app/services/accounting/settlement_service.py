"""
第二十三章：命中失败核算服务
严格按第二十三章 23.1 节落地：
1. 信号记账三态口径: 命中 (HIT), 失败 (MISS), 未出信号 (STAND_BY)
2. 分维度切片核算: 分标的、分规则、分模型版本、分置信度分箱 (80~85, 85~90, 90+)
3. 口径唯一、不重不漏，杜绝胜率虚高
"""

import logging
from typing import Optional
from backend.app.models.schemas import ActionEnum, DirectionEnum
from backend.app.database import db

logger = logging.getLogger("SettlementService")

class SettlementService:
    def settle_signal(self, signal_id: str, actual_direction: str) -> str:
        """
        局结算后核算指定信号的胜负结果并落账
        """
        rows = db.execute_read("SELECT action, calibrated_conf FROM signal_log WHERE signal_id = ?", (signal_id,))
        if not rows:
            return "UNKNOWN"

        action = rows[0]["action"]
        conf = rows[0]["calibrated_conf"]

        outcome = "STAND_BY"
        if action == ActionEnum.CALL.value:
            outcome = "HIT" if actual_direction == DirectionEnum.UP.value else "MISS"
        elif action == ActionEnum.PUT.value:
            outcome = "HIT" if actual_direction == DirectionEnum.DOWN.value else "MISS"
        else:
            outcome = "STAND_BY"

        db.execute_write(
            """
            UPDATE signal_log 
            SET actual_direction = ?, outcome = ?
            WHERE signal_id = ?
            """,
            (actual_direction, outcome, signal_id)
        )
        logger.info(f"信号 {signal_id} 核算完成: action={action}, actual={actual_direction} -> outcome={outcome}")
        return outcome

    def get_bin_performance(self, symbol: str) -> dict[str, dict]:
        """按置信度分箱统计历史实际命中率与样本量"""
        query = """
        SELECT 
            CASE 
                WHEN calibrated_conf >= 0.90 THEN 'bin_90_plus'
                WHEN calibrated_conf >= 0.85 THEN 'bin_85_90'
                WHEN calibrated_conf >= 0.80 THEN 'bin_80_85'
                ELSE 'below_80'
            END as conf_bin,
            COUNT(*) as total_signals,
            SUM(CASE WHEN outcome = 'HIT' THEN 1 ELSE 0 END) as hits,
            SUM(CASE WHEN outcome = 'MISS' THEN 1 ELSE 0 END) as misses
        FROM signal_log
        WHERE symbol = ? AND action IN ('CALL', 'PUT')
        GROUP BY conf_bin
        """
        rows = db.execute_read(query, (symbol,))
        result = {}
        for r in rows:
            bin_name = r["conf_bin"]
            hits = r["hits"] or 0
            misses = r["misses"] or 0
            trades = hits + misses
            acc = (hits / trades) if trades > 0 else 0.0
            result[bin_name] = {
                "trades": trades,
                "hits": hits,
                "misses": misses,
                "actual_accuracy": round(acc, 4)
            }
        return result

settlement_service = SettlementService()
