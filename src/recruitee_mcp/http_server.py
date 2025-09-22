"""HTTP transport for the Recruitee MCP JSON-RPC server."""

from __future__ import annotations

import json
import logging
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from typing import Any, Optional, Type

from .server import JSONRPCError, RecruiteeMCPServer

LOGGER = logging.getLogger(__name__)

DEFAULT_HTTP_PORT = 8080
HTTP_PORT_ENV_VAR = "RECRUITEE_HTTP_PORT"
HEALTH_CHECK_PATH = "/health"


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    """Threaded HTTP server with `serve_forever` support."""

    daemon_threads = True
    allow_reuse_address = True


def _resolve_port(port: Optional[int]) -> int:
    if port is not None:
        return port

    env_value = os.getenv(HTTP_PORT_ENV_VAR)
    if not env_value:
        return DEFAULT_HTTP_PORT

    try:
        parsed = int(env_value)
    except ValueError:
        LOGGER.warning(
            "Invalid value for %s: %s. Falling back to %s",
            HTTP_PORT_ENV_VAR,
            env_value,
            DEFAULT_HTTP_PORT,
        )
        return DEFAULT_HTTP_PORT

    if not (0 <= parsed <= 65535):
        LOGGER.warning(
            "Port from %s is out of range (%s). Falling back to %s",
            HTTP_PORT_ENV_VAR,
            parsed,
            DEFAULT_HTTP_PORT,
        )
        return DEFAULT_HTTP_PORT

    return parsed


def _create_handler(mcp_server: RecruiteeMCPServer) -> Type[BaseHTTPRequestHandler]:
    class JSONRPCRequestHandler(BaseHTTPRequestHandler):
        server_version = "RecruiteeMCPHTTP/1.0"

        def do_POST(self) -> None:  # noqa: N802 - required signature
            content_length_header = self.headers.get("Content-Length")
            if content_length_header is None:
                self.send_error(HTTPStatus.LENGTH_REQUIRED, "Missing Content-Length header")
                return

            try:
                content_length = int(content_length_header)
            except ValueError:
                self.send_error(HTTPStatus.BAD_REQUEST, "Invalid Content-Length header")
                return

            body = self.rfile.read(content_length)
            try:
                request_payload = json.loads(body)
            except json.JSONDecodeError:
                response_payload = JSONRPCError(-32700, "Parse error").to_response(None)
                self._write_json_response(response_payload)
                return

            response_payload = self._dispatch_request(request_payload)
            self._write_json_response(response_payload)

        def do_GET(self) -> None:  # noqa: N802 - required signature
            if self.path == HEALTH_CHECK_PATH:
                self._write_json_response({"status": "ok"})
                return

            self.send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Only POST is supported")

        def _dispatch_request(self, payload: Any) -> dict[str, Any]:
            if not isinstance(payload, dict):
                return JSONRPCError(-32600, "Invalid Request", data="Request must be an object").to_response(None)

            request_id = payload.get("id")
            try:
                return mcp_server.handle_json_rpc(payload)
            except JSONRPCError as exc:
                return exc.to_response(request_id)
            except Exception as exc:  # pragma: no cover - defensive logging
                LOGGER.exception("Unhandled exception while processing HTTP JSON-RPC request")
                return JSONRPCError(-32603, "Internal error", data=str(exc)).to_response(request_id)

        def _write_json_response(self, payload: dict[str, Any]) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A003 - BaseHTTPRequestHandler API
            LOGGER.info("%s - %s", self.address_string(), format % args)

    return JSONRPCRequestHandler


def create_http_server(
    mcp_server: RecruiteeMCPServer,
    *,
    host: str = "0.0.0.0",
    port: Optional[int] = None,
) -> ThreadingHTTPServer:
    resolved_port = _resolve_port(port)
    handler_cls = _create_handler(mcp_server)
    server = ThreadingHTTPServer((host, resolved_port), handler_cls)
    return server


def serve_http(
    mcp_server: RecruiteeMCPServer,
    *,
    host: str = "0.0.0.0",
    port: Optional[int] = None,
) -> None:
    server = create_http_server(mcp_server, host=host, port=port)
    actual_host, actual_port = server.server_address[:2]
    LOGGER.info("Starting HTTP JSON-RPC server on %s:%s", actual_host, actual_port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:  # pragma: no cover - manual interrupt
        LOGGER.info("Received shutdown signal. Stopping HTTP server.")
    finally:
        server.server_close()


__all__ = [
    "DEFAULT_HTTP_PORT",
    "HTTP_PORT_ENV_VAR",
    "HEALTH_CHECK_PATH",
    "ThreadingHTTPServer",
    "create_http_server",
    "serve_http",
]
