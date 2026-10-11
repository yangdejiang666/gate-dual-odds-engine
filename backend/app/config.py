"""
系统全局配置中心
按设计方案第二、三、五、八、十、二十、二十七章落地
支持生产环境 Pydantic 校验与纯标准库自适应降级运行
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

try:
    from pydantic_settings import BaseSettings
    from pydantic import Field

    class SystemSettings(BaseSettings):
        APP_NAME: str = "Gate Dual Odds Engine"
        VERSION: str = "3.0.0"
        HOST: str = os.getenv("HOST", "127.0.0.1")  # 严格默认仅本机监听
        PORT: int = int(os.getenv("PORT", 8099))
        DEBUG: bool = False
        
        DATA_DIR: Path = BASE_DIR / "data"
        SQLITE_PATH: Path = BASE_DIR / "data" / "sqlite" / "dual_odds_hot.db"
        PARQUET_DIR: Path = BASE_DIR / "data" / "parquet"
        REPORTS_DIR: Path = BASE_DIR / "data" / "reports"
        SNAPSHOTS_DIR: Path = BASE_DIR / "data" / "snapshots"
        CHECKPOINTS_DIR: Path = BASE_DIR / "data" / "checkpoints"
        
        SYMBOLS: list[str] = ["BTC", "ETH"]
        
        HEADLESS: bool = True
        GATE_BTC_URL: str = "https://www.gate.com/zh/options/dual/BTC_USDT"
        GATE_ETH_URL: str = "https://www.gate.com/zh/options/dual/ETH_USDT"
        CRAWLER_SAMPLE_INTERVAL_SEC: float = 1.0
        HEARTBEAT_INTERVAL_SEC: int = 30
        SELECTOR_CONFIG_PATH: Path = BASE_DIR / "backend" / "app" / "services" / "crawler" / "selector_config.yaml"
        
        BROWSER_ARGS: list[str] = [
            "--disable-background-timer-throttling",
            "--disable-renderer-backgrounding",
            "--disable-backgrounding-occluded-windows",
            "--disable-features=IntensiveWakeUpThrottling",
            "--no-sandbox",
            "--disable-gpu"
        ]
        
        MEM_SOFT_LIMIT_MB: int = 800
        MEM_HARD_LIMIT_MB: int = 1200
        DISK_MIN_FREE_GB: float = 5.0
        HOT_CACHE_MAX_PERIODS: int = 6
        WARM_STORE_KEEP_PERIODS: int = 5000
        DOWNSAMPLE_MAX_POINTS: int = 40
        
        T_EARLY_SEC: int = 60
        T_WORK_SEC: int = 270
        T_CUTOFF_SEC: int = 270
        
        MIN_CONFIDENCE_THRESHOLD: float = 0.80
        MIN_SAMPLE_COUNT_FOR_SIGNAL: int = 50
        ENSEMBLE_MODEL_COUNT: int = 3
        REPUTATION_DISABLE_SCORE: float = 45.0
        CONSECUTIVE_FAIL_LIMIT: int = 4
        
        EVOLVE_CONFIDENCE_LADDER: list[float] = [0.80, 0.85, 0.88, 0.90]
        EVOLVE_MIN_EVAL_SAMPLES: int = 500
        EVOLVE_MAX_GENERALIZATION_GAP_PP: float = 5.0
        EVOLVE_MIN_DAILY_ACTIONS: float = 2.0
        
        MARKET_API_ENABLED: bool = False
        
        class Config:
            env_file = ".env"
            extra = "allow"

    settings = SystemSettings()

except ImportError:
    # 纯标准库自适应降级配置类
    class SystemSettingsFallback:
        APP_NAME: str = "Gate Dual Odds Engine"
        VERSION: str = "3.0.0"
        HOST: str = os.getenv("HOST", "127.0.0.1")
        PORT: int = int(os.getenv("PORT", 8099))
        DEBUG: bool = False
        
        DATA_DIR: Path = BASE_DIR / "data"
        SQLITE_PATH: Path = BASE_DIR / "data" / "sqlite" / "dual_odds_hot.db"
        PARQUET_DIR: Path = BASE_DIR / "data" / "parquet"
        REPORTS_DIR: Path = BASE_DIR / "data" / "reports"
        SNAPSHOTS_DIR: Path = BASE_DIR / "data" / "snapshots"
        CHECKPOINTS_DIR: Path = BASE_DIR / "data" / "checkpoints"
        
        SYMBOLS: list[str] = ["BTC", "ETH"]
        
        HEADLESS: bool = True
        GATE_BTC_URL: str = "https://www.gate.com/zh/options/dual/BTC_USDT"
        GATE_ETH_URL: str = "https://www.gate.com/zh/options/dual/ETH_USDT"
        CRAWLER_SAMPLE_INTERVAL_SEC: float = 1.0
        HEARTBEAT_INTERVAL_SEC: int = 30
        SELECTOR_CONFIG_PATH: Path = BASE_DIR / "backend" / "app" / "services" / "crawler" / "selector_config.yaml"
        
        BROWSER_ARGS: list[str] = [
            "--disable-background-timer-throttling",
            "--disable-renderer-backgrounding",
            "--disable-backgrounding-occluded-windows",
            "--disable-features=IntensiveWakeUpThrottling",
            "--no-sandbox",
            "--disable-gpu"
        ]
        
        MEM_SOFT_LIMIT_MB: int = 800
        MEM_HARD_LIMIT_MB: int = 1200
        DISK_MIN_FREE_GB: float = 5.0
        HOT_CACHE_MAX_PERIODS: int = 6
        WARM_STORE_KEEP_PERIODS: int = 5000
        DOWNSAMPLE_MAX_POINTS: int = 40
        
        T_EARLY_SEC: int = 60
        T_WORK_SEC: int = 270
        T_CUTOFF_SEC: int = 270
        
        MIN_CONFIDENCE_THRESHOLD: float = 0.80
        MIN_SAMPLE_COUNT_FOR_SIGNAL: int = 50
        ENSEMBLE_MODEL_COUNT: int = 3
        REPUTATION_DISABLE_SCORE: float = 45.0
        CONSECUTIVE_FAIL_LIMIT: int = 4
        
        EVOLVE_CONFIDENCE_LADDER: list[float] = [0.80, 0.85, 0.88, 0.90]
        EVOLVE_MIN_EVAL_SAMPLES: int = 500
        EVOLVE_MAX_GENERALIZATION_GAP_PP: float = 5.0
        EVOLVE_MIN_DAILY_ACTIONS: float = 2.0
        
        MARKET_API_ENABLED: bool = False

    settings = SystemSettingsFallback()

# 确保所有必要的数据目录存在
for d in [
    settings.DATA_DIR,
    settings.SQLITE_PATH.parent,
    settings.PARQUET_DIR,
    settings.REPORTS_DIR,
    settings.SNAPSHOTS_DIR,
    settings.CHECKPOINTS_DIR
]:
    d.mkdir(parents=True, exist_ok=True)
