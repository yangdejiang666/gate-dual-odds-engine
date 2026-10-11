"""
期数查询与明细接口
严格按第二十章 20.1 节落地
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Optional
from backend.app.database import db

router = APIRouter(prefix="/api/periods", tags=["Periods"])

@router.get("")
def list_periods(
    symbol: Optional[str] = Query(None, description="标的 BTC/ETH"),
    direction: Optional[str] = Query(None, description="涨跌方向 UP/DOWN/FLAT"),
    is_anomaly: Optional[int] = Query(None, description="是否异常局"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500)
):
    offset = (page - 1) * page_size
    conditions = []
    params = []

    if symbol:
        conditions.append("symbol = ?")
        params.append(symbol)
    if direction:
        conditions.append("direction = ?")
        params.append(direction)
    if is_anomaly is not None:
        conditions.append("is_anomaly = ?")
        params.append(is_anomaly)

    where_sql = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    
    count_sql = f"SELECT COUNT(*) as total FROM period_result {where_sql}"
    total = db.execute_read(count_sql, tuple(params))[0]["total"]

    data_sql = f"""
    SELECT period_id, symbol, open_time, close_time, open_price, close_price,
           direction, amplitude_pct, final_up_odds, final_down_odds, is_anomaly, anomaly_type
    FROM period_result
    {where_sql}
    ORDER BY open_time DESC
    LIMIT ? OFFSET ?
    """
    rows = db.execute_read(data_sql, tuple(params + [page_size, offset]))

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "data": rows
    }

@router.get("/{period_id}")
def get_period_detail(period_id: str):
    res_rows = db.execute_read("SELECT * FROM period_result WHERE period_id = ?", (period_id,))
    if not res_rows:
        raise HTTPException(status_code=404, detail="未找到该期号记录")

    tick_rows = db.execute_read(
        "SELECT sec_offset, up_odds, down_odds, odds_diff, price FROM odds_tick WHERE period_id = ? ORDER BY sec_offset ASC",
        (period_id,)
    )
    shape_rows = db.execute_read("SELECT * FROM chart_shape WHERE period_id = ?", (period_id,))
    signals = db.execute_read("SELECT * FROM signal_log WHERE period_id = ?", (period_id,))

    return {
        "period": res_rows[0],
        "shape": shape_rows[0] if shape_rows else None,
        "signals": signals,
        "ticks": tick_rows
    }
