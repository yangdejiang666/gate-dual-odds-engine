"""
WebSocket 实时推送与数据摄入服务
严格按第十六章 16.3 节、第二十章 20.1 节与真实 Gate 现场数据落地：
1. /ws/live: 增量广播 (倒计时 + 倍率/份额价 + 盘口多空比 + 信号)
2. /ws/ingest: 真实现场数据摄入通道 (支持探针脚本/CDP/Playwright 双向交互)
3. 毫秒级触发联动分析与级联决策漏斗，实时反哺弹窗
"""

import json
import asyncio
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import List, Dict, Any, Optional

from backend.app.services.engine.coordinator import engine_coordinator
from backend.app.database import db

logger = logging.getLogger("WebSocket")

router = APIRouter(tags=["WebSocket"])

class ConnectionManager:
    def __init__(self):
        self.live_connections: List[WebSocket] = []
        self.evolve_connections: List[WebSocket] = []
        self.ingest_connections: List[WebSocket] = []
        self.seq: int = 0
        
        # 局内实时最新读数缓存
        self.latest_cache: Dict[str, Any] = {
            "period_id": "",
            "remaining_sec": 180,
            "btc": {"target_price": 83008.45, "current_price": 83022.04, "price_diff": 13.59, "call_price": 0.98, "put_price": 0.03, "b_ratio": "B 68.27%", "odds_diff": -0.95},
            "eth": {"target_price": 2502.24, "current_price": 2502.31, "price_diff": 0.07, "call_price": 0.78, "put_price": 0.23, "b_ratio": "B 34.07%", "odds_diff": -0.55},
            "signal": {"action": "STAND_BY", "calibrated_conf": 0.80, "advice": "正在等待高把握时机...", "cross_state": "CO_DIRECTIONAL"}
        }

    async def connect_live(self, websocket: WebSocket):
        await websocket.accept()
        self.live_connections.append(websocket)
        # 连上立即推送当前最新状态
        await websocket.send_text(json.dumps({"seq": self.seq, **self.latest_cache}, ensure_ascii=False))

    def disconnect_live(self, websocket: WebSocket):
        if websocket in self.live_connections:
            self.live_connections.remove(websocket)

    async def connect_evolve(self, websocket: WebSocket):
        await websocket.accept()
        self.evolve_connections.append(websocket)

    def disconnect_evolve(self, websocket: WebSocket):
        if websocket in self.evolve_connections:
            self.evolve_connections.remove(websocket)

    async def broadcast_live(self, data: dict):
        self.seq += 1
        payload = {"seq": self.seq, **data}
        self.latest_cache = payload
        text = json.dumps(payload, ensure_ascii=False)
        for conn in list(self.live_connections):
            try:
                await conn.send_text(text)
            except Exception:
                self.disconnect_live(conn)

    async def broadcast_evolve(self, data: dict):
        text = json.dumps(data, ensure_ascii=False)
        for conn in list(self.evolve_connections):
            try:
                await conn.send_text(text)
            except Exception:
                self.disconnect_evolve(conn)

ws_manager = ConnectionManager()

@router.websocket("/ws/live")
async def websocket_live_endpoint(websocket: WebSocket):
    await ws_manager.connect_live(websocket)
    try:
        while True:
            msg = await websocket.receive_text()
            if msg == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect_live(websocket)
    except Exception:
        ws_manager.disconnect_live(websocket)

@router.websocket("/ws/evolve")
async def websocket_evolve_endpoint(websocket: WebSocket):
    await ws_manager.connect_evolve(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect_evolve(websocket)
    except Exception:
        ws_manager.disconnect_evolve(websocket)

@router.websocket("/ws/ingest")
async def websocket_ingest_endpoint(websocket: WebSocket):
    """
    现场数据摄入通道：
    接收页面探针脚本或爬虫发来的实时现场数据并实时计算与广播
    """
    await websocket.accept()
    logger.info("已建立现场数据摄入通道 (Gate 页面实时探针已连接)")
    try:
        while True:
            raw_text = await websocket.receive_text()
            try:
                payload = json.loads(raw_text)
                await _process_ingest_payload(payload, websocket)
            except Exception as e:
                logger.error(f"处理摄入数据异常: {e}")
    except WebSocketDisconnect:
        logger.info("现场数据摄入连接断开")
    except Exception:
        pass

@router.post("/api/ingest")
async def http_ingest_endpoint(payload: dict):
    """HTTP 摄入接口：供浏览器 CSP 拦截 WebSocket 时的优雅降级"""
    try:
        computed = await _process_ingest_payload(payload, None)
        return {"status": "ok", "signal": computed.get("signal", {})}
    except Exception as e:
        logger.error(f"HTTP 摄入处理失败: {e}")
        return {"status": "error", "message": str(e)}

async def _process_ingest_payload(payload: dict, client_ws: Optional[WebSocket] = None) -> dict:
    """由计算协同器调度各层计算并广播最新决策"""
    computed = engine_coordinator.process_tick(payload)
    
    # 广播给桌面弹窗与控制台
    await ws_manager.broadcast_live(computed)

    # 若有直接摄入的 WebSocket，向探针回传决策反馈
    if client_ws:
        sig = computed.get("signal", {})
        await client_ws.send_text(json.dumps({
            "type": "SIGNAL_FEEDBACK",
            "action": sig.get("action", "STAND_BY"),
            "calibrated_conf": sig.get("calibrated_conf", 0.5),
            "advice": sig.get("advice", "保持观望"),
            "cross_state": sig.get("cross_state", "UNKNOWN")
        }, ensure_ascii=False))
        
    return computed
