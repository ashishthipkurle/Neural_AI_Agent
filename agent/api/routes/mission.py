from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from agent.runtime import RUNTIME


mission_router = APIRouter(prefix="/missions", tags=["missions"])


class MissionRequest(BaseModel):
    goal: str
    metadata: Optional[Dict[str, Any]] = None


@mission_router.post("/run")
async def run_mission(req: MissionRequest) -> Dict[str, Any]:
    return await RUNTIME.run_goal(req.goal, req.metadata or {})


@mission_router.get("/running")
async def list_running() -> Dict[str, Any]:
    return {"running": RUNTIME.list_running_missions()}
