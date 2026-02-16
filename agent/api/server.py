from __future__ import annotations

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from agent.api.routes import conformance_router, mission_router
from agent.api.websocket import WebSocketHub


app = FastAPI(title="Autonomous Agent API", version="3.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(mission_router, prefix="/api")
app.include_router(conformance_router, prefix="/api")

hub = WebSocketHub()


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok", "service": "autonomous-agent"}


@app.websocket("/api/ws")
async def ws(socket: WebSocket) -> None:
    await hub.connect(socket)
    try:
        while True:
            _ = await socket.receive_text()
    except WebSocketDisconnect:
        hub.disconnect(socket)
