"""
第二层：五分钟一局状态机
严格按第六章落地：
1. 四态流转: WAITING -> RUNNING -> SETTLING -> RESULT
2. 双保险驱动: 倒计时递减秒级驱动 (主) + 期号文本变化驱动 (辅)
3. 冲突仲裁: 冲突时以期号变化为准，杜绝整局错位
4. 局内秒偏移 sec_offset (0 到 300) 统一对齐
"""

import time
import logging
from typing import Optional, Callable
from datetime import datetime
from backend.app.models.schemas import StateMachineState, SymbolEnum

logger = logging.getLogger("StateMachine")

class PeriodStateMachine:
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.state: StateMachineState = StateMachineState.WAITING
        self.current_period_id: str = ""
        self.period_start_time: float = 0.0
        self.last_remaining_sec: int = 300
        self.sec_offset: int = 0
        self.stall_count: int = 0 # 倒计时停滞检测计数器
        
        # 结果与状态回调注册
        self.on_period_start: Optional[Callable] = None
        self.on_tick_sample: Optional[Callable] = None
        self.on_period_settle: Optional[Callable] = None

    def update(self, recognized_period_id: str, remaining_sec: int, current_price: float, up_odds: float, down_odds: float):
        """
        每秒读数输入状态机，驱动状态转移
        """
        now = time.time()

        # 检查是否发生倒计时卡死停滞 (第五章 5.4 故障自愈)
        if self.state == StateMachineState.RUNNING and remaining_sec == self.last_remaining_sec and remaining_sec > 5:
            self.stall_count += 1
        else:
            self.stall_count = 0

        # 双保险驱动仲裁：检测到新期号
        if recognized_period_id and recognized_period_id != self.current_period_id:
            logger.info(f"[{self.symbol}] 检测到期号切换: {self.current_period_id} -> {recognized_period_id}")
            if self.current_period_id:
                # 上一局进入结算落地
                self._transition_to_result()
            self._start_new_period(recognized_period_id, remaining_sec)
            return

        # 局内状态流转
        if self.state == StateMachineState.RUNNING:
            self.sec_offset = max(0, min(300, 300 - remaining_sec))
            self.last_remaining_sec = remaining_sec

            # 倒计时归零进入结算中
            if remaining_sec <= 2:
                logger.info(f"[{self.symbol}] 倒计时归零，进入 SETTLING 状态")
                self.state = StateMachineState.SETTLING

            if self.on_tick_sample:
                self.on_tick_sample(
                    symbol=self.symbol,
                    period_id=self.current_period_id,
                    sec_offset=self.sec_offset,
                    up_odds=up_odds,
                    down_odds=down_odds,
                    price=current_price
                )

        elif self.state == StateMachineState.SETTLING:
            # 等待新期号开出
            pass

    def _start_new_period(self, period_id: str, remaining_sec: int):
        self.current_period_id = period_id
        self.state = StateMachineState.RUNNING
        self.period_start_time = time.time()
        self.last_remaining_sec = remaining_sec
        self.sec_offset = max(0, 300 - remaining_sec)
        self.stall_count = 0
        logger.info(f"[{self.symbol}] 开启新局: {period_id}, 剩余秒: {remaining_sec}")
        if self.on_period_start:
            self.on_period_start(self.symbol, period_id)

    def _transition_to_result(self):
        self.state = StateMachineState.RESULT
        logger.info(f"[{self.symbol}] 局号 {self.current_period_id} 结果落地，进入 RESULT")
        if self.on_period_settle:
            self.on_period_settle(self.symbol, self.current_period_id)
        self.state = StateMachineState.WAITING

    def is_stalled(self) -> bool:
        """连续 3 次读数相同判定为倒计时停滞"""
        return self.stall_count >= 3
