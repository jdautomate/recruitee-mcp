"""Entry point for launching the Recruitee MCP server."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from typing import Any, Iterable, Mapping, TextIO

from .client import RecruiteeClient
from .config import RecruiteeConfig
from .http_server import serve_http
from .server import JSONRPCError, RecruiteeMCPServer


LOGGER = logging.getLogger(__name__)


def _configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


def _create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Recruitee MCP server")
    parser.add_argument(
        "--stdio",
        action="store_true",
        help="Run the server using the stdio transport instead of HTTP",
    )
    parser.add_argument(
        "--host",
        default=os.getenv("RECRUITEE_HTTP_HOST", "0.0.0.0"),
        help="Host interface for the HTTP server (defaults to RECRUITEE_HTTP_HOST or 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Port for the HTTP server. Overrides the RECRUITEE_HTTP_PORT environment variable.",
    )
    parser.add_argument("--company-id", help="Recruitee company identifier", default=None)
    parser.add_argument("--api-token", help="Recruitee API token", default=None)
    parser.add_argument(
        "--base-url",
        help="Override the Recruitee API base URL (defaults to https://openvpn.recruitee.com)",
        default=None,
    )
    parser.add_argument(
        "--timeout",
        type=float,
        help="Request timeout in seconds (defaults to 30)",
        default=None,
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging output")
    return parser


def _build_config_from_args(args: argparse.Namespace) -> RecruiteeConfig:
    env = dict(os.environ)
    if args.company_id:
        env["RECRUITEE_COMPANY_ID"] = args.company_id
    if args.api_token:
        env["RECRUITEE_API_TOKEN"] = args.api_token
    if args.base_url:
        env["RECRUITEE_BASE_URL"] = args.base_url
    if args.timeout is not None:
        env["RECRUITEE_TIMEOUT"] = str(args.timeout)
    return RecruiteeConfig.from_env(env)


class _ServerTransportAdapter:
    """Adapter that provides ``handle_json_rpc`` for legacy transport helpers."""

    def __init__(self, server: RecruiteeMCPServer) -> None:
        self._server = server

    def handle_json_rpc(self, payload: Mapping[str, Any]) -> Mapping[str, Any] | None:
        dispatch = getattr(self._server, "_dispatch", None)
        if dispatch is None:
            raise AttributeError("RecruiteeMCPServer does not provide a JSON-RPC dispatch method")
        return dispatch(payload)

    def __getattr__(self, item: str) -> Any:
        return getattr(self._server, item)


def _ensure_transport_server(server: RecruiteeMCPServer) -> Any:
    if hasattr(server, "handle_json_rpc"):
        return server
    return _ServerTransportAdapter(server)


def run_stdio(
    mcp_server: Any,
    *,
    input_stream: TextIO = sys.stdin,
    output_stream: TextIO = sys.stdout,
) -> None:
    """Simple stdio transport that consumes JSON-RPC payloads line-by-line."""

    for line in input_stream:
        line = line.strip()
        if not line:
            continue

        try:
            request_payload = json.loads(line)
        except json.JSONDecodeError:
            response_payload = JSONRPCError(-32700, "Parse error").to_response(None)
        else:
            request_id = request_payload.get("id") if isinstance(request_payload, Mapping) else None
            try:
                response_payload = mcp_server.handle_json_rpc(request_payload)
            except JSONRPCError as exc:
                response_payload = exc.to_response(request_id)
            except Exception as exc:  # pragma: no cover - defensive logging
                LOGGER.exception("Unhandled exception while processing stdio JSON-RPC request")
                response_payload = JSONRPCError(-32603, "Internal error", data=str(exc)).to_response(request_id)

        if response_payload is None:
            continue

        output_stream.write(json.dumps(response_payload))
        output_stream.write("\n")
        output_stream.flush()


def main(argv: Iterable[str] | None = None) -> int:
    parser = _create_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    _configure_logging(args.verbose)

    try:
        config = _build_config_from_args(args)
    except ValueError as exc:
        parser.error(str(exc))

    client = RecruiteeClient.from_config(config)
    server = RecruiteeMCPServer(client)
    transport_server = _ensure_transport_server(server)

    if args.stdio:
        LOGGER.info("Starting Recruitee MCP server in stdio mode")
        run_stdio(transport_server)
        return 0

    LOGGER.info("Starting Recruitee MCP server in HTTP mode")
    serve_http(transport_server, host=args.host, port=args.port)
    return 0


if __name__ == "__main__":  # pragma: no cover - module execution guard
    sys.exit(main())
