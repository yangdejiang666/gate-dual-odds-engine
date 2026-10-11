"""
领域模型与规范
支持 Pydantic v2 与纯标准库自适应降级
"""

from enum import Enum
from typing import Optional, Any
from datetime import datetime

try:
    from pydantic import BaseModel, Field
except ImportError:
    # 纯标准库自适应降级 BaseModel
    class BaseModel:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
        def dict(self):
            return {k: v for k, v in self.__dict__.items() if not k.startswith('_')}
        def model_dump(self):
            return self.dict()

    def Field(default=None, default_factory=None, **kwargs):
        if default_factory is not None:
            return default_factory()
        return default

class SymbolEnum(str, Enum):
    BTC = "BTC"
    ETH = "ETH"

class DirectionEnum(str, Enum):
    UP = "UP"
    DOWN = "DOWN"
    FLAT = "FLAT"
    UNKNOWN = "UNKNOWN"

class ActionEnum(str, Enum):
    CALL = "CALL"       # 看涨
    PUT = "PUT"         # 看跌
    STAND_BY = "STAND_BY" # 观望

class CrossStateEnum(str, Enum):
    CO_DIRECTIONAL = "CO_DIRECTIONAL" # 同向跟随
    LEAD_LAG = "LEAD_LAG"             # 领先滞后
    DIVERGENT = "DIVERGENT"           # 背离独立
    UNKNOWN = "UNKNOWN"

class StateMachineState(str, Enum):
    WAITING = "WAITING"
    RUNNING = "RUNNING"
    SETTLING = "SETTLING"
    RESULT = "RESULT"

class ShapeCategoryEnum(str, Enum):
    ONE_WAY_TREND = "ONE_WAY_TREND"       # 单边倾斜型
    MID_REVERSAL = "MID_REVERSAL"         # 中途反转型
    TIGHT_CONGESTION = "TIGHT_CONGESTION" # 全程胶着型
    TAIL_BURST = "TAIL_BURST"             # 尾盘突变型
    UNKNOWN = "UNKNOWN"

class EvolveStateEnum(str, Enum):
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    WAIT_SAMPLE = "WAIT_SAMPLE"
    TRAINING = "TRAINING"
    CALIBRATING = "CALIBRATING"
    EVALUATING = "EVALUATING"
    DECIDING = "DECIDING"
    CONVERGED = "CONVERGED"
    PLATEAU = "PLATEAU"
    GUARD_HOLD = "GUARD_HOLD"
    STOPPED = "STOPPED"

class PeriodResultModel(BaseModel):
    period_id: str
    symbol: str
    open_time: datetime
    close_time: datetime
    open_price: float
    close_price: float
    direction: DirectionEnum
    amplitude_pct: float
    final_up_odds: float
    final_down_odds: float
    is_anomaly: bool = False
    anomaly_type: Optional[str] = None
    created_at: Optional[datetime] = None

class OddsTickModel(BaseModel):
    period_id: str
    symbol: str
    sec_offset: int
    up_odds: float
    down_odds: float
    odds_diff: float
    diff_slope: Optional[float] = 0.0
    price: Optional[float] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class ChartShapeModel(BaseModel):
    period_id: str
    symbol: str
    amplitude: float
    reversal_count: int
    extreme_sec: int
    shape_category: ShapeCategoryEnum
    normalized_series_json: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

class RuleRegistryModel(BaseModel):
    rule_id: str
    name: str
    symbol: str
    condition_json: str
    sample_count: int
    win_rate: float
    confidence: float
    reputation_score: float = 70.0
    status: str = "ACTIVE"
    consecutive_fails: int = 0
    recent_100_win_rate: Optional[float] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class SignalLogModel(BaseModel):
    signal_id: str
    period_id: str
    symbol: str
    sec_offset: int
    action: ActionEnum
    raw_prob: float
    calibrated_conf: float
    rule_hits: list[str] = []
    cross_state: CrossStateEnum = CrossStateEnum.UNKNOWN
    advice: str
    actual_direction: Optional[DirectionEnum] = None
    outcome: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class RunManifestModel(BaseModel):
    run_id: str
    round_index: int
    timestamp: datetime
    sample_start_period: str
    sample_end_period: str
    sample_size: int
    metric_version: str
    factors_used: list[str]
    auc: float
    brier: float
    target_bin_accuracy: float
    wilson_lower_bound: float
    daily_action_rate: float
    action_decision: str
    notes: Optional[str] = None

class PeriodQueryFilter(BaseModel):
    symbols: Optional[list[str]] = None
    date_start: Optional[datetime] = None
    date_end: Optional[datetime] = None
    period_id_prefix: Optional[str] = None
    directions: Optional[list[str]] = None
    shape_categories: Optional[list[str]] = None
    min_confidence: Optional[float] = None
    is_anomaly: Optional[bool] = None
    page: int = 1
    page_size: int = 50

class SystemHealthResponse(BaseModel):
    status: str
    app_version: str
    uptime_seconds: float
    rss_mb: float
    cpu_percent: float
    disk_free_gb: float
    crawler_btc_alive: bool
    crawler_eth_alive: bool
    today_periods_count: int
    today_fail_rate_pct: float
    active_rules_count: int
    evolve_state: EvolveStateEnum

class BacktestRequest(BaseModel):
    symbol: str
    date_start: str = "2026-10-01T00:00:00Z"
    date_end: str = "2026-10-11T00:00:00Z"
    min_confidence: float = 0.80
    contract_cost_pct: float = 0.03
    initial_balance: float = 10000.0
    fixed_bet_size: float = 100.0

class BacktestResponse(BaseModel):
    task_id: str
    status: str
    symbol: str
    total_trades: int
    hit_count: int
    miss_count: int
    stand_by_count: int
    win_rate: float
    net_profit: float
    max_drawdown_pct: float
    sharpe_ratio: float
    bin_accuracies: dict[str, float]
    equity_curve: list[dict[str, Any]]

class EvolveStartRequest(BaseModel):
    target_confidence: float = 0.85
    max_rounds: int = 20
    max_hours: int = 48
    min_daily_actions: float = 2.0
    symbols: list[str] = ["BTC", "ETH"]

class CurrentPeriodSnapshot(BaseModel):
    period_id: str
    symbol: str
    state: StateMachineState
    sec_offset: int
    remaining_sec: int
    current_up_odds: float
    current_down_odds: float
    odds_diff: float
    latest_price: float
    is_anomaly: bool = False
    signal: Optional[SignalLogModel] = None
