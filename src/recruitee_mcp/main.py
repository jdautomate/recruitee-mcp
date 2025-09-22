"""Entry point for launching the Recruitee MCP server."""
"""Entry point for running the Recruitee MCP server."""

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
import os
import sys
from typing import Dict

from .client import RecruiteeClient, RecruiteeError
from .config import RecruiteeConfig
from .server import RecruiteeMCPServer


def _build_config_from_args(args: argparse.Namespace) -> RecruiteeConfig:
    env: Dict[str, str] = dict(os.environ)
    if args.company_id:
        env["RECRUITEE_COMPANY_ID"] = args.company_id
    if args.api_token:
        env["RECRUITEE_API_TOKEN"] = args.api_token
    if args.base_url:
        env["RECRUITEE_BASE_URL"] = args.base_url
    if args.timeout:
        env["RECRUITEE_TIMEOUT"] = str(args.timeout)
    return RecruiteeConfig.from_env(env)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Recruitee MCP server.")
    parser.add_argument("--company-id", help="Recruitee company identifier")
    parser.add_argument("--api-token", help="Recruitee API token")
    parser.add_argument(
        "--base-url",
        help="Override the Recruitee API base URL (defaults to https://api.recruitee.com)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        help="Request timeout in seconds (defaults to 30)",
    )
    parsed = parser.parse_args(argv)

    try:
        config = _build_config_from_args(parsed)
    except ValueError as exc:
        parser.error(str(exc))
        return 2

    client = RecruiteeClient.from_config(config)
    server = RecruiteeMCPServer(client)

    try:
        server.run()
    except RecruiteeError as exc:
        print(f"Server terminated due to Recruitee error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 0

    return 0


if __name__ == "__main__":  # pragma: no cover - manual execution
    raise SystemExit(main())
