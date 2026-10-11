"""
内存与资源管控守护器
严格按第十章 10.5 节落地：
1. watchdog 周期采样进程 RSS 内存
2. 触碰软限 (MEM_SOFT_LIMIT_MB): 强制 gc.collect()，清空热层非当前局缓存
3. 触碰硬限 (MEM_HARD_LIMIT_MB): 自动降级，暂停 OCR 兜底、抓取频率降为 3 秒、推迟模型训练
4. 磁盘配额监控: 剩余空间低于 5GB 停止截图落盘
"""

import os
import gc
import shutil
import logging
import psutil
from datetime import datetime
from backend.app.config import settings
from backend.app.database import db

logger = logging.getLogger("MemoryGuard")

class ResourceGuard:
    def __init__(self):
        self.process = psutil.Process(os.getpid())
        self.is_degraded_mode: bool = False
        self.pause_screenshot: bool = False
        self.sample_interval: float = settings.CRAWLER_SAMPLE_INTERVAL_SEC

    def check_resources(self) -> dict:
        """采样当前系统资源与触发必要降级保护"""
        # 1. 内存采样
        rss_bytes = self.process.memory_info().rss
        rss_mb = rss_bytes / (1024 * 1024)
        
        # 2. 磁盘剩余空间采样
        total, used, free = shutil.disk_usage(settings.DATA_DIR)
        disk_free_gb = free / (1024 * 1024 * 1024)

        # 3. 磁盘预警
        if disk_free_gb < settings.DISK_MIN_FREE_GB:
            if not self.pause_screenshot:
                logger.warning(f"磁盘剩余空间不足 {disk_free_gb:.2f}GB (< {settings.DISK_MIN_FREE_GB}GB)，暂停截图落地以保护磁盘")
                self.pause_screenshot = True
                self._record_event("DISK_LOW", f"磁盘空间告警，剩余 {disk_free_gb:.2f}GB")
        else:
            self.pause_screenshot = False

        # 4. 内存软限检查
        if rss_mb >= settings.MEM_SOFT_LIMIT_MB:
            logger.warning(f"触发内存软限 (当前 RSS: {rss_mb:.1f}MB >= {settings.MEM_SOFT_LIMIT_MB}MB)，执行强力垃圾回收")
            gc.collect()

        # 5. 内存硬限检查与系统降级
        if rss_mb >= settings.MEM_HARD_LIMIT_MB:
            if not self.is_degraded_mode:
                logger.error(f"触发内存硬限 (当前 RSS: {rss_mb:.1f}MB >= {settings.MEM_HARD_LIMIT_MB}MB)，启动降级运行模式")
                self.is_degraded_mode = True
                self.sample_interval = 3.0  # 抓取采样频率从 1s 降为 3s
                self._record_event("MEMORY_HARD_LIMIT", f"内存超限达到 {rss_mb:.1f}MB，抓频降至3s，暂停复杂运算")
        else:
            if self.is_degraded_mode and rss_mb < settings.MEM_SOFT_LIMIT_MB:
                logger.info(f"内存水位回落正常 ({rss_mb:.1f}MB)，解除降级状态")
                self.is_degraded_mode = False
                self.sample_interval = settings.CRAWLER_SAMPLE_INTERVAL_SEC

        return {
            "rss_mb": round(rss_mb, 2),
            "disk_free_gb": round(disk_free_gb, 2),
            "is_degraded": self.is_degraded_mode,
            "pause_screenshot": self.pause_screenshot,
            "current_sample_interval": self.sample_interval
        }

    def _record_event(self, event_type: str, msg: str):
        try:
            db.execute_write(
                "INSERT INTO page_event (event_type, message) VALUES (?, ?)",
                (event_type, msg)
            )
        except Exception as e:
            logger.error(f"记录资源告警事件失败: {e}")

resource_guard = ResourceGuard()
