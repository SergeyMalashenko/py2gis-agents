from __future__ import annotations

import pytest
from pydantic import ValidationError

from py2gis_agents.core.schemas import InfrastructureInput, ToolError, ToolResult


def test_shared_input_bounds() -> None:
    parsed = InfrastructureInput(latitude=56.0, longitude=44.0)

    assert parsed.radius_m == 5000
    assert parsed.mode == "minimal"
    assert parsed.limit_per_category == 5

    with pytest.raises(ValidationError):
        InfrastructureInput(latitude=91, longitude=44)
    with pytest.raises(ValidationError):
        InfrastructureInput(latitude=56, longitude=44, radius_m=50_001)
    with pytest.raises(ValidationError):
        InfrastructureInput(latitude=56, longitude=44, mode="wide")


def test_tool_result_enforces_success_failure_state() -> None:
    assert ToolResult.success({"value": 1}).ok
    assert not ToolResult.failure(ToolError(code="failure", message="bad")).ok

    with pytest.raises(ValidationError):
        ToolResult(ok=False)
    with pytest.raises(ValidationError):
        ToolResult(ok=True, error=ToolError(code="failure", message="bad"))
