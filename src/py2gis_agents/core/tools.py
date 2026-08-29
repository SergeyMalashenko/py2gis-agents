"""High-level social and transport infrastructure analyzers."""

from __future__ import annotations

import json
import math
from collections.abc import Sequence
from typing import Any, Literal

from typing_extensions import Self

from .client import DgisClient, DgisHttpClient
from .errors import exception_to_tool_error, sanitize_error_message
from .schemas import (
    AnalysisIssue,
    DgisRubric,
    InfrastructureAnalysisData,
    InfrastructureAnalysisType,
    InfrastructureCategoryResult,
    InfrastructureGroupResult,
    InfrastructureInput,
    InfrastructureObject,
    InfrastructureSummary,
    SearchPoint,
    ToolResult,
)
from .taxonomy import (
    SOCIAL_INFRASTRUCTURE_CATEGORIES,
    TRANSPORT_INFRASTRUCTURE_CATEGORIES,
    InfrastructureCategory,
)

PAGE_SIZE = 10
MAX_PAGES_PER_QUERY = 5
MAX_ITEMS_PER_QUERY = 100
MAX_TOTAL_ITEMS = 1000

RESULT_METADATA: dict[str, Any] = {
    "provider": "2GIS Search API",
    "source": "catalog.api.2gis.com",
    "distance_note": (
        "Distances are straight-line distances from the search point, not route "
        "distances or distances from a land-parcel boundary"
    ),
    "filter_note": (
        "Objects are filtered by 2GIS rubrics; text fallback is used for map "
        "objects without rubrics"
    ),
}


