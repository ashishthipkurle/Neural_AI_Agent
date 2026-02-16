import pytest

from agent.runtime import RUNTIME


@pytest.mark.asyncio
async def test_mission_pipeline_executes_end_to_end():
    result = await RUNTIME.run_goal("Research and code architecture report", {"user_approved": True})
    assert "mission_id" in result
    assert result["status"] in {"completed", "failed", "blocked"}
    assert "results" in result
