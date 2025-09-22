"""Core JSON-RPC server logic for the Recruitee MCP implementation."""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Iterable, Mapping


LOGGER = logging.getLogger(__name__)


class JSONRPCError(Exception):
    """Exception representing a JSON-RPC 2.0 error response."""

    def __init__(self, code: int, message: str, *, data: Any | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data

    def to_response(self, request_id: Any) -> Dict[str, Any]:
        error: Dict[str, Any] = {"code": self.code, "message": self.message}
        if self.data is not None:
            error["data"] = self.data
        return {"jsonrpc": "2.0", "error": error, "id": request_id}


class RecruiteeMCPServer:
    """Minimal JSON-RPC server used for dispatching MCP commands."""

    def __init__(self) -> None:
        self._methods: Dict[str, Callable[..., Any]] = {}
        # Register built-in methods.
        self.register_method("ping", self.ping)

    def register_method(self, name: str, func: Callable[..., Any]) -> None:
        """Register a callable for a JSON-RPC method name."""

        if not name:
            raise ValueError("Method name must be a non-empty string.")
        self._methods[name] = func
        LOGGER.debug("Registered JSON-RPC method %s", name)

    def ping(self) -> str:
        """Simple health-check endpoint."""

        return "pong"

    def handle_json_rpc(self, request: Mapping[str, Any]) -> Dict[str, Any]:
        """Dispatch a JSON-RPC request and return a response payload."""

        if not isinstance(request, Mapping):
            raise JSONRPCError(-32600, "Invalid Request", data="Request must be an object")

        if request.get("jsonrpc") != "2.0":
            raise JSONRPCError(-32600, "Invalid Request", data="jsonrpc must be '2.0'")

        if "id" not in request:
            raise JSONRPCError(-32600, "Invalid Request", data="Missing id")

        method_name = request.get("method")
        if not isinstance(method_name, str) or not method_name:
            raise JSONRPCError(-32600, "Invalid Request", data="Method must be a non-empty string")

        method = self._methods.get(method_name)
        if method is None:
            raise JSONRPCError(-32601, "Method not found")

        params = request.get("params", [])
        try:
            result = self._invoke_method(method, params)
        except JSONRPCError:
            raise
        except Exception as exc:  # pragma: no cover - defensive logging
            LOGGER.exception("Unhandled exception calling method %s", method_name)
            raise JSONRPCError(-32603, "Internal error", data=str(exc)) from exc

        return {"jsonrpc": "2.0", "result": result, "id": request["id"]}

    def _invoke_method(self, method: Callable[..., Any], params: Any) -> Any:
        """Call the provided method with validated parameters."""

        if params is None:
            return method()

        if isinstance(params, Iterable) and not isinstance(params, (str, bytes, Mapping)):
            return method(*params)

        if isinstance(params, Mapping):
            return method(**params)

        raise JSONRPCError(-32602, "Invalid params")


__all__ = ["JSONRPCError", "RecruiteeMCPServer"]