class DgisTools:
    """Framework-neutral implementation behind the two public MCP tools."""

    def __init__(self, client: DgisClient | None = None) -> None:
        self._client = client or DgisHttpClient()
        self._owns_client = client is None

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    async def close(self) -> None:
        if self._owns_client:
            await self._client.close()

    async def analyze_social_infrastructure(
        self,
        *,
        latitude: float,
        longitude: float,
        radius_m: int = 5000,
        mode: str = "minimal",
        limit_per_category: int = 5,
    ) -> ToolResult[InfrastructureAnalysisData]:
        """Find social services around one WGS84 point."""

        return await self._run_public_analysis(
            analysis_type="social_infrastructure",
            categories=SOCIAL_INFRASTRUCTURE_CATEGORIES,
            latitude=latitude,
            longitude=longitude,
            radius_m=radius_m,
            mode=mode,
            limit_per_category=limit_per_category,
        )

    async def analyze_transport_infrastructure(
        self,
        *,
        latitude: float,
        longitude: float,
        radius_m: int = 5000,
        mode: str = "minimal",
        limit_per_category: int = 5,
    ) -> ToolResult[InfrastructureAnalysisData]:
        """Find public-transport objects and transport hubs around one point."""

        return await self._run_public_analysis(
            analysis_type="transport_infrastructure",
            categories=TRANSPORT_INFRASTRUCTURE_CATEGORIES,
            latitude=latitude,
            longitude=longitude,
            radius_m=radius_m,
            mode=mode,
            limit_per_category=limit_per_category,
        )

    async def _run_public_analysis(
        self,
        *,
        analysis_type: InfrastructureAnalysisType,
        categories: Sequence[InfrastructureCategory],
        latitude: float,
        longitude: float,
        radius_m: int,
        mode: str,
        limit_per_category: int,
    ) -> ToolResult[InfrastructureAnalysisData]:
        try:
            arguments = InfrastructureInput.model_validate(
                {
                    "latitude": latitude,
                    "longitude": longitude,
                    "radius_m": radius_m,
                    "mode": mode,
                    "limit_per_category": limit_per_category,
                }
            )
            return await self._analyze(analysis_type, categories, arguments)
        except Exception as exc:  # noqa: BLE001 - stable public boundary
            return ToolResult.failure(
                exception_to_tool_error(exc),
                metadata=dict(RESULT_METADATA),
            )

    async def _analyze(
        self,
        analysis_type: InfrastructureAnalysisType,
        categories: Sequence[InfrastructureCategory],
        arguments: InfrastructureInput,
    ) -> ToolResult[InfrastructureAnalysisData]:
        api_point = f"{arguments.longitude},{arguments.latitude}"
        search_point = SearchPoint(
            latitude=arguments.latitude,
            longitude=arguments.longitude,
        )
        planned_queries = sum(
            len(category.queries(arguments.mode)) for category in categories
        )
        total_requests = 0
        successful_requests = 0
        failed_requests = 0
        source_truncated_queries = 0
        loaded_total = 0
        filtered_total = 0
        issues: list[AnalysisIssue] = []
        group_order: list[str] = []
        groups: dict[str, dict[str, Any]] = {}
        all_identities: set[str] = set()
        returned_identities: set[str] = set()
        first_failure: Exception | None = None

        for category in categories:
            if category.group_key not in groups:
                group_order.append(category.group_key)
                groups[category.group_key] = {
                    "key": category.group_key,
                    "name": category.group_name,
                    "categories": [],
                }

            objects: dict[str, InfrastructureObject] = {}
            category_loaded = 0
            category_filtered = 0
            category_reported: int | None = None
            category_source_truncated = False

            for query in category.queries(arguments.mode):
                page = 1
                query_loaded = 0
                query_reported: int | None = None
                query_truncated = False

                while True:
                    if page > MAX_PAGES_PER_QUERY:
                        query_truncated = True
                        self._add_limit_issue(
                            issues,
                            category,
                            query,
                            "provider_page_limit",
                            "The internal page limit was reached before the query was complete",
                        )
                        break
                    remaining_query = MAX_ITEMS_PER_QUERY - query_loaded
                    remaining_total = MAX_TOTAL_ITEMS - loaded_total
                    if remaining_query <= 0 or remaining_total <= 0:
                        query_truncated = True
                        code = (
                            "per_query_item_limit"
                            if remaining_query <= 0
                            else "total_item_limit"
                        )
                        self._add_limit_issue(
                            issues,
                            category,
                            query,
                            code,
                            "An internal item limit was reached before the query was complete",
                        )
                        break
                    page_size = min(PAGE_SIZE, remaining_query, remaining_total)
                    total_requests += 1
                    try:
                        payload = await self._client.search_places(
                            query,
                            point=api_point,
                            radius_m=arguments.radius_m,
                            page_size=page_size,
                            page=page,
                            object_type=category.object_type,
                        )
                    except Exception as exc:  # noqa: BLE001 - partial result boundary
                        failed_requests += 1
                        first_failure = first_failure or exc
                        public_error = exception_to_tool_error(exc)
                        issues.append(
                            AnalysisIssue(
                                code=public_error.code,
                                message=sanitize_error_message(public_error.message),
                                category=category.key,
                                query=query,
                                retryable=public_error.retryable,
                            )
                        )
                        break

                    successful_requests += 1
                    items = _response_items(payload)
                    reported = _response_total(payload)
                    if reported is not None:
                        query_reported = reported
                    category_loaded += len(items)
                    query_loaded += len(items)
                    loaded_total += len(items)

                    for item in items:
                        if not _matches_category(item, category):
                            category_filtered += 1
                            filtered_total += 1
                            continue
                        identity, normalized = _normalize_item(
                            item,
                            search_point=search_point,
                            query=query,
                        )
                        existing = objects.get(identity)
                        if existing is None:
                            objects[identity] = normalized
                        else:
                            _merge_object(existing, normalized)

                    if not items:
                        if query_reported is not None and query_loaded < query_reported:
                            query_truncated = True
                        break
                    if query_reported is not None and query_loaded >= query_reported:
                        break
                    if len(items) < page_size:
                        if query_reported is not None and query_loaded < query_reported:
                            query_truncated = True
                        break
                    page += 1

                if query_reported is not None:
                    category_reported = (category_reported or 0) + query_reported
                    if query_loaded < query_reported:
                        query_truncated = True
                if query_truncated:
                    source_truncated_queries += 1
                    category_source_truncated = True

            sorted_objects = sorted(
                objects.items(),
                key=lambda pair: (
                    pair[1].distance_to_search_point_m is None,
                    pair[1].distance_to_search_point_m or 0.0,
                    pair[1].name or "",
                    pair[0],
                ),
            )
            returned = sorted_objects[: arguments.limit_per_category]
            response_limited = len(sorted_objects) > len(returned)
            all_identities.update(objects)
            returned_identities.update(identity for identity, _ in returned)
            groups[category.group_key]["categories"].append(
                InfrastructureCategoryResult(
                    key=category.key,
                    name=category.name,
                    queries=list(category.queries(arguments.mode)),
                    provider_reported_count=category_reported,
                    loaded_item_count=category_loaded,
                    filtered_out_count=category_filtered,
                    object_count=len(sorted_objects),
                    returned_count=len(returned),
                    source_truncated=category_source_truncated,
                    response_limited=response_limited,
                    nearest_distance_m=(
                        returned[0][1].distance_to_search_point_m if returned else None
                    ),
                    objects=[item for _, item in returned],
                )
            )

        if successful_requests == 0 and first_failure is not None:
            return ToolResult.failure(
                exception_to_tool_error(first_failure),
                metadata=dict(RESULT_METADATA),
            )

        group_results = [
            InfrastructureGroupResult(
                key=groups[key]["key"],
                name=groups[key]["name"],
                categories=groups[key]["categories"],
                object_membership_count=sum(
                    category.object_count for category in groups[key]["categories"]
                ),
            )
            for key in group_order
        ]
        response_limited = any(
            category.response_limited
            for group in group_results
            for category in group.categories
        )
        source_complete = failed_requests == 0 and source_truncated_queries == 0
        data = InfrastructureAnalysisData(
            analysis_type=analysis_type,
            point=search_point,
            radius_m=arguments.radius_m,
            mode=arguments.mode,
            limit_per_category=arguments.limit_per_category,
            complete=source_complete and not response_limited,
            source_complete=source_complete,
            response_limited=response_limited,
            summary=InfrastructureSummary(
                planned_search_queries=planned_queries,
                total_api_requests=total_requests,
                successful_api_requests=successful_requests,
                failed_api_requests=failed_requests,
                source_truncated_queries=source_truncated_queries,
                loaded_item_count=loaded_total,
                filtered_out_item_count=filtered_total,
                unique_object_count=len(all_identities),
                returned_object_count=len(returned_identities),
                category_count=len(categories),
            ),
            groups=group_results,
            issues=issues,
        )
        return ToolResult.success(data, metadata=dict(RESULT_METADATA))

    @staticmethod
    def _add_limit_issue(
        issues: list[AnalysisIssue],
        category: InfrastructureCategory,
        query: str,
        code: str,
        message: str,
    ) -> None:
        issues.append(
            AnalysisIssue(
                code=code,
                message=message,
                category=category.key,
                query=query,
            )
        )


