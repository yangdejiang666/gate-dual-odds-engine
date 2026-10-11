"""
第二十四章：异常行情与盘口匹配识别处理
严格按第二十四章落地：
1. 单边被动上涨/拉盘砸盘识别 (PASSIVE_PUMP_DUMP)
2. 插针识别 (SPIKE_PIN)
3. 倍率极端跳变识别 (ODDS_EXTREME_JUMP)
4. 无行情静默 (MARKET_SILENCE)
5. 隔离处理：默认从统计和模型训练中剔除，杜绝极端局污染规则胜率
"""

from typing import Any, Optional

class AnomalyDetector:
    def detect_period_anomaly(self, ticks: list[dict[str, Any]], open_price: float) -> tuple[bool, Optional[str]]:
        """
        局结束时分析整局走势与倍率，判定是否为极端异常局
        """
        if len(ticks) < 10:
            return (True, "MARKET_SILENCE")

        prices = [t.get("price") or open_price for t in ticks]
        diffs = [t["odds_diff"] for t in ticks]

        amplitude_pct = ((max(prices) - min(prices)) / max(0.01, open_price)) * 100

        # 1. 无行情静默 (振幅接近 0 且倍率无变化)
        if amplitude_pct < 0.005 and max(diffs) - min(diffs) < 0.02:
            return (True, "MARKET_SILENCE")

        # 2. 插针 (Spike): 极值与次极值偏离过大
        sorted_p = sorted(prices)
        if len(sorted_p) >= 20:
            top_gap = (sorted_p[-1] - sorted_p[-5]) / max(0.01, open_price) * 100
            bot_gap = (sorted_p[4] - sorted_p[0]) / max(0.01, open_price) * 100
            if top_gap > 0.40 or bot_gap > 0.40:
                return (True, "SPIKE_PIN")

        # 3. 单边被动拉盘/砸盘 (振幅过大且单边无反转)
        if amplitude_pct > 0.60:
            # 检查是否有反转
            reversals = 0
            for i in range(1, len(diffs)):
                if (diffs[i-1] > 0 and diffs[i] < 0) or (diffs[i-1] < 0 and diffs[i] > 0):
                    reversals += 1
            if reversals <= 1:
                return (True, "PASSIVE_PUMP_DUMP")

        # 4. 倍率极端跳变 (单秒跳变大于 0.8)
        for i in range(1, len(diffs)):
            if abs(diffs[i] - diffs[i-1]) > 0.80:
                return (True, "ODDS_EXTREME_JUMP")

        return (False, None)

anomaly_detector = AnomalyDetector()
