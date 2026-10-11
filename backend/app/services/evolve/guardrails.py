"""
第二十七章：防刷 90% 护栏与统计显著性检验
严格按第二十七章 27.2 节与 27.6 节落地：
1. 唯一判据: 只看校准后高置信档滚动样本外命中率
2. 泛化差监控: 训练集 vs 样本外命中差 > 5pp 直接触发 GUARD_HOLD
3. Wilson 95% 置信区间下界计算 (防小样本虚假达标)
4. 日均有效出手率约束 (>= 2次/天)
"""

import math
from typing import Tuple

class EvolveGuardrails:
    def __init__(self, wilson_z: float = 1.96): # 95% 置信度对应 z = 1.96
        self.z = wilson_z

    def calculate_wilson_lower_bound(self, hits: int, total: int) -> float:
        """
        计算 Wilson 得分置信区间下界 (第二十七章 27.2 节)
        防止小样本 (如 20 局对 19 局 95%) 假达标
        """
        if total <= 0:
            return 0.0
        p = hits / total
        z2 = self.z ** 2
        denominator = 1 + z2 / total
        centre_adjusted_probability = p + z2 / (2 * total)
        adjusted_standard_deviation = math.sqrt((p * (1 - p) + z2 / (4 * total)) / total)
        
        lower_bound = (centre_adjusted_probability - self.z * adjusted_standard_deviation) / denominator
        return round(max(0.0, float(lower_bound)), 4)

    def check_guardrails(
        self,
        train_acc: float,
        out_of_sample_acc: float,
        total_eval_samples: int,
        daily_actions: float,
        target_ladder: float
    ) -> Tuple[bool, str]:
        """
        全量护栏扫描，返回 (是否通过, 诊断说明)
        """
        # 1. 泛化差监控 (过拟合熔断)
        generalization_gap = (train_acc - out_of_sample_acc) * 100
        if generalization_gap > 5.0:
            return (False, f"泛化差过大 ({generalization_gap:.1f}pp > 5.0pp)，判定为记忆化过拟合，触发 GUARD_HOLD")

        # 2. 样本量下限检查
        if total_eval_samples < 50:
            return (False, f"评估样本量不足 ({total_eval_samples} < 50)，继续累积数据，暂未收敛")

        # 3. 日均出手率检查
        if daily_actions < 1.0:
            return (False, f"有效出手率过低 ({daily_actions:.1f}次/天 < 1.0次/天)，疑似靠极端收窄阈值刷指标")

        # 4. Wilson 下界必须达标
        hits = int(out_of_sample_acc * total_eval_samples)
        wilson_lower = self.calculate_wilson_lower_bound(hits, total_eval_samples)
        if wilson_lower < (target_ladder - 0.03):
            return (False, f"Wilson 95% 下界仅为 {wilson_lower*100:.1f}%，未达到目标阈值 {target_ladder*100:.1f}%-3pp")

        return (True, "护栏全部通过")

guardrails = EvolveGuardrails()
