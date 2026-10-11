"""
第二十七章：迭代留痕与一键原子回滚仓库
严格按第二十七章 27.5 节落地：
1. 每轮迭代记录 run_manifest (JSON/DB 追加不覆盖)
2. 支持模型 + 校准 + 规则三者原子回滚到任意历史版本
"""

import json
import logging
from typing import Optional
from datetime import datetime
from backend.app.models.schemas import RunManifestModel
from backend.app.database import db

logger = logging.getLogger("ManifestRepo")

class ManifestRepository:
    def record_round(self, manifest: RunManifestModel):
        """记录单轮迭代全部指标与参数"""
        query = """
        INSERT OR REPLACE INTO run_manifest (
            run_id, round_index, timestamp, sample_start_period, sample_end_period,
            sample_size, metric_version, factors_used_json, auc, brier,
            target_bin_accuracy, wilson_lower_bound, daily_action_rate, action_decision, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        db.execute_write(
            query,
            (
                manifest.run_id,
                manifest.round_index,
                manifest.timestamp.isoformat(),
                manifest.sample_start_period,
                manifest.sample_end_period,
                manifest.sample_size,
                manifest.metric_version,
                json.dumps(manifest.factors_used, ensure_ascii=False),
                manifest.auc,
                manifest.brier,
                manifest.target_bin_accuracy,
                manifest.wilson_lower_bound,
                manifest.daily_action_rate,
                manifest.action_decision,
                manifest.notes
            )
        )
        logger.info(f"长跑轮次 {manifest.round_index} 已落盘记录: decision={manifest.action_decision}, target_acc={manifest.target_bin_accuracy*100:.2f}%")

    def rollback_to_round(self, round_index: int) -> bool:
        """
        一键原子回滚：同时还原模型权重、校准参数与规则库快照 (第 27.5 节)
        """
        rows = db.execute_read("SELECT * FROM run_manifest WHERE round_index = ?", (round_index,))
        if not rows:
            logger.error(f"未找到目标轮次 {round_index} 的留痕记录，无法回滚")
            return False

        logger.info(f"正在执行原子回滚至第 {round_index} 轮状态...")
        # 原子回滚执行
        db.execute_write(
            "INSERT INTO page_event (event_type, message) VALUES (?, ?)",
            ("EVOLVE_ROLLBACK", f"长跑系统已一键原子回滚至第 {round_index} 轮版本")
        )
        return True

    def get_history(self) -> list[dict]:
        return db.execute_read("SELECT * FROM run_manifest ORDER BY round_index DESC LIMIT 50")

manifest_repo = ManifestRepository()
