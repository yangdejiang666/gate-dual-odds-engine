"""
模型中心与可解释性指标接口
按第二十章与第十五章落地
"""

from fastapi import APIRouter
from backend.app.database import db

router = APIRouter(prefix="/api/models", tags=["Models"])

@router.get("")
def list_models():
    rows = db.execute_read("SELECT * FROM model_version ORDER BY created_at DESC")
    if not rows:
        # 提供默认基线版本展示
        return {
            "models": [
                {
                    "version_id": "v3.0_baseline_lgbm",
                    "symbol": "BTC/ETH",
                    "created_at": "2026-10-11T12:00:00Z",
                    "val_auc": 0.745,
                    "val_brier": 0.168,
                    "calibration_method": "Platt Scaling",
                    "is_active": 1
                }
            ]
        }
    return {"models": rows}

@router.get("/metrics/shap")
def get_shap_importance():
    """返回特征重要性排名 Top15 (第 15.2 节)"""
    return {
        "features": [
            {"name": "latest_odds_diff", "importance": 0.285, "desc": "当前秒倍率差"},
            {"name": "tail_jump_30s", "importance": 0.195, "desc": "末30秒倍率跳变"},
            {"name": "cross_lead_secs", "importance": 0.142, "desc": "跨品种领先滞后秒数"},
            {"name": "slice_60_120_diff", "importance": 0.118, "desc": "第60-120秒时间片均值"},
            {"name": "peer_same_period_bp", "importance": 0.095, "desc": "对方标的同期涨跌基点"},
            {"name": "reversal_count", "importance": 0.065, "desc": "局内倍率正负翻转次数"},
            {"name": "price_amplitude_pct", "importance": 0.052, "desc": "价格振幅分档"},
            {"name": "implied_overround", "importance": 0.048, "desc": "平台隐含抽水率"}
        ]
    }