def _response_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    result = payload.get("result")
    items = result.get("items") if isinstance(result, dict) else None
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def _response_total(payload: dict[str, Any]) -> int | None:
    result = payload.get("result")
    total = result.get("total") if isinstance(result, dict) else None
    try:
        return int(total) if total is not None else None
    except (TypeError, ValueError):
        return None


def _text(value: object) -> str:
    return str(value or "").casefold().replace("ё", "е")


def _optional_text(value: object) -> str | None:
    return None if value in (None, "") else str(value)


def _optional_float(value: object) -> float | None:
    if value in (None, ""):
        return None
    if not isinstance(value, (str, int, float)):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _contains_term(value: object, terms: Sequence[str]) -> bool:
    normalized = _text(value)
    return any(_text(term) in normalized for term in terms)


def _rubrics(item: dict[str, Any]) -> list[DgisRubric]:
    raw = item.get("rubrics")
    if not isinstance(raw, list):
        return []
    return [
        DgisRubric(
            id=_optional_text(rubric.get("id")),
            name=_optional_text(rubric.get("name")),
        )
        for rubric in raw
        if isinstance(rubric, dict)
    ]


def _matches_category(
    item: dict[str, Any], category: InfrastructureCategory
) -> bool:
    item_type = _text(item.get("type"))
    if item_type in category.disallowed_types:
        return False
    if category.accept_station_types and item_type in {"station", "station_platform"}:
        return True
    rubrics = _rubrics(item)
    if rubrics:
        return any(
            _contains_term(rubric.name, category.rubric_terms) for rubric in rubrics
        )
    fallback_value = " ".join(
        str(item.get(key) or "")
        for key in (
            "name",
            "full_name",
            "purpose_name",
            "subtype",
            "route_type",
            "route_types",
        )
    )
    terms = category.fallback_terms or category.rubric_terms
    return not terms or _contains_term(fallback_value, terms)


