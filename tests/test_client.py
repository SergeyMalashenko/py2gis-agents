from __future__ import annotations

import httpx
import pytest

from py2gis_agents.core.client import DgisHttpClient
from py2gis_agents.core.errors import DgisServiceError


async def test_client_builds_bounded_places_request() -> None:
    captured: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            200,
            json={"meta": {"code": 200}, "result": {"items": [], "total": 0}},
        )

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = DgisHttpClient(
        api_key="secret",
        api_url="https://catalog.example",
        http_client=http,
    )

    await client.search_places(
        "автостанция",
        point="43.6,56.0",
        radius_m=5000,
        page_size=10,
        page=2,
        object_type="station,branch",
    )

    request = captured[0]
    assert request.url.path == "/3.0/items"
    assert request.url.params["q"] == "автостанция"
    assert request.url.params["location"] == "43.6,56.0"
    assert request.url.params["page"] == "2"
    assert request.url.params["type"] == "station,branch"
    assert request.url.params["key"] == "secret"
    await http.aclose()


async def test_application_item_not_found_is_normal_empty_result() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "meta": {
                    "code": 404,
                    "error": {"type": "itemNotFound", "message": "not found"},
                }
            },
        )

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = DgisHttpClient(
        api_key="secret",
        api_url="https://catalog.example",
        http_client=http,
    )

    payload = await client.search_places(
        "нет объекта",
        point="43.6,56.0",
        radius_m=1000,
        page_size=10,
        page=1,
    )

    assert payload["meta"]["code"] == 404
    await http.aclose()


@pytest.mark.parametrize(
    ("status", "code", "retryable"),
    [(401, "authorization_error", False), (429, "rate_limited", True)],
)
async def test_http_errors_are_mapped_without_response_body(
    status: int,
    code: str,
    retryable: bool,
) -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, text="upstream details")

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = DgisHttpClient(
        api_key="secret",
        api_url="https://catalog.example",
        http_client=http,
    )

    with pytest.raises(DgisServiceError) as caught:
        await client.search_places(
            "школа",
            point="43.6,56.0",
            radius_m=1000,
            page_size=10,
            page=1,
        )

    assert caught.value.code == code
    assert caught.value.retryable is retryable
    assert "secret" not in str(caught.value)
    await http.aclose()
