import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import json

from core.metrics import websocket_connections

router = APIRouter()

_connections: list[WebSocket] = []


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    _connections.append(websocket)
    websocket_connections.inc()
    try:
        while True:
            # Mantem a conexao viva com ping a cada 30s
            await asyncio.sleep(30)
            await websocket.send_text(json.dumps({"type": "ping"}))
    except WebSocketDisconnect:
        _connections.remove(websocket)
        websocket_connections.dec()


async def broadcast(data: dict):
    payload = json.dumps({"type": "scan_result", "data": data})
    dead = []
    for ws in _connections:
        try:
            await ws.send_text(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _connections.remove(ws)
