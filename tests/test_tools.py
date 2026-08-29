from __future__ import annotations

import httpx

from py2gis_agents.core import DgisTools

from .fakes import FakeDgisClient, item, response


def _category(result: object, key: str):
    data = result.data  # type: ignore[attr-defined]
    return next(
        category
        for group in data.groups
        for category in group.categories
        if category.key == key
    )


async def test_social_analysis_filters_and_limits_response() -> None:
    def handler(query: str, _page: int, _type: str | None):
        if query == "школа":
            return response(
                [
                    item("school-1", "Школа №1", rubric="Школы", distance=100),
                    item(
                        "shop-1",
                        "Магазин",
                        rubric="Продуктовые магазины",
                    ),
                    item("school-2", "Школа №2", rubric="Школы", distance=200),
                ],
                total=3,
            )
        return response(total=0)

    client = FakeDgisClient(handler)
    result = await DgisTools(client).analyze_social_infrastructure(
        latitude=56.0678,
        longitude=43.6031,
        limit_per_category=1,
    )

    assert result.ok
    assert result.data is not None
    assert result.data.analysis_type == "social_infrastructure"
    education = _category(result, "education")
    assert education.object_count == 2
    assert education.returned_count == 1
    assert education.filtered_out_count == 1
    assert education.response_limited
    assert education.objects[0].name == "Школа №1"
    assert result.data.response_limited
    assert not result.data.complete
    assert result.data.summary.category_count == 11
    assert len(client.calls) == 11


async def test_transport_rejects_station_false_positive_for_airport() -> None:
    def handler(query: str, _page: int, _type: str | None):
        if query == "аэропорт":
            return response(
                [
                    item(
                        "bad-stop",
                        "Аэродром",
                        item_type="station",
                        rubric="Остановки общественного транспорта",
                    ),
                    item(
                        "airport-1",
                        "Международный аэропорт",
                        item_type="building",
                        rubric="Аэропорты",
                        distance=1250,
                    ),
                ],
                total=2,
            )
        return response(total=0)

    client = FakeDgisClient(handler)
    result = await DgisTools(client).analyze_transport_infrastructure(
        latitude=56.0,
        longitude=44.0,
    )

    assert result.ok
    airports = _category(result, "airports")
    assert airports.object_count == 1
    assert airports.filtered_out_count == 1
    assert airports.objects[0].id == "airport-1"
    assert result.data is not None
    assert result.data.summary.category_count == 7


async def test_pagination_cap_is_explicitly_reported() -> None:
    def handler(query: str, page: int, _type: str | None):
        if query == "школа":
            items = [
                item(
                    f"school-{page}-{index}",
                    f"Школа {page}-{index}",
                    rubric="Школы",
                    distance=page * 100 + index,
                )
                for index in range(10)
            ]
            return response(items, total=60)
        return response(total=0)

    result = await DgisTools(FakeDgisClient(handler)).analyze_social_infrastructure(
        latitude=56.0,
        longitude=44.0,
        limit_per_category=20,
    )

    assert result.ok
    assert result.data is not None
    education = _category(result, "education")
    assert education.loaded_item_count == 50
    assert education.object_count == 50
    assert education.source_truncated
    assert result.data.summary.source_truncated_queries == 1
    assert not result.data.source_complete
    assert any(issue.code == "provider_page_limit" for issue in result.data.issues)


async def test_invalid_arguments_use_stable_failure_envelope() -> None:
    result = await DgisTools(FakeDgisClient()).analyze_social_infrastructure(
        latitude=100,
        longitude=44,
    )

    assert not result.ok
    assert result.error is not None
    assert result.error.code == "invalid_arguments"


async def test_total_upstream_failure_returns_failure_envelope() -> None:
    def handler(_query: str, _page: int, _type: str | None):
        request = httpx.Request("GET", "https://catalog.example/3.0/items")
        raise httpx.ConnectError("connection failed", request=request)

    result = await DgisTools(FakeDgisClient(handler)).analyze_transport_infrastructure(
        latitude=56,
        longitude=44,
    )

    assert not result.ok
    assert result.error is not None
    assert result.error.code == "upstream_unavailable"
    assert result.error.retryable