def _item_identity(item: dict[str, Any]) -> str:
    if item.get("id") not in (None, ""):
        return f"2gis:{item['id']}"
    point = item.get("point") if isinstance(item.get("point"), dict) else {}
    fallback = (
        item.get("name"),
        item.get("full_name"),
        item.get("address_name"),
        point.get("lon"),
        point.get("lat"),
    )
    return "fallback:" + json.dumps(fallback, ensure_ascii=False, separators=(",", ":"))


def _normalize_item(
    item: dict[str, Any],
    *,
    search_point: SearchPoint,
    query: str,
) -> tuple[str, InfrastructureObject]:
    point = item.get("point") if isinstance(item.get("point"), dict) else {}
    longitude = _optional_float(point.get("lon"))
    latitude = _optional_float(point.get("lat"))
    if longitude is not None and not -180 <= longitude <= 180:
        longitude = None
    if latitude is not None and not -90 <= latitude <= 90:
        latitude = None

    distance = _optional_float(item.get("distance"))
    context = item.get("context")
    if distance is None and isinstance(context, dict):
        distance = _optional_float(context.get("distance"))
    distance_method: Literal[
        "2gis", "haversine_to_search_point", "unavailable"
    ] = "2gis"
    if distance is None and longitude is not None and latitude is not None:
        distance = _haversine_distance_m(
            search_point.latitude,
            search_point.longitude,
            latitude,
            longitude,
        )
        distance_method = "haversine_to_search_point"
    if distance is None:
        distance_method = "unavailable"

    return _item_identity(item), InfrastructureObject(
        id=_optional_text(item.get("id")),
        name=_optional_text(item.get("name")),
        full_name=_optional_text(item.get("full_name")),
        address_name=_optional_text(item.get("address_name")),
        type=_optional_text(item.get("type")),
        subtype=_optional_text(item.get("subtype")),
        purpose_name=_optional_text(item.get("purpose_name")),
        route_type=_optional_text(item.get("route_type")),
        latitude=latitude,
        longitude=longitude,
        distance_to_search_point_m=round(distance, 1) if distance is not None else None,
        distance_method=distance_method,
        rubrics=_rubrics(item),
        matched_queries=[query],
    )


def _merge_object(existing: InfrastructureObject, candidate: InfrastructureObject) -> None:
    for query in candidate.matched_queries:
        if query not in existing.matched_queries:
            existing.matched_queries.append(query)
    if candidate.distance_to_search_point_m is not None and (
        existing.distance_to_search_point_m is None
        or candidate.distance_to_search_point_m < existing.distance_to_search_point_m
    ):
        existing.distance_to_search_point_m = candidate.distance_to_search_point_m
        existing.distance_method = candidate.distance_method


def _haversine_distance_m(
    latitude1: float,
    longitude1: float,
    latitude2: float,
    longitude2: float,
) -> float:
    earth_radius_m = 6_371_008.8
    phi1 = math.radians(latitude1)
    phi2 = math.radians(latitude2)
    delta_phi = phi2 - phi1
    delta_lambda = math.radians(longitude2 - longitude1)
    value = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    return 2 * earth_radius_m * math.asin(min(1.0, math.sqrt(value)))
