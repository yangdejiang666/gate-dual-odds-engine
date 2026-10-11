"""
第十四章：BTC 与 ETH 联动规律研究与双品种互为参考
严格按第十四章落地：
1. 双轨处理：分标的独立统计（口径绝不混合）+ 跨标的联动特征（互为环境条件）
2. 联动指标体系：滚动同向率、收益率相关、互相关 CCF 领先滞后阶、倍率差之差、背离率与收敛
3. 三类状态判定：同向跟随 (CO_DIRECTIONAL)、领先滞后 (LEAD_LAG)、背离独立 (DIVERGENT)
4. 过程级联动：同局内对方标的已走完的过程作为本标的的实时可用特征（不构成未来函数）
5. 一致性过滤器：信号与联动冲突时一律降级观望或下调置信度
6. 支持原生与纯 Python 自适应降级计算
"""

import math
from typing import Optional, Any
from backend.app.models.schemas import CrossStateEnum, DirectionEnum, ActionEnum

def _calc_corr(x: list[float], y: list[float]) -> float:
    """纯 Python 计算两组序列的 Pearson 相关系数"""
    n = len(x)
    if n < 2:
        return 0.0
    mean_x = sum(x) / n
    mean_y = sum(y) / n
    cov = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
    var_x = sum((x[i] - mean_x) ** 2 for i in range(n))
    var_y = sum((y[i] - mean_y) ** 2 for i in range(n))
    if var_x <= 1e-9 or var_y <= 1e-9:
        return 0.0
    return cov / math.sqrt(var_x * var_y)

class CrossSymbolAnalyzer:
    def __init__(self):
        self.rolling_window: int = 200

    def compute_cross_features(
        self,
        current_symbol: str,
        current_ticks: list[dict[str, Any]],
        peer_ticks: list[dict[str, Any]],
        peer_prev_direction: Optional[str] = None
    ) -> dict[str, Any]:
        """
        计算跨品种联动特征组 (第 14.5 节)
        """
        if not current_ticks or not peer_ticks:
            return self._empty_cross_features()

        # 1. 同局内两标的倍率差同向秒数占比
        min_len = min(len(current_ticks), len(peer_ticks))
        same_dir_secs = 0
        for i in range(min_len):
            c_diff = current_ticks[i]["odds_diff"]
            p_diff = peer_ticks[i]["odds_diff"]
            if (c_diff > 0 and p_diff > 0) or (c_diff < 0 and p_diff < 0):
                same_dir_secs += 1
        cross_same_dir_ratio = same_dir_secs / max(1, min_len)

        # 2. 对方标的截至目前的过程方向与基点涨幅
        peer_latest = peer_ticks[-1]
        peer_first = peer_ticks[0]
        peer_open_price = peer_first.get("price") or 1.0
        peer_cur_price = peer_latest.get("price") or peer_open_price
        peer_return_bp = ((peer_cur_price - peer_open_price) / peer_open_price) * 10000

        if peer_return_bp > 5.0:
            peer_dir = 1
        elif peer_return_bp < -5.0:
            peer_dir = -1
        else:
            peer_dir = 0

        # 3. 领先滞后秒数估计 (通过互相关 CCF 峰值)
        lead_secs = self._estimate_lead_lag(current_ticks, peer_ticks)

        # 4. 盘口买方多空配比差与背离 (第二十四章)
        cur_ratio = current_ticks[-1].get("b_ratio", 0.50) if current_ticks else 0.50
        peer_ratio = peer_ticks[-1].get("b_ratio", 0.50) if peer_ticks else 0.50
        order_ratio_diff = round(cur_ratio - peer_ratio, 4)

        # 5. 判定联动状态 (第 14.3 节)
        if cross_same_dir_ratio >= 0.70 and abs(lead_secs) <= 5:
            state = CrossStateEnum.CO_DIRECTIONAL
        elif abs(lead_secs) > 5:
            state = CrossStateEnum.LEAD_LAG
        elif cross_same_dir_ratio < 0.40 or abs(order_ratio_diff) >= 0.30:
            state = CrossStateEnum.DIVERGENT
        else:
            state = CrossStateEnum.UNKNOWN

        is_divergent = 1 if state == CrossStateEnum.DIVERGENT else 0

        return {
            "cross_same_dir_ratio": round(cross_same_dir_ratio, 4),
            "cross_lead_secs": lead_secs,
            "cross_state": state.value,
            "order_ratio_diff": order_ratio_diff,
            "peer_same_period_dir": peer_dir,
            "peer_same_period_bp": round(peer_return_bp, 2),
            "peer_prev_dir": peer_prev_direction or "UNKNOWN",
            "is_divergent": is_divergent
        }

    def _estimate_lead_lag(self, cur_ticks: list[dict], peer_ticks: list[dict]) -> int:
        cur_series = [t["odds_diff"] for t in cur_ticks]
        peer_series = [t["odds_diff"] for t in peer_ticks]
        
        n = min(len(cur_series), len(peer_series))
        if n < 30:
            return 0
        
        best_lag = 0
        max_corr = 0.0 # 阈值至少大于 0 才是正相关
        for lag in range(-15, 16):
            if lag < 0:
                corr = _calc_corr(cur_series[:lag], peer_series[-lag:n])
            elif lag > 0:
                corr = _calc_corr(cur_series[lag:n], peer_series[:n-lag])
            else:
                corr = _calc_corr(cur_series[:n], peer_series[:n])
            
            if corr > max_corr:
                max_corr = corr
                best_lag = lag
        return best_lag

    def apply_consistency_filter(
        self,
        proposed_action: ActionEnum,
        calibrated_conf: float,
        cross_state: CrossStateEnum,
        peer_dir: int
    ) -> tuple[ActionEnum, float, str]:
        if cross_state in [CrossStateEnum.CO_DIRECTIONAL, CrossStateEnum.LEAD_LAG]:
            if proposed_action == ActionEnum.CALL and peer_dir == -1:
                return (ActionEnum.STAND_BY, calibrated_conf * 0.8, "联动一致性过滤：与对方标的下行趋势冲突，降级观望")
            elif proposed_action == ActionEnum.PUT and peer_dir == 1:
                return (ActionEnum.STAND_BY, calibrated_conf * 0.8, "联动一致性过滤：与对方标的上行趋势冲突，降级观望")

        return (proposed_action, calibrated_conf, "联动校验通过")

    def _empty_cross_features(self) -> dict[str, Any]:
        return {
            "cross_same_dir_ratio": 0.5,
            "cross_lead_secs": 0,
            "cross_state": CrossStateEnum.UNKNOWN.value,
            "peer_same_period_dir": 0,
            "peer_same_period_bp": 0.0,
            "peer_prev_dir": "UNKNOWN",
            "is_divergent": 0
        }

cross_analyzer = CrossSymbolAnalyzer()
