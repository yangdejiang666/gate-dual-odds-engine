"""
历史回测中心接口
按第二十章与第十八章落地
"""

from fastapi import APIRouter
from backend.app.models.schemas import BacktestRequest, BacktestResponse
from backend.app.services.engine.walk_forward_backtest import backtest_engine

router = APIRouter(prefix="/api/backtest", tags=["Backtest"])

@router.post("/run", response_model=BacktestResponse)
def run_backtest_endpoint(req: BacktestRequest):
    return backtest_engine.run_backtest(req)
