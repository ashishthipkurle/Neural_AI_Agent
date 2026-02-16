from __future__ import annotations

from fastapi import APIRouter

from agent.core.conformance_checker import ConformanceChecker


conformance_router = APIRouter(prefix="/architecture", tags=["architecture"])


@conformance_router.get("/conformance")
async def architecture_conformance() -> dict:
    checker = ConformanceChecker('.')
    return checker.report()
