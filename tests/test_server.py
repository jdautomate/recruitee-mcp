"""Tests for the RecruiteeMCPServer JSON-RPC behaviour."""

from __future__ import annotations

from unittest.mock import MagicMock

from recruitee_mcp.server import MCP_PROTOCOL_VERSION, RecruiteeMCPServer


def build_server() -> tuple[RecruiteeMCPServer, MagicMock]:
    client = MagicMock()
    client.list_offers.return_value = {"offers": []}
    client.list_pipelines.return_value = {"pipelines": []}
    client.get_offer.return_value = {"offer": {}}
    client.search_candidates.return_value = {"candidates": []}
    client.get_candidate.return_value = {"candidate": {}}
    client.create_candidate.return_value = {"candidate": {"id": 1}}
    return RecruiteeMCPServer(client), client


def test_initialize_response_contains_capabilities() -> None:
    server, _ = build_server()
    response = server._dispatch({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    assert response["result"]["protocolVersion"] == MCP_PROTOCOL_VERSION
    assert response["result"]["serverInfo"]["name"] == "recruitee-mcp"
    assert response["result"]["capabilities"]["tools"]["call"] is True


def test_read_resource_invokes_client() -> None:
    server, client = build_server()
    response = server._dispatch(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "read_resource",
            "params": {"uri": "recruitee://offers"},
        }
    )
    assert client.list_offers.call_count == 1
    assert response["result"]["contents"][0]["type"] == "application/json"


def test_call_tool_dispatches_to_client() -> None:
    server, client = build_server()
    response = server._dispatch(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "call_tool",
            "params": {
                "name": "create_candidate",
                "arguments": {
                    "first_name": "Jane",
                    "last_name": "Doe",
                    "email": "jane@example.com",
                },
            },
        }
    )
    assert client.create_candidate.call_count == 1
    assert response["result"]["content"][0]["data"]["candidate"]["id"] == 1


def test_call_tool_missing_arguments_returns_error() -> None:
    server, _ = build_server()
    response = server._dispatch(
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "call_tool",
            "params": {"name": "create_candidate", "arguments": {}},
        }
    )
    assert response["error"]["code"] == -32001
    assert "Missing required fields" in response["error"]["message"]


def test_unknown_method_returns_error() -> None:
    server, _ = build_server()
    response = server._dispatch({"jsonrpc": "2.0", "id": 7, "method": "unknown"})
    assert response["error"]["code"] == -32601
