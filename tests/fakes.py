from __future__ import annotations

from collections.abc import Callable
from typing import Any


def response(
    items: list[dict[str, Any]] | None = None,
    *,
    total: int | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {"items": items or []}
    if total is not None:
        result["total"] = total
    return {"meta": {"code": 200}, "result": result}


def item(
    item_id: str,
    name: str,
    *,
    rubric: str | None = None,
    item_type: str = "branch",
    distance: float | None = None,
    longitude: float = 43.6,
    latitude: float = 56.07,
) -> dict[str, Any]:
    value: dict[str, Any] = {
        "id": item_id,
        "name": name,
        "full_name": name,
        "address_name": "Тестовый адрес",
        "type": item_type,
        "point": {"lon": longitude, "lat": latitude},
    }
    if rubric is not None:
        value["rubrics"] = [{"id": f"rubric-{item_id}", "name": rubric}]
    if distance is not None:
        value["distance"] = distance
    return value


class FakeDgisClient:
    def __init__(
        self,
        handler: Callable[[str, int, str | None], dict[str, Any]] | None = None,
    ) -> None:
        self.handler = handler or (lambda _query, _page, _type: response(total=0))
        self.calls: list[dict[str, Any]] = []
        self.closed = False

    async def search_places(
        self,
        query: str,
        *,
        point: str,
        radius_m: int,
        page_size: int,
        page: int,
        object_type: str | None = None,
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "query": query,
                "point": point,
                "radius_m": radius_m,
                "page_size": page_size,
                "page": page,
                "object_type": object_type,
            }
        )
        return self.handler(query, page, object_type)

    async def close(self) -> None:
        self.closed = True
