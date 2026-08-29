from __future__ import annotations

from collections.abc import Callable
from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest

from py2gis_agents.core import DgisTools
from py2gis_agents.mcp import _build_parser, _run_server, create_mcp_server

from .fakes import FakeDgisClient


class FakeFastMCP:
    def __init__(self, name: str, **kwargs: Any) -> None:
        self.name = name
        self.kwargs = kwargs
        self.tools: dict[str, Callable[..., Any]] = {}

    def tool(self) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(function: Callable[..., Any]) -> Callable[..., Any]:
            self.tools[function.__name__] = function
            return function

        return decorator


def test_mcp_registers_exactly_two_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("py2gis_agents.mcp._load_mcp_server_class", lambda: FakeFastMCP)

    server = create_mcp_server(DgisTools(FakeDgisClient()))

    assert list(server.tools) == [
        "dgis_analyze_social_infrastructure",
        "dgis_analyze_transport_infrastructure",
    ]
    assert server.kwargs["stateless_http"] is True
    assert server.kwargs["json_response"] is True
    assert server.kwargs["port"] == 8003


async def test_mcp_tool_returns_structured_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("py2gis_agents.mcp._load_mcp_server_class", lambda: FakeFastMCP)
    server = create_mcp_server(DgisTools(FakeDgisClient()))

    result = await server.tools["dgis_analyze_social_infrastructure"](56.0, 44.0)

    assert result.ok
    assert result.data is not None
    assert result.data.analysis_type == "social_infrastructure"


@pytest.mark.filterwarnings("ignore:Field 'lifespan' has an incomplete definition")
async def test_real_streamable_http_call_returns_structured_content() -> None:
    pytest.importorskip("mcp.server.fastmcp")

    app = create_mcp_server(DgisTools(FakeDgisClient())).streamable_http_app()
    headers = {
        "accept": "application/json, text/event-stream",
        "content-type": "application/json",
    }
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://127.0.0.1:8003",
        ) as http,
    ):
        initialized = await http.post(
            "/mcp",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "pytest", "version": "1"},
                },
            },
        )
        called = await http.post(
            "/mcp",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "dgis_analyze_transport_infrastructure",
                    "arguments": {"latitude": 56.0, "longitude": 44.0},
                },
            },
        )

    assert initialized.status_code == 200
    assert called.status_code == 200
    structured = called.json()["result"]["structuredContent"]
    assert structured["ok"] is True
    assert structured["data"]["summary"]["category_count"] == 7


@pytest.mark.parametrize("transport", ["stdio", "streamable-http"])
async def test_runner_closes_service(transport: str) -> None:
    class FakeServer:
        def __init__(self) -> None:
            self.calls: list[str] = []

        async def run_stdio_async(self) -> None:
            self.calls.append("stdio")

        async def run_streamable_http_async(self) -> None:
            self.calls.append("streamable-http")

    server = FakeServer()
    service = DgisTools(FakeDgisClient())
    service.close = AsyncMock(wraps=service.close)  # type: ignore[method-assign]

    await _run_server(server, service, transport)

    assert server.calls == [transport]
    service.close.assert_awaited_once_with()


def test_cli_defaults_to_stdio_and_port_8003() -> None:
    args = _build_parser().parse_args([])

    assert args.transport == "stdio"
    assert args.host == "127.0.0.1"
    assert args.port == 8003


@pytest.mark.parametrize("port", [0, 65536])
def test_invalid_mcp_port_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    port: int,
) -> None:
    monkeypatch.setattr("py2gis_agents.mcp._load_mcp_server_class", lambda: FakeFastMCP)

    with pytest.raises(ValueError, match="port"):
        create_mcp_server(DgisTools(FakeDgisClient()), port=port)
