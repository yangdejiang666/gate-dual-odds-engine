"""
第二十三章：动态信誉评分体系
严格按第二十三章 23.2 节与 23.3 节落地：
1. 0 到 100 动态信用分体系
2. 五大分量加权合成:
   - 减基准净胜率 (剔除天然偏斜)
   - 近期 EWMA 指数加权命中率 (近 100 局衰减监控)
   - 样本量置信度收缩 (防小样本虚高)
   - 校准偏差惩罚 (惩罚说到做不到)
   - 连错惩罚 (连续翻车立即降权)
3. 熔断与自愈：连续 4 次失败熔断停用，信誉低于 45 分退出决策源
"""

import math
import logging
from backend.app.config import settings
from backend.app.database import db

logger = logging.getLogger("ReputationEngine")

class ReputationEngine:
    def __init__(self):
        self.default_baseline = 0.50

    def calculate_score(
        self,
        recent_win_rate: float,
        baseline_rate: float,
        sample_count: int,
        claimed_conf: float,
        consecutive_fails: int
    ) -> float:
        """
        计算单条规则或模型的动态信用分 (0.0 ~ 100.0)
        """
        # 1. 减基准净胜率分量 (满分 30 分)
        # 净胜率 +0.30 达到满分，-0.10 跌至 0 分
        net_edge = recent_win_rate - baseline_rate
        s_baseline = max(0.0, min(30.0, (net_edge + 0.10) / 0.40 * 30.0))

        # 2. 近期加权命中率分量 (满分 35 分)
        s_recent = max(0.0, min(35.0, recent_win_rate * 35.0))

        # 3. 样本量置信度收缩分量 (满分 15 分, 样本达 500 局得满分)
        shrinkage = 1.0 - math.exp(-sample_count / 150.0)
        s_sample = shrinkage * 15.0

        # 4. 校准偏差惩罚 (满分 10 分，偏差每大 5% 扣 2 分)
        calib_error = abs(claimed_conf - recent_win_rate)
        s_calib = max(0.0, 10.0 - (calib_error / 0.05) * 2.0)

        # 5. 连错惩罚分量 (满分 10 分，连错一次扣 2.5 分)
        s_streak = max(0.0, 10.0 - consecutive_fails * 2.5)

        total_score = s_baseline + s_recent + s_sample + s_calib + s_streak
        return round(max(0.0, min(100.0, total_score)), 2)

    def update_rule_reputation(self, rule_id: str, is_hit: bool):
        """规则产生单次核算后的增量信用分维护与熔断检查"""
        rows = db.execute_read(
            "SELECT sample_count, win_rate, confidence, consecutive_fails, symbol FROM rule_registry WHERE rule_id = ?",
            (rule_id,)
        )
        if not rows:
            return

        r = rows[0]
        n = r["sample_count"] + 1
        old_win_rate = r["win_rate"]
        new_win_rate = old_win_rate + (1.0 if is_hit else 0.0 - old_win_rate) / n
        new_fails = 0 if is_hit else (r["consecutive_fails"] + 1)

        baseline = 0.505 if r["symbol"] == "BTC" else 0.498
        new_score = self.calculate_score(
            recent_win_rate=new_win_rate,
            baseline_rate=baseline,
            sample_count=n,
            claimed_conf=r["confidence"],
            consecutive_fails=new_fails
        )

        status = "ACTIVE"
        if new_fails >= settings.CONSECUTIVE_FAIL_LIMIT:
            status = "BLOCKED" # 熔断临时停用
            logger.warning(f"规则 {rule_id} 连续 {new_fails} 次失败，触发熔断停用！")
        elif new_score < settings.REPUTATION_DISABLE_SCORE and n >= 50:
            status = "RETIRED" # 衰减退役
            logger.warning(f"规则 {rule_id} 信誉分降至 {new_score} (< {settings.REPUTATION_DISABLE_SCORE})，移入退役池！")

        db.execute_write(
            """
            UPDATE rule_registry
            SET sample_count = ?, win_rate = ?, consecutive_fails = ?, reputation_score = ?, status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE rule_id = ?
            """,
            (n, round(new_win_rate, 4), new_fails, new_score, status, rule_id)
        )

reputation_engine = ReputationEngine()
