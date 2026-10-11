"""
特征工程与过程分析服务 (v3.1 真实盘面特征升级版)
严格按第七章、第十二章、第十三章与第二十四章落地：
1. 倍率/份额价时序特征: 倍率差、斜率、交叉点、末30s跳变、隐含概率与抽水率
2. 真实盘面多空配比: 买方配比 (b_ratio)、价差超额 (price_diff)
3. 时间片条件特征: 0-30s, 30-60s, 60-120s, 120-180s, 180-240s, 240-300s
4. 价格变动与反转叠加: 振幅分档、量价同向、资金抢跑、背离因子
5. 归一化曲线序列与形态归类 (单边倾斜/中途反转/全程胶着/尾盘突变)
"""

import math
from typing import Any
from backend.app.models.schemas import ShapeCategoryEnum

class FeatureExtractor:
    def __init__(self):
        pass

    def extract_period_features(self, ticks: list[dict[str, Any]], open_price: float) -> dict[str, Any]:
        """
        从单局所有已知 ticks 提取完整特征集合 (40~60 维特征)
        """
        if not ticks:
            return self._empty_features()

        sorted_ticks = sorted(ticks, key=lambda x: x["sec_offset"])
        first_tick = sorted_ticks[0]
        last_tick = sorted_ticks[-1]

        # 1. 基础倍率/份额价特征 (第七章 7.1)
        up_odds_list = [t.get("up_odds", 1.95) for t in sorted_ticks]
        down_odds_list = [t.get("down_odds", 1.95) for t in sorted_ticks]
        diff_list = [t["odds_diff"] for t in sorted_ticks]

        initial_diff = diff_list[0]
        latest_diff = diff_list[-1]
        mean_diff = sum(diff_list) / len(diff_list)

        max_diff = max(diff_list)
        min_diff = min(diff_list)
        extreme_max_sec = sorted_ticks[diff_list.index(max_diff)]["sec_offset"]
        extreme_min_sec = sorted_ticks[diff_list.index(min_diff)]["sec_offset"]

        # 正负符号翻转交叉点次数
        cross_count = 0
        for i in range(1, len(diff_list)):
            if (diff_list[i - 1] > 0 and diff_list[i] <= 0) or (diff_list[i - 1] < 0 and diff_list[i] >= 0):
                cross_count += 1

        # 末段 30 秒跳变 (尾盘抢筹捕捉)
        tail_ticks = [t for t in sorted_ticks if t["sec_offset"] >= 270]
        tail_jump = (tail_ticks[-1]["odds_diff"] - tail_ticks[0]["odds_diff"]) if len(tail_ticks) >= 2 else 0.0

        # 隐含概率与平台抽水率
        implied_p_up = 1.0 / max(0.01, last_tick.get("up_odds", 1.95))
        implied_p_down = 1.0 / max(0.01, last_tick.get("down_odds", 1.95))
        overround = (implied_p_up + implied_p_down) - 1.0

        # 2. 真实价格与价差超额 (第十二章 12.1)
        prices = [t.get("price") or open_price for t in sorted_ticks]
        current_price = prices[-1]
        target_price = first_tick.get("target_price") or open_price
        price_diff = current_price - target_price
        price_return_pct = ((current_price - target_price) / max(0.01, target_price) * 100)
        amplitude_pct = ((max(prices) - min(prices)) / max(0.01, target_price) * 100)

        # 买方配比特征 (第二十四章 24.2 节)
        latest_b_ratio = last_tick.get("b_ratio", 0.50)

        # 价格振幅分档
        if amplitude_pct < 0.05:
            amp_bucket = 0
        elif amplitude_pct < 0.15:
            amp_bucket = 1
        else:
            amp_bucket = 2

        # 3. 时间片切分特征
        slices = {
            "slice_0_30_diff": self._get_slice_diff(sorted_ticks, 0, 30),
            "slice_30_60_diff": self._get_slice_diff(sorted_ticks, 30, 60),
            "slice_60_120_diff": self._get_slice_diff(sorted_ticks, 60, 120),
            "slice_120_180_diff": self._get_slice_diff(sorted_ticks, 120, 180),
            "slice_180_240_diff": self._get_slice_diff(sorted_ticks, 180, 240),
            "slice_240_300_diff": self._get_slice_diff(sorted_ticks, 240, 300)
        }

        # 4. 量价与资金同向/背离
        is_co_direction = 1 if (price_return_pct > 0 and latest_diff < 0) or (price_return_pct < 0 and latest_diff > 0) else 0
        is_divergence = 1 if (price_return_pct > 0 and latest_diff > 0) or (price_return_pct < 0 and latest_diff < 0) else 0

        # 5. 形态归类
        shape_cat = self.classify_shape(diff_list, cross_count, tail_jump)

        return {
            "initial_diff": initial_diff,
            "latest_diff": latest_diff,
            "mean_diff": mean_diff,
            "max_diff": max_diff,
            "min_diff": min_diff,
            "extreme_max_sec": extreme_max_sec,
            "extreme_min_sec": extreme_min_sec,
            "cross_count": cross_count,
            "tail_jump": tail_jump,
            "implied_p_up": implied_p_up,
            "implied_p_down": implied_p_down,
            "overround": overround,
            "price_diff": price_diff,
            "price_return_pct": price_return_pct,
            "amplitude_pct": amplitude_pct,
            "amp_bucket": amp_bucket,
            "b_ratio": latest_b_ratio,
            "is_co_direction": is_co_direction,
            "is_divergence": is_divergence,
            "shape_cat": shape_cat.value,
            **slices
        }

    def classify_shape(self, diff_list: list[float], cross_count: int, tail_jump: float) -> ShapeCategoryEnum:
        if not diff_list:
            return ShapeCategoryEnum.UNKNOWN
        if abs(tail_jump) >= 0.35:
            return ShapeCategoryEnum.TAIL_BURST
        if cross_count >= 3:
            return ShapeCategoryEnum.TIGHT_CONGESTION
        if cross_count in (1, 2):
            return ShapeCategoryEnum.MID_REVERSAL
        return ShapeCategoryEnum.ONE_WAY_TREND

    def _get_slice_diff(self, ticks: list[dict[str, Any]], start_sec: int, end_sec: int) -> float:
        sub = [t["odds_diff"] for t in ticks if start_sec <= t["sec_offset"] <= end_sec]
        return (sum(sub) / len(sub)) if sub else 0.0

    def _empty_features(self) -> dict[str, Any]:
        return {
            "initial_diff": 0.0, "latest_diff": 0.0, "mean_diff": 0.0,
            "max_diff": 0.0, "min_diff": 0.0, "extreme_max_sec": 0, "extreme_min_sec": 0,
            "cross_count": 0, "tail_jump": 0.0, "implied_p_up": 0.5, "implied_p_down": 0.5,
            "overround": 0.05, "price_diff": 0.0, "price_return_pct": 0.0, "amplitude_pct": 0.0,
            "amp_bucket": 1, "b_ratio": 0.50, "is_co_direction": 0, "is_divergence": 0,
            "shape_cat": ShapeCategoryEnum.UNKNOWN.value,
            "slice_0_30_diff": 0.0, "slice_30_60_diff": 0.0, "slice_60_120_diff": 0.0,
            "slice_120_180_diff": 0.0, "slice_180_240_diff": 0.0, "slice_240_300_diff": 0.0
        }

feature_extractor = FeatureExtractor()
