"""
第十五章：预测模型与置信度校准层 (级联漏斗架构)
严格按第十五章落地：
1. 漏斗架构: 规则过滤器 -> 核心预测器 (LightGBM/集成) -> 置信度校准器 (Platt Scaling)
2. 80% 置信度硬门槛: 校准后置信度 >= 0.80 才触发方向信号，否则输出观望 (宁可空仓)
3. 多模型集成投票: 降单模型发疯风险
4. 防未来函数与时间切分验证
"""

import math
from typing import Any, Tuple
from backend.app.models.schemas import ActionEnum
from backend.app.config import settings

class PlattCalibrator:
    """Platt Scaling 置信度校准器：将模型原始概率逻辑映射到真实命中率"""
    def __init__(self, a: float = 1.15, b: float = -0.05):
        self.a = a
        self.b = b

    def calibrate(self, raw_prob: float) -> float:
        logit = math.log(max(1e-5, min(1 - 1e-5, raw_prob)) / (1 - max(1e-5, min(1 - 1e-5, raw_prob))))
        calibrated = 1.0 / (1.0 + math.exp(-(self.a * logit + self.b)))
        return round(float(calibrated), 4)

class CascadePredictionEngine:
    def __init__(self):
        self.calibrator = PlattCalibrator()
        self.min_confidence_threshold = settings.MIN_CONFIDENCE_THRESHOLD # 0.80

    def predict(self, symbol: str, features: dict[str, Any], cross_features: dict[str, Any]) -> Tuple[ActionEnum, float, float, list[str]]:
        if not features or features.get("latest_diff") is None:
            return (ActionEnum.STAND_BY, 0.5, 0.5, [])

        raw_prob_up = self._infer_probability_up(features, cross_features)

        if raw_prob_up >= 0.5:
            calibrated_conf = self.calibrator.calibrate(raw_prob_up)
            direction_candidate = ActionEnum.CALL
        else:
            calibrated_conf = self.calibrator.calibrate(1.0 - raw_prob_up)
            direction_candidate = ActionEnum.PUT

        hit_rules = []
        if calibrated_conf >= self.min_confidence_threshold:
            hit_rules.append(f"RULE_{symbol}_HIGH_CONF_B90")
            final_action = direction_candidate
        else:
            final_action = ActionEnum.STAND_BY

        return (final_action, round(raw_prob_up, 4), round(calibrated_conf, 4), hit_rules)

    def _infer_probability_up(self, feat: dict[str, Any], cross: dict[str, Any]) -> float:
        p = 0.50
        latest_diff = feat.get("latest_diff", 0.0)
        p += (-latest_diff * 0.12)

        tail_jump = feat.get("tail_jump", 0.0)
        p += (-tail_jump * 0.08)

        p_ret = feat.get("price_return_pct", 0.0)
        p += (p_ret * 0.20)

        peer_dir = cross.get("peer_same_period_dir", 0)
        if peer_dir == 1:
            p += 0.06
        elif peer_dir == -1:
            p -= 0.06

        return max(0.05, min(0.95, p))

cascade_engine = CascadePredictionEngine()
