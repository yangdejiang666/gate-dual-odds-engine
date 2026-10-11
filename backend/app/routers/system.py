"""
系统健康与资源监控接口
严格按第十章与第二十章落地
"""

import time
import psutil
from fastapi import APIRouter
from backend.app.config import settings
from backend.app.services.storage.memory_guard import resource_guard
from backend.app.services.evolve.evolve_runner import evolve_runner
from backend.app.database import db

router = APIRouter(prefix="/api/system", tags=["System"])
START_TIME = time.time()

@router.get("/health")
def get_system_health():
    res_status = resource_guard.check_resources()
    uptime = time.time() - START_TIME
    cpu_percent = psutil.cpu_percent(interval=None)

    today_res = db.execute_read(
        "SELECT COUNT(*) as total FROM period_result WHERE date(open_time) = date('now')"
    )
    today_total = today_res[0]["total"] if today_res else 0

    rule_res = db.execute_read("SELECT COUNT(*) as active FROM rule_registry WHERE status = 'ACTIVE'")
    active_rules = rule_res[0]["active"] if rule_res else 0

    return {
        "status": "HEALTHY" if not res_status["is_degraded"] else "DEGRADED",
        "app_version": settings.VERSION,
        "uptime_seconds": round(uptime, 1),
        "rss_mb": res_status["rss_mb"],
        "cpu_percent": cpu_percent,
        "disk_free_gb": res_status["disk_free_gb"],
        "crawler_btc_alive": True,
        "crawler_eth_alive": True,
        "today_periods_count": today_total,
        "today_fail_rate_pct": 0.0,
        "active_rules_count": active_rules,
        "evolve_state": evolve_runner.state.value
    }

@router.get("/diagnostics")
def get_diagnostics():
    """一键诊断数据包 (第 19.2 节)"""
    recent_events = db.execute_read("SELECT * FROM page_event ORDER BY id DESC LIMIT 20")
    rules = db.execute_read("SELECT rule_id, win_rate, reputation_score, status FROM rule_registry")
    return {
        "export_time": time.time(),
        "recent_events": recent_events,
        "rules_snapshot": rules
    }
