"""
WebSocket 实时推送服务
严格按第十六章 16.3 节、第二十章 20.1 节落地：
1. 增量包推送: 只推当前局增量包 (倒计时 + 倍率差序列增量 + 信号)
2. 序号防丢: 带 seq 递增序号，前端检测跳号主动补洞
3. 多端广播: 桌面决策弹窗与 Web 控制台同源同步
"""

import json
import asyncio
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import List

logger = logging.getLogger("WebSocket")

router = APIRouter(tags=["WebSocket"])

class ConnectionManager:
    def __init__(self):
        self.live_connections: List[WebSocket] = []
        self.evolve_connections: List[WebSocket] = []
        self.seq: int = 0

    async def connect_live(self, websocket: WebSocket):
        await websocket.accept()
        self.live_connections.append(websocket)

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
            # 保持保活读取客户端心跳 ping
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
