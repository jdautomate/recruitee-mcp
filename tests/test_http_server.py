import json
import threading
from urllib import request

import pytest

from recruitee_mcp.http_server import HEALTH_CHECK_PATH, create_http_server
from recruitee_mcp.server import RecruiteeMCPServer


@pytest.fixture()
def http_server():
    server = RecruiteeMCPServer()
    httpd = create_http_server(server, host="127.0.0.1", port=0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield httpd
    httpd.shutdown()
    thread.join(timeout=5)
    httpd.server_close()


def _post_json(httpd, payload: bytes) -> dict:
    host, port = httpd.server_address[:2]
    url = f"http://{host}:{port}/"
    req = request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    with request.urlopen(req, timeout=2) as response:
        body = response.read().decode("utf-8")
    return json.loads(body)


def test_http_server_success(http_server):
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "ping",
    }
    response = _post_json(http_server, json.dumps(payload).encode("utf-8"))
    assert response["result"] == "pong"
    assert response["id"] == 1


def test_http_server_unknown_method_error(http_server):
    payload = {
        "jsonrpc": "2.0",
        "id": "request-1",
        "method": "does_not_exist",
    }
    response = _post_json(http_server, json.dumps(payload).encode("utf-8"))
    assert "error" in response
    assert response["error"]["code"] == -32601
    assert response["id"] == "request-1"


def test_http_server_parse_error(http_server):
    response = _post_json(http_server, b"not-json")
    assert response["error"]["code"] == -32700
    assert response["id"] is None


def test_http_server_health_check(http_server):
    host, port = http_server.server_address[:2]
    url = f"http://{host}:{port}{HEALTH_CHECK_PATH}"
    with request.urlopen(url, timeout=2) as response:
        assert response.status == 200
        assert response.headers.get("Content-Type") == "application/json"
        body = response.read().decode("utf-8")

    payload = json.loads(body)
    assert payload == {"status": "ok"}
