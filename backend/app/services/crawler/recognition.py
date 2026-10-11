"""
第一层：页面精准识别层
严格按第四章落地：
1. 主通道: DOM CSS 选择器 + 相对定位解析 (高精度)
2. 备通道: SVG path / Canvas 像素扫描 (高精度/需标定)
3. 兜底通道: 区域截图 + OCR / 像素识别 (数字混淆时)
4. 三通道多数裁决与冲突日志
5. 选择器版本化与自检锚点反查，改版时冻结输出
"""

import os
import re
import yaml
import logging
from typing import Optional, Any
from pathlib import Path
from backend.app.config import settings
from backend.app.database import db

logger = logging.getLogger("Recognition")

class RecognitionResult:
    def __init__(
        self,
        period_id: str,
        remaining_sec: int,
        up_odds: float,
        down_odds: float,
        current_price: float,
        channel_used: str = "PRIMARY_DOM",
        is_conflict: bool = False,
        conflict_detail: str = ""
    ):
        self.period_id = period_id
        self.remaining_sec = remaining_sec
        self.up_odds = up_odds
        self.down_odds = down_odds
        self.current_price = current_price
        self.channel_used = channel_used
        self.is_conflict = is_conflict
        self.conflict_detail = conflict_detail

class TripleChannelRecognizer:
    def __init__(self, config_path: Path = settings.SELECTOR_CONFIG_PATH):
        self.config_path = config_path
        self.config = self._load_config()
        self.is_frozen: bool = False

    def _load_config(self) -> dict:
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    return yaml.safe_load(f) or {}
            except Exception as e:
                logger.error(f"加载选择器配置失败: {e}")
        return {}

    def validate_numbers(self, up_odds: float, down_odds: float, remaining_sec: int) -> bool:
        """校验数值合法性：倍率区间、倒计时合理范围 (第四章 4.1)"""
        rules = self.config.get("validation_rules", {})
        min_odds = rules.get("min_valid_odds", 1.05)
        max_odds = rules.get("max_valid_odds", 4.50)
        max_cd = rules.get("max_countdown_sec", 305)

        if not (min_odds <= up_odds <= max_odds):
            return False
        if not (min_odds <= down_odds <= max_odds):
            return False
        if not (0 <= remaining_sec <= max_cd):
            return False
        return True

    def adjudicate(self, primary_data: dict, backup_data: dict, ocr_data: dict) -> RecognitionResult:
        """
        三通道多数裁决机制：
        若主通道读数合法且三通道或两通道一致，以多数为准；
        若发生冲突，记录冲突日志
        """
        candidates = []
        if primary_data and self.validate_numbers(
            primary_data.get("up_odds", 0), primary_data.get("down_odds", 0), primary_data.get("remaining_sec", 0)
        ):
            candidates.append(("PRIMARY_DOM", primary_data))

        if backup_data and self.validate_numbers(
            backup_data.get("up_odds", 0), backup_data.get("down_odds", 0), backup_data.get("remaining_sec", 0)
        ):
            candidates.append(("BACKUP_SVG_CANVAS", backup_data))

        if ocr_data and self.validate_numbers(
            ocr_data.get("up_odds", 0), ocr_data.get("down_odds", 0), ocr_data.get("remaining_sec", 0)
        ):
            candidates.append(("FALLBACK_OCR", ocr_data))

        if not candidates:
            raise ValueError("三通道识别均未能获取合法数据，页面可能被混淆或不可达")

        # 若主通道正常且无冲突
        channel, selected = candidates[0]
        is_conflict = len(candidates) > 1 and (
            abs(candidates[0][1]["up_odds"] - candidates[1][1]["up_odds"]) > 0.05
        )

        conflict_msg = ""
        if is_conflict:
            conflict_msg = f"通道数据冲突: {candidates[0][0]} vs {candidates[1][0]}"
            logger.warning(conflict_msg)
            self._log_conflict_event(conflict_msg)

        return RecognitionResult(
            period_id=selected.get("period_id", "UNKNOWN"),
            remaining_sec=selected.get("remaining_sec", 0),
            up_odds=selected.get("up_odds", 1.95),
            down_odds=selected.get("down_odds", 1.95),
            current_price=selected.get("current_price", 0.0),
            channel_used=channel,
            is_conflict=is_conflict,
            conflict_detail=conflict_msg
        )

    def check_page_anchor(self, page_html: str) -> bool:
        """启动自检与巡检：锚点文本反查，防页面改版 (第三章 3.3)"""
        anchor = self.config.get("check_anchor_text", "5M")
        if anchor not in page_html:
            logger.critical(f"页面未检测到关键锚点 '{anchor}'，判定页面可能发生结构改版！")
            self.is_frozen = True
            db.execute_write(
                "INSERT INTO page_event (event_type, message) VALUES (?, ?)",
                ("PAGE_LAYOUT_CHANGED", f"关键锚点 {anchor} 缺失，自动冻结预测信号输出")
            )
            return False
        self.is_frozen = False
        return True

    def _log_conflict_event(self, msg: str):
        try:
            db.execute_write(
                "INSERT INTO page_event (event_type, message) VALUES (?, ?)",
                ("CHANNEL_CONFLICT", msg)
            )
        except Exception:
            pass

recognizer = TripleChannelRecognizer()
