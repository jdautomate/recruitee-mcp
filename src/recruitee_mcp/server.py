"""Core JSON-RPC server logic for the Recruitee MCP implementation."""

from __future__ import annotations

import json
import logging
import sys
from dataclasses import dataclass
from typing import Any, Callable, Dict, Mapping

from .client import (
    RecruiteeAPIError,
    RecruiteeClient,
    RecruiteeConnectionError,
    RecruiteeError,
)

try:  # pragma: no cover - only exercised when optional dependency is present
    from mcp.server.constants import PROTOCOL_VERSION as MCP_PROTOCOL_VERSION
except (ImportError, AttributeError):  # pragma: no cover - executed in minimal install
    MCP_PROTOCOL_VERSION = "0.5"

LOGGER = logging.getLogger(__name__)

JsonDict = Dict[str, Any]


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


@dataclass(slots=True)
class _Tool:
    name: str
    description: str
    handler: Callable[[Mapping[str, Any]], Mapping[str, Any]]
    schema: Mapping[str, Any]


class RecruiteeMCPServer:
    """Serve a limited subset of the Model Context Protocol for Recruitee."""

    def __init__(self, client: RecruiteeClient | None = None):
        self._client: RecruiteeClient | None = client
        self._tools: Dict[str, _Tool] = {
            "search_offers": _Tool(
                name="search_offers",
                description="List job offers for the company.",
                handler=self._tool_search_offers,
                schema={
                    "type": "object",
                    "properties": {
                        "state": {
                            "type": ["string", "null"],
                            "description": "Filter by offer state (published, archived, etc).",
                        },
                        "limit": {
                            "type": ["integer", "null"],
                            "description": "Maximum number of offers to return.",
                        },
                        "include_description": {
                            "type": ["boolean", "null"],
                            "description": "Include offer descriptions in the payload.",
                        },
                    },
                },
            ),
            "get_offer": _Tool(
                name="get_offer",
                description="Fetch a single offer by identifier.",
                handler=self._tool_get_offer,
                schema={
                    "type": "object",
                    "required": ["offer_id"],
                    "properties": {
                        "offer_id": {
                            "type": ["integer", "string"],
                            "description": "Offer identifier.",
                        }
                    },
                },
            ),
            "search_candidates": _Tool(
                name="search_candidates",
                description="Search candidates by text query.",
                handler=self._tool_search_candidates,
                schema={
                    "type": "object",
                    "required": ["query"],
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Query string that matches candidate fields.",
                        },
                        "page": {
                            "type": ["integer", "null"],
                        },
                        "limit": {
                            "type": ["integer", "null"],
                        },
                    },
                },
            ),
            "get_candidate": _Tool(
                name="get_candidate",
                description="Fetch a candidate by identifier.",
                handler=self._tool_get_candidate,
                schema={
                    "type": "object",
                    "required": ["candidate_id"],
                    "properties": {
                        "candidate_id": {
                            "type": ["integer", "string"],
                        }
                    },
                },
            ),
            "create_candidate": _Tool(
                name="create_candidate",
                description="Create a new candidate record.",
                handler=self._tool_create_candidate,
                schema={
                    "type": "object",
                    "required": ["first_name", "last_name", "email"],
                    "properties": {
                        "first_name": {"type": "string"},
                        "last_name": {"type": "string"},
                        "email": {"type": "string"},
                        "phone": {"type": ["string", "null"]},
                        "source": {"type": ["string", "null"]},
                        "offer_id": {"type": ["integer", "null"]},
                        "pipeline_id": {"type": ["integer", "null"]},
                        "notes": {"type": ["string", "null"]},
                        "custom_fields": {"type": ["object", "null"]},
                    },
                },
            ),
        }

    # ------------------------------------------------------------------
    # JSON-RPC entry points
    # ------------------------------------------------------------------
    def handle_json_rpc(self, request: Mapping[str, Any]) -> JsonDict:
        """Validate and dispatch a JSON-RPC request."""

        if not isinstance(request, Mapping):
            raise JSONRPCError(-32600, "Invalid Request", data="Request must be an object")

        if request.get("jsonrpc") != "2.0":
            raise JSONRPCError(-32600, "Invalid Request", data="jsonrpc must be '2.0'")

        if "id" not in request:
            raise JSONRPCError(-32600, "Invalid Request", data="Missing id")

        if request.get("id") is None:
            raise JSONRPCError(-32600, "Invalid Request", data="id must not be null")

        method_name = request.get("method")
        if not isinstance(method_name, str) or not method_name:
            raise JSONRPCError(
                -32600,
                "Invalid Request",
                data="Method must be a non-empty string",
            )

        raw_params = request.get("params")
        if raw_params is None:
            params: Mapping[str, Any] = {}
        elif isinstance(raw_params, Mapping):
            params = raw_params
        else:
            raise JSONRPCError(-32602, "Invalid params", data="Params must be an object")

        normalized_request: Dict[str, Any] = dict(request)
        normalized_request["params"] = params

        return self._dispatch(normalized_request)

    def run(self, *, input_stream=None, output_stream=None) -> None:
        input_stream = input_stream or sys.stdin
        output_stream = output_stream or sys.stdout
        for line in input_stream:
            payload = line.strip()
            if not payload:
                continue
            try:
                request = json.loads(payload)
            except json.JSONDecodeError:
                response = JSONRPCError(-32700, "Parse error").to_response(None)
                self._write_json(output_stream, response)
                continue

            try:
                response = self.handle_json_rpc(request)
            except JSONRPCError as exc:
                request_id = request.get("id") if isinstance(request, Mapping) else None
                response = exc.to_response(request_id)
            except Exception as exc:  # pragma: no cover - defensive safeguard
                LOGGER.exception("Unhandled exception while processing JSON-RPC request")
                request_id = request.get("id") if isinstance(request, Mapping) else None
                response = JSONRPCError(-32603, "Internal error", data=str(exc)).to_response(
                    request_id
                )

            if response is None:
                continue

            self._write_json(output_stream, response)

    # ------------------------------------------------------------------
    # Protocol handlers
    # ------------------------------------------------------------------
    def _dispatch(self, request: Mapping[str, Any]) -> JsonDict:
        method = request.get("method")
        request_id = request.get("id")
        params = request.get("params") or {}

        try:
            if method == "initialize":
                return self._response(request_id, self._handle_initialize())
            if method == "ping":
                return self._response(request_id, "pong")
            if method == "list_resources":
                return self._response(request_id, self._handle_list_resources(params))
            if method == "read_resource":
                return self._response(request_id, self._handle_read_resource(params))
            if method == "list_tools":
                return self._response(request_id, self._handle_list_tools())
            if method == "call_tool":
                return self._response(request_id, self._handle_call_tool(params))
            return self._error(request_id, -32601, f"Unknown method: {method}")
        except RecruiteeAPIError as exc:
            return self._error(request_id, exc.status_code or -32000, str(exc))
        except RecruiteeConnectionError as exc:
            return self._error(request_id, -32002, str(exc))
        except RecruiteeError as exc:
            return self._error(request_id, -32001, str(exc))
        except Exception as exc:  # pragma: no cover - defensive safeguard
            return self._error(request_id, -32603, f"Unexpected error: {exc}")

    def _handle_initialize(self) -> JsonDict:
        return {
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "serverInfo": {
                "name": "recruitee-mcp",
                "version": "0.1.0",
            },
            "capabilities": {
                "resources": {
                    "list": True,
                    "read": True,
                },
                "tools": {
                    "list": True,
                    "call": True,
                },
            },
        }

    def _handle_list_resources(self, params: Mapping[str, Any]) -> JsonDict:
        _ = params  # unused but kept for interface completeness
        return {
            "resources": [
                {
                    "uri": "recruitee://offers",
                    "name": "Job offers",
                    "description": "Published job offers for the configured company.",
                },
                {
                    "uri": "recruitee://pipelines",
                    "name": "Pipelines",
                    "description": "Recruiting pipelines and stages.",
                },
            ]
        }

    def _handle_read_resource(self, params: Mapping[str, Any]) -> JsonDict:
        uri = params.get("uri")
        client = self._require_client()
        if uri == "recruitee://offers":
            data = client.list_offers(include_description=True)
        elif uri == "recruitee://pipelines":
            data = client.list_pipelines()
        else:
            raise RecruiteeError(f"Unsupported resource URI: {uri}")

        return {"contents": [self._json_content(data)]}

    def _handle_list_tools(self) -> JsonDict:
        return {
            "tools": [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "inputSchema": tool.schema,
                }
                for tool in self._tools.values()
            ]
        }

    def _handle_call_tool(self, params: Mapping[str, Any]) -> JsonDict:
        name = params.get("name")
        arguments = params.get("arguments") or {}
        tool = self._tools.get(name)
        if not tool:
            raise RecruiteeError(f"Unknown tool: {name}")

        result = tool.handler(arguments)
        return {"content": [self._json_content(result)]}

    # ------------------------------------------------------------------
    # Tool handlers
    # ------------------------------------------------------------------
    def _tool_search_offers(self, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        client = self._require_client()
        return client.list_offers(
            state=arguments.get("state"),
            limit=arguments.get("limit"),
            include_description=bool(arguments.get("include_description")),
        )

    def _tool_get_offer(self, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        offer_id = arguments.get("offer_id")
        if offer_id is None:
            raise RecruiteeError("'offer_id' is required")
        return self._require_client().get_offer(offer_id)

    def _tool_search_candidates(self, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        query = arguments.get("query")
        if not query:
            raise RecruiteeError("'query' is required")
        client = self._require_client()
        return client.search_candidates(
            query=query,
            page=arguments.get("page"),
            limit=arguments.get("limit"),
        )

    def _tool_get_candidate(self, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        candidate_id = arguments.get("candidate_id")
        if candidate_id is None:
            raise RecruiteeError("'candidate_id' is required")
        return self._require_client().get_candidate(candidate_id)

    def _tool_create_candidate(self, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        required = ["first_name", "last_name", "email"]
        missing = [field for field in required if not arguments.get(field)]
        if missing:
            raise RecruiteeError(f"Missing required fields: {', '.join(missing)}")
        client = self._require_client()
        return client.create_candidate(
            first_name=arguments["first_name"],
            last_name=arguments["last_name"],
            email=arguments["email"],
            phone=arguments.get("phone"),
            source=arguments.get("source"),
            offer_id=arguments.get("offer_id"),
            pipeline_id=arguments.get("pipeline_id"),
            notes=arguments.get("notes"),
            custom_fields=arguments.get("custom_fields"),
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _json_content(self, data: Mapping[str, Any]) -> JsonDict:
        return {
            "type": "application/json",
            "data": data,
        }

    @staticmethod
    def _response(request_id: Any, result: Any) -> JsonDict:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": result,
        }

    @staticmethod
    def _error(request_id: Any, code: int, message: str) -> JsonDict:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": code,
                "message": message,
            },
        }

    @staticmethod
    def _write_json(output_stream, payload: Mapping[str, Any]) -> None:
        output_stream.write(json.dumps(payload))
        output_stream.write("\n")
        output_stream.flush()

    def _require_client(self) -> RecruiteeClient:
        if self._client is None:
            raise RuntimeError("Recruitee client is not configured")
        return self._client


__all__ = ["JSONRPCError", "RecruiteeMCPServer"]
