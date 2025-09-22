"""Entry point for launching the Recruitee MCP server."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from typing import Iterable, Mapping, TextIO

from .http_server import serve_http
from .server import JSONRPCError, RecruiteeMCPServer


LOGGER = logging.getLogger(__name__)


def _configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


def _parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Recruitee MCP server")
    parser.add_argument(
        "--stdio",
        action="store_true",
        help="Run the server in legacy stdio mode instead of the HTTP transport",
    )
    parser.add_argument(
        "--host",
        default=os.getenv("RECRUITEE_HTTP_HOST", "0.0.0.0"),
        help="Host interface to bind the HTTP server to (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Port for the HTTP server. Overrides the RECRUITEE_HTTP_PORT environment variable.",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging output")
    return parser.parse_args(list(argv) if argv is not None else None)


def run_stdio(
    mcp_server: RecruiteeMCPServer,
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

        output_stream.write(json.dumps(response_payload))
        output_stream.write("\n")
        output_stream.flush()


def main(argv: Iterable[str] | None = None) -> int:
    args = _parse_args(argv)
    _configure_logging(args.verbose)

    mcp_server = RecruiteeMCPServer()

    if args.stdio:
        LOGGER.info("Starting Recruitee MCP server in stdio mode")
        run_stdio(mcp_server)
        return 0

    LOGGER.info("Starting Recruitee MCP server in HTTP mode")
    serve_http(mcp_server, host=args.host, port=args.port)
    return 0


if __name__ == "__main__":  # pragma: no cover - module execution guard
    sys.exit(main())
