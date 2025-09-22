# Recruitee MCP

This repository contains a minimal reference implementation of the Recruitee Model Context Protocol (MCP) server.

## Running the server

The server now exposes a JSON-RPC endpoint over HTTP by default. You can start it directly via the installed console
script:

```bash
recruitee-mcp
```

By default the server binds to `0.0.0.0:8080`. The port can be configured through the `RECRUITEE_HTTP_PORT`
environment variable or via the `--port` CLI argument:

```bash
export RECRUITEE_HTTP_PORT=9090
recruitee-mcp --host 127.0.0.1
```

To explicitly select the port via CLI instead of the environment variable:

```bash
recruitee-mcp --port 9090
```

### Legacy stdio transport

For backwards compatibility a stdio transport is still available. It can be enabled with the `--stdio` flag which causes
the server to read JSON-RPC payloads from standard input and write responses to standard output:

```bash
echo '{"jsonrpc": "2.0", "id": 1, "method": "ping"}' | recruitee-mcp --stdio
```

This mode remains opt-in, while the default behaviour continues to be the HTTP transport described above.

## Development

Install the project in editable mode and run the tests via `pytest`:

```bash
pip install -e .
pytest
```
