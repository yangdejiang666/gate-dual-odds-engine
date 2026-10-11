"""
本地存储层与表结构管理
支持 SQLite(WAL) 高并发写入与 DuckDB OLAP 分析加速
严格按第八章与第十章落地
"""

import sqlite3
import logging
from pathlib import Path
from contextlib import contextmanager
from datetime import datetime
from backend.app.config import settings

logger = logging.getLogger("Database")

CREATE_TABLES_SQL = """
-- 局结算结果主表（标签表，只用于事后验证，绝不参与特征构造杜绝未来函数）
CREATE TABLE IF NOT EXISTS period_result (
    period_id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    open_time TEXT NOT NULL,
    close_time TEXT NOT NULL,
    open_price REAL NOT NULL,
    close_price REAL NOT NULL,
    direction TEXT NOT NULL, -- UP, DOWN, FLAT
    amplitude_pct REAL NOT NULL,
    final_up_odds REAL NOT NULL,
    final_down_odds REAL NOT NULL,
    is_anomaly INTEGER DEFAULT 0,
    anomaly_type TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_period_result_symbol_time ON period_result(symbol, open_time);
CREATE INDEX IF NOT EXISTS idx_period_result_direction ON period_result(direction);

-- 秒级/降采样倍率与走势表
CREATE TABLE IF NOT EXISTS odds_tick (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    period_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    sec_offset INTEGER NOT NULL, -- 0 到 300
    up_odds REAL NOT NULL,
    down_odds REAL NOT NULL,
    odds_diff REAL NOT NULL,     -- down_odds - up_odds (正代表资金看跌，负代表看涨)
    diff_slope REAL DEFAULT 0.0,
    price REAL,
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_odds_tick_period_sec ON odds_tick(period_id, sec_offset);
CREATE INDEX IF NOT EXISTS idx_odds_tick_symbol_time ON odds_tick(symbol, timestamp);

-- 局走势形态表
CREATE TABLE IF NOT EXISTS chart_shape (
    period_id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    amplitude REAL NOT NULL,
    reversal_count INTEGER NOT NULL,
    extreme_sec INTEGER NOT NULL,
    shape_category TEXT NOT NULL, -- ONE_WAY_TREND, MID_REVERSAL, TIGHT_CONGESTION, TAIL_BURST
    normalized_series_json TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_chart_shape_cat ON chart_shape(shape_category);

-- 页面与系统异常事件表
CREATE TABLE IF NOT EXISTS page_event (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL, -- SELECTOR_MISMATCH, RECONNECT, ANOMALY_MARKET, STALL, MEMORY_HIGH
    symbol TEXT,
    period_id TEXT,
    message TEXT NOT NULL,
    snapshot_path TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_page_event_created ON page_event(created_at);

-- 规则注册与动态信誉表 (第二十三章)
CREATE TABLE IF NOT EXISTS rule_registry (
    rule_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    symbol TEXT NOT NULL,
    condition_json TEXT NOT NULL,
    sample_count INTEGER DEFAULT 0,
    win_rate REAL DEFAULT 0.5,
    confidence REAL DEFAULT 0.5,
    reputation_score REAL DEFAULT 70.0,
    status TEXT DEFAULT 'ACTIVE', -- ACTIVE, WATCH, RETIRED, BLOCKED
    consecutive_fails INTEGER DEFAULT 0,
    recent_100_win_rate REAL,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- 决策信号流水表 (用于事后核算与信誉打分)
CREATE TABLE IF NOT EXISTS signal_log (
    signal_id TEXT PRIMARY KEY,
    period_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    sec_offset INTEGER NOT NULL,
    action TEXT NOT NULL, -- CALL, PUT, STAND_BY
    raw_prob REAL NOT NULL,
    calibrated_conf REAL NOT NULL,
    rule_hits TEXT,       -- JSON Array of rule_id
    cross_state TEXT,     -- CO_DIRECTIONAL, LEAD_LAG, DIVERGENT
    advice TEXT NOT NULL,
    actual_direction TEXT,
    outcome TEXT,         -- HIT, MISS, STAND_BY
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_signal_log_period ON signal_log(period_id, symbol);
CREATE INDEX IF NOT EXISTS idx_signal_log_outcome ON signal_log(outcome);

-- 模型与校准版本仓库
CREATE TABLE IF NOT EXISTS model_version (
    version_id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    features_json TEXT NOT NULL,
    val_auc REAL,
    val_brier REAL,
    calibration_method TEXT,
    model_blob_path TEXT,
    is_active INTEGER DEFAULT 0
);

-- 自动长跑迭代清单表 (第二十七章)
CREATE TABLE IF NOT EXISTS run_manifest (
    run_id TEXT PRIMARY KEY,
    round_index INTEGER NOT NULL,
    timestamp TEXT NOT NULL,
    sample_start_period TEXT,
    sample_end_period TEXT,
    sample_size INTEGER NOT NULL,
    metric_version TEXT NOT NULL,
    factors_used_json TEXT NOT NULL,
    auc REAL,
    brier REAL,
    target_bin_accuracy REAL,
    wilson_lower_bound REAL,
    daily_action_rate REAL,
    action_decision TEXT NOT NULL,
    notes TEXT
);

-- 真实市场外部参考表 (第二十六章扩展)
CREATE TABLE IF NOT EXISTS market_tick (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    price REAL NOT NULL,
    funding_rate REAL,
    volume_24h REAL
);

-- 聚合预算表 (第十六章/第二十章：前端秒开保障)
CREATE TABLE IF NOT EXISTS agg_hourly_summary (
    agg_hour TEXT NOT NULL,
    symbol TEXT NOT NULL,
    total_periods INTEGER DEFAULT 0,
    up_count INTEGER DEFAULT 0,
    down_count INTEGER DEFAULT 0,
    avg_amplitude REAL DEFAULT 0.0,
    hit_rate_80_plus REAL DEFAULT 0.0,
    PRIMARY KEY (agg_hour, symbol)
);
"""

class DatabaseManager:
    def __init__(self, db_path: Path = settings.SQLITE_PATH):
        self.db_path = db_path
        self._init_sqlite()

    def _init_sqlite(self):
        """开启 SQLite WAL 模式并初始化表结构"""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        try:
            cursor = conn.cursor()
            # 开启写前日志模式支持读写并发 (第八章)
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute("PRAGMA synchronous=NORMAL;")
            cursor.execute("PRAGMA temp_store=MEMORY;")
            cursor.execute("PRAGMA cache_size=-64000;") # 64MB cache
            cursor.executescript(CREATE_TABLES_SQL)
            conn.commit()
            logger.info(f"SQLite WAL 数据库初始化成功: {self.db_path}")
        except Exception as e:
            logger.error(f"初始化数据库失败: {e}")
            raise
        finally:
            conn.close()

    @contextmanager
    def get_connection(self):
        """获取 SQLite 连接上下文管理器"""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def execute_read(self, query: str, params: tuple = ()) -> list[dict]:
        """线程安全的只读查询"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def execute_write(self, query: str, params: tuple = ()) -> int:
        """单条写入操作"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.lastrowid

    def execute_batch_write(self, query: str, params_list: list[tuple]) -> int:
        """批量写入（解耦抓取与磁盘IO）"""
        if not params_list:
            return 0
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(query, params_list)
            return cursor.rowcount

    def vacuum_database(self):
        """重整碎片与释放未分配页 (第十章 10.4)"""
        with self.get_connection() as conn:
            conn.execute("VACUUM;")
            logger.info("数据库 VACUUM 维护完成")

db = DatabaseManager()
