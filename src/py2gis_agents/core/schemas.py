"""Stable Pydantic contracts exposed by the Python and MCP interfaces."""

from __future__ import annotations

from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing_extensions import Self

T = TypeVar("T")
InfrastructureMode = Literal["minimal", "extended"]
InfrastructureAnalysisType = Literal[
    "social_infrastructure",
    "transport_infrastructure",
]


class ToolError(BaseModel):
    """Stable, agent-friendly representation of an execution error."""

    code: str
    message: str
    retryable: bool = False


class ToolResult(BaseModel, Generic[T]):
    """Common result envelope returned by both public tools."""

    model_config = ConfigDict(extra="forbid")

    ok: bool
    data: T | None = None
    error: ToolError | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_result_state(self) -> Self:
        if self.ok and self.error is not None:
            raise ValueError("A successful result cannot contain an error")
        if not self.ok and self.error is None:
            raise ValueError("A failed result must contain an error")
        return self

    @classmethod
    def success(
        cls,
        data: T,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> ToolResult[T]:
        return cls(ok=True, data=data, metadata=metadata or {})

    @classmethod
    def failure(
        cls,
        error: ToolError,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> ToolResult[T]:
        return cls(ok=False, error=error, metadata=metadata or {})


class InfrastructureInput(BaseModel):
    """Validated arguments shared by social and transport analysis."""

    model_config = ConfigDict(extra="forbid")

    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    radius_m: int = Field(default=5000, ge=1, le=50_000)
    mode: InfrastructureMode = "minimal"
    limit_per_category: int = Field(default=5, ge=1, le=20)


class SearchPoint(BaseModel):
    """WGS84 search centre."""

    latitude: float
    longitude: float


class DgisRubric(BaseModel):
    """One 2GIS category attached to an object."""

    id: str | None = None
    name: str | None = None


class InfrastructureObject(BaseModel):
    """Normalized 2GIS object suitable for an LLM response."""

    id: str | None = None
    name: str | None = None
    full_name: str | None = None
    address_name: str | None = None
    type: str | None = None
    subtype: str | None = None
    purpose_name: str | None = None
    route_type: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    distance_to_search_point_m: float | None = None
    distance_method: Literal[
        "2gis",
        "haversine_to_search_point",
        "unavailable",
    ]
    rubrics: list[DgisRubric] = Field(default_factory=list)
    matched_queries: list[str] = Field(default_factory=list)


class InfrastructureCategoryResult(BaseModel):
    """One semantic category and its nearest matching objects."""

    key: str
    name: str
    queries: list[str]
    provider_reported_count: int | None = None
    loaded_item_count: int = 0
    filtered_out_count: int = 0
    object_count: int = 0
    returned_count: int = 0
    source_truncated: bool = False
    response_limited: bool = False
    nearest_distance_m: float | None = None
    objects: list[InfrastructureObject] = Field(default_factory=list)


class InfrastructureGroupResult(BaseModel):
    """Named group containing related infrastructure categories."""

    key: str
    name: str
    object_membership_count: int
    categories: list[InfrastructureCategoryResult]


class AnalysisIssue(BaseModel):
    """Non-fatal problem that makes an otherwise useful report partial."""

    code: str
    message: str
    category: str | None = None
    query: str | None = None
    retryable: bool = False


class InfrastructureSummary(BaseModel):
    """Compact completeness and volume counters."""

    planned_search_queries: int
    total_api_requests: int
    successful_api_requests: int
    failed_api_requests: int
    source_truncated_queries: int
    loaded_item_count: int
    filtered_out_item_count: int
    unique_object_count: int
    returned_object_count: int
    category_count: int


class InfrastructureAnalysisData(BaseModel):
    """Normalized response shared by both 2GIS analysis tools."""

    analysis_type: InfrastructureAnalysisType
    point: SearchPoint
    radius_m: int
    mode: InfrastructureMode
    limit_per_category: int
    complete: bool
    source_complete: bool
    response_limited: bool
    summary: InfrastructureSummary
    groups: list[InfrastructureGroupResult]
    issues: list[AnalysisIssue] = Field(default_factory=list)
