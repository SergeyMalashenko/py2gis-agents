"""Asynchronous, framework-neutral client for the 2GIS Places endpoint."""

from __future__ import annotations

from typing import Any, Protocol

import httpx
from typing_extensions import Self

from .errors import DgisServiceError
from .settings import get_settings


class DgisClient(Protocol):
    """Client surface used by infrastructure analyzers and their tests."""

    async def search_places(
        self,
        query: str,
        *,
        point: str,
        radius_m: int,
        page_size: int,
        page: int,
        object_type: str | None = None,
    ) -> dict[str, Any]: ...

    async def close(self) -> None: ...


class DgisHttpClient:
    """2GIS Search API client that validates application-level responses."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        api_url: str | None = None,
        timeout_s: float | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        settings = None
        if api_key is None or api_url is None:
            settings = get_settings()
        if api_key is None:
            assert settings is not None
            api_key = settings.api_key
        if api_url is None:
            assert settings is not None
            api_url = settings.api_url
        self._api_key = api_key
        resolved_url = api_url
        self._api_url = resolved_url.rstrip("/")
        timeout = timeout_s if timeout_s is not None else (
            settings.timeout_s if settings is not None else 30.0
        )
        self._client = http_client or httpx.AsyncClient(timeout=timeout)
        self._owns_client = http_client is None

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

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
        params: dict[str, str | int] = {
            "q": query,
            "location": point,
            "point": point,
            "radius": radius_m,
            "sort": "distance",
            "fields": "items.point,items.rubrics,items.address",
            "page_size": page_size,
            "page": page,
            "key": self._api_key,
        }
        if object_type:
            params["type"] = object_type

        response = await self._client.get(f"{self._api_url}/3.0/items", params=params)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status in {401, 403}:
                raise DgisServiceError(
                    "authorization_error",
                    "2GIS Search API rejected the API key",
                ) from exc
            if status == 429:
                raise DgisServiceError(
                    "rate_limited",
                    "2GIS Search API rate limit was reached",
                    retryable=True,
                ) from exc
            if status >= 500:
                raise DgisServiceError(
                    "upstream_error",
                    f"2GIS Search API returned HTTP {status}",
                    retryable=True,
                ) from exc
            raise DgisServiceError(
                "upstream_request_error",
                f"2GIS Search API returned HTTP {status}",
            ) from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise DgisServiceError(
                "invalid_upstream_response",
                "2GIS Search API returned invalid JSON",
                retryable=True,
            ) from exc
        if not isinstance(payload, dict):
            raise DgisServiceError(
                "invalid_upstream_response",
                "2GIS Search API returned an invalid response object",
                retryable=True,
            )
        self._validate_application_result(payload)
        return payload

    @staticmethod
    def _validate_application_result(payload: dict[str, Any]) -> None:
        meta = payload.get("meta")
        if not isinstance(meta, dict):
            raise DgisServiceError(
                "invalid_upstream_response",
                "2GIS Search API response has no valid meta object",
                retryable=True,
            )
        try:
            code = int(meta.get("code"))
        except (TypeError, ValueError) as exc:
            raise DgisServiceError(
                "invalid_upstream_response",
                "2GIS Search API returned an invalid application code",
                retryable=True,
            ) from exc
        error = meta.get("error")
        error_type = error.get("type") if isinstance(error, dict) else None
        if code == 200 or (code == 404 and error_type == "itemNotFound"):
            return
        if code in {401, 403}:
            public_code, retryable = "authorization_error", False
        elif code == 429:
            public_code, retryable = "rate_limited", True
        elif code >= 500:
            public_code, retryable = "upstream_error", True
        else:
            public_code, retryable = "upstream_request_error", False
        raise DgisServiceError(
            public_code,
            f"2GIS Search API returned application error {code}",
            retryable=retryable,
        )
