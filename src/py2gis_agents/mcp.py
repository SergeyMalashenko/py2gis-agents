"""Model Context Protocol server exposing two high-level 2GIS tools."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from typing import Any, Literal

from pydantic import ValidationError

from .core import DgisTools, InfrastructureAnalysisData, ToolResult

DEFAULT_INSTRUCTIONS = (
    "Use dgis_analyze_social_infrastructure for education, healthcare, emergency, "
    "everyday-service, leisure, and environmental-quality objects. Use "
    "dgis_analyze_transport_infrastructure for public-transport stops, railway "
    "stations and platforms, bus stations, airports, ports, railway facilities, "
    "and logistics terminals. Both tools search around a caller-provided WGS84 "
    "point. Distances are straight-line distances from that point, not route "
    "distances or distances from a parcel boundary. Treat provider results as "
    "potentially incomplete and inspect completeness flags. Do not invent a "
    "cadastral contour: obtain its search point from the acquisition pipeline."
)


class MCPDependencyError(RuntimeError):
    """Raised when the optional MCP SDK is unavailable."""


def _load_mcp_server_class() -> type[Any]:
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise MCPDependencyError(
            "MCP support is not installed. Install it with "
            "`pip install 'py2gis-agents[mcp]'`."
        ) from exc
    return FastMCP


def create_mcp_server(
    tools: DgisTools | None = None,
    *,
    name: str = "py2gis",
    instructions: str = DEFAULT_INSTRUCTIONS,
    host: str = "127.0.0.1",
    port: int = 8003,
    streamable_http_path: str = "/mcp",
    stateless_http: bool = True,
    json_response: bool = True,
) -> Any:
    """Create a FastMCP server with exactly two infrastructure tools."""

    if not 1 <= port <= 65535:
        raise ValueError("port must be between 1 and 65535")
    if not streamable_http_path.startswith("/"):
        raise ValueError("streamable_http_path must start with '/'")

    service = tools or DgisTools()
    server_class = _load_mcp_server_class()
    server = server_class(
        name,
        instructions=instructions,
        host=host,
        port=port,
        streamable_http_path=streamable_http_path,
        stateless_http=stateless_http,
        json_response=json_response,
    )

    @server.tool()
    async def dgis_analyze_social_infrastructure(
        latitude: float,
        longitude: float,
        radius_m: int = 5000,
        mode: Literal["minimal", "extended"] = "minimal",
        limit_per_category: int = 5,
    ) -> ToolResult[InfrastructureAnalysisData]:
        """Analyze social infrastructure around a WGS84 point.

        Args:
            latitude: Search-centre latitude between -90 and 90.
            longitude: Search-centre longitude between -180 and 180.
            radius_m: Search radius from 1 to 50000 metres.
            mode: ``minimal`` for one quota-conscious query per category or
                ``extended`` for broader coverage.
            limit_per_category: Nearest objects returned per category, from 1
                to 20. Completeness counters still describe all loaded matches.
        """

        return await service.analyze_social_infrastructure(
            latitude=latitude,
            longitude=longitude,
            radius_m=radius_m,
            mode=mode,
            limit_per_category=limit_per_category,
        )

    @server.tool()
    async def dgis_analyze_transport_infrastructure(
        latitude: float,
        longitude: float,
        radius_m: int = 5000,
        mode: Literal["minimal", "extended"] = "minimal",
        limit_per_category: int = 5,
    ) -> ToolResult[InfrastructureAnalysisData]:
        """Analyze public transport and transport hubs around a WGS84 point.

        Args:
            latitude: Search-centre latitude between -90 and 90.
            longitude: Search-centre longitude between -180 and 180.
            radius_m: Search radius from 1 to 50000 metres.
            mode: ``minimal`` for one quota-conscious query per category or
                ``extended`` for broader coverage.
            limit_per_category: Nearest objects returned per category, from 1
                to 20. Completeness counters still describe all loaded matches.
        """

        return await service.analyze_transport_infrastructure(
            latitude=latitude,
            longitude=longitude,
            radius_m=radius_m,
            mode=mode,
            limit_per_category=limit_per_category,
        )

    return server


async def _run_server(server: Any, service: DgisTools, transport: str) -> None:
    """Run FastMCP and close its shared HTTP client at process shutdown."""

    try:
        if transport == "stdio":
            await server.run_stdio_async()
        elif transport == "streamable-http":
            await server.run_streamable_http_async()
        else:  # pragma: no cover - argparse restricts public values
            raise ValueError(f"Unsupported MCP transport: {transport}")
    finally:
        await service.close()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="py2gis-mcp",
        description="Run the two 2GIS infrastructure tools as an MCP server.",
    )
    parser.add_argument(
        "--transport",
        choices=("stdio", "streamable-http"),
        default="stdio",
        help="MCP transport (default: stdio)",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8003)
    parser.add_argument("--path", default="/mcp", dest="streamable_http_path")
    parser.add_argument(
        "--stateful-http",
        action="store_true",
        help="Keep MCP HTTP sessions instead of stateless request handling",
    )
    parser.add_argument(
        "--sse-response",
        action="store_true",
        help="Stream HTTP responses as SSE instead of a single JSON body",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    """Run the server from the ``py2gis-mcp`` console command."""

    args = _build_parser().parse_args(argv)
    try:
        import anyio

        service = DgisTools()
        server = create_mcp_server(
            service,
            host=args.host,
            port=args.port,
            streamable_http_path=args.streamable_http_path,
            stateless_http=not args.stateful_http,
            json_response=not args.sse_response,
        )
    except ValidationError as exc:
        raise SystemExit(
            "2GIS API key is not configured. Set PY2GIS_API_KEY in the "
            "environment or in the current directory's .env file."
        ) from exc
    except (ImportError, MCPDependencyError) as exc:
        raise SystemExit(
            "MCP support is not installed. Install it with "
            "`pip install 'py2gis-agents[mcp]'`."
        ) from exc
    anyio.run(_run_server, server, service, args.transport)


if __name__ == "__main__":  # pragma: no cover
    main()
