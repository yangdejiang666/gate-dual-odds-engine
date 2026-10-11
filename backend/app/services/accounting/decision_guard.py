"""
第二十五章：跟随机制与剩余时间机制
严格按第二十五章落地：
1. 剩余时间硬过滤器:
   - T_early (前 60 秒): 早期反转多为噪声，信息不足，一律观望不出手
   - T_work (60~270 秒): 黄金工作区间，信号在此输出
   - T_cutoff (270 秒后): 临近结算，防滑点与追单失败，一律截断观望
2. 跟随机制: 顺势延续与联动确认，冲突时信誉加权降级
"""

from typing import Tuple, Any
from backend.app.models.schemas import ActionEnum
from backend.app.config import settings

class DecisionGuard:
    def __init__(self):
        self.t_early = settings.T_EARLY_SEC
        self.t_cutoff = settings.T_CUTOFF_SEC

    def check_timing_constraints(self, sec_offset: int, raw_action: Any = None, proposed_action: Any = None) -> Tuple[ActionEnum, str]:
        """
        检查局内秒偏移是否处于允许下单的安全时间窗 (第二十五章 25.2 节)
        """
        act = proposed_action if proposed_action is not None else raw_action
        if isinstance(act, str):
            try:
                act = ActionEnum(act)
            except Exception:
                act = ActionEnum.STAND_BY

        if act == ActionEnum.STAND_BY or act is None:
            return (ActionEnum.STAND_BY, "模型本身输出观望")

        # 1. 开局前 60 秒: 信息量不足，易被反转
        if sec_offset < self.t_early:
            return (ActionEnum.STAND_BY, f"开局早期 ({sec_offset}s < {self.t_early}s): 信息量不足，保持观望")

        # 2. 临近结算 (270 秒后，即最后 30 秒): 禁止追单
        if sec_offset >= self.t_cutoff:
            return (ActionEnum.STAND_BY, f"临近结算 ({sec_offset}s >= {self.t_cutoff}s): 窗口关闭防滑点，停止出手")

        return (act, "处于黄金工作窗口 T_work")

decision_guard = DecisionGuard()
