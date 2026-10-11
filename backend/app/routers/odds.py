"""
倍率摘要接口
按第二十章落地，提供前端画图与趋势分析
"""

from fastapi import APIRouter, Query
from typing import Optional
from backend.app.database import db

router = APIRouter(prefix="/api/odds", tags=["Odds"])

@router.get("/summary")
def get_odds_summary(symbol: str = Query("BTC"), limit_periods: int = Query(20, ge=1, le=100)):
    """获取最新若干期的降采样倍率序列汇总"""
    query = """
    SELECT p.period_id, p.open_time, p.direction, t.sec_offset, t.odds_diff, t.up_odds, t.down_odds
    FROM period_result p
    JOIN odds_tick t ON p.period_id = t.period_id
    WHERE p.symbol = ?
    ORDER BY p.open_time DESC, t.sec_offset ASC
    LIMIT ?
    """
    rows = db.execute_read(query, (symbol, limit_periods * 35))
    return {"symbol": symbol, "ticks": rows}
