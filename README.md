# recruitee-mcp

## Kubernetes deployment

The repository contains example manifests under `k8s/` for running the HTTP
server on Kubernetes.

1. Deploy the application pods:
   ```bash
   kubectl apply -f k8s/deployment.yaml
   ```
2. Expose the pods internally through a ClusterIP Service:
   ```bash
   kubectl apply -f k8s/service.yaml
   ```
3. Publish the Service externally with an Ingress resource:
   ```bash
   kubectl apply -f k8s/ingress.yaml
   ```

Update the container image in `k8s/deployment.yaml` to match the image you wish
to deploy. The Service exposes port 80 inside the cluster and forwards traffic
to the container port `8080` declared in the Deployment.

The default Ingress manifest assumes an ingress controller such as NGINX. Adjust
the annotations under `metadata.annotations` to match your ingress controller
(e.g., `kubernetes.io/ingress.class`, `nginx.ingress.kubernetes.io/rewrite-target`).
Set `external-dns.alpha.kubernetes.io/hostname` (or controller-specific
equivalents) and the `spec.rules[0].host` value to the hostname that should
route to this service. To enable TLS termination, provide a TLS secret name in
the `spec.tls` section and, if using cert-manager, uncomment the
`cert-manager.io/cluster-issuer` annotation or replace it with the issuer name
required by your environment.

Once the manifests are configured, you can apply updates at any time with
`kubectl apply -f k8s/` to sync all resources in a single command.
# Recruitee MCP

This repository contains a minimal reference implementation of the Recruitee Model Context Protocol (MCP) server. It
announces compliance with MCP protocol version 0.5 so it interoperates with current clients that target the published
specification.

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

The HTTP transport now advertises a [Model Context Protocol over HTTP (MCPO)](https://github.com/modelcontextprotocol)
manifest at `/.well-known/mcp.json`. Clients that support MCPO discovery (including Open WebUI) can use the
manifest to discover the JSON-RPC endpoint and available tools.

### Legacy stdio transport

For backwards compatibility a stdio transport is still available. It can be enabled with the `--stdio` flag which causes
the server to read JSON-RPC payloads from standard input and write responses to standard output:

```bash
echo '{"jsonrpc": "2.0", "id": 1, "method": "ping"}' | recruitee-mcp --stdio
```

This mode remains opt-in, while the default behaviour continues to be the HTTP transport described above.

### FastMCP tooling

The optional `recruitee_mcp.mcp_server` module relies on the
[`mcp`](https://github.com/modelcontextprotocol/python-sdk) package. Install the
extra dependencies to enable the FastMCP tools and streamable HTTP endpoints:

```bash
pip install "recruitee-mcp[fastmcp]"
```

If the dependencies are missing, importing the module will raise a descriptive
error with the same installation hint.

## Development

Install the project in editable mode and run the tests via `pytest`:

```bash
pip install -e .
pytest
```
A lightweight [Model Context Protocol](https://github.com/modelcontextprotocol/specification) (MCP) server written in Python that exposes resources and tools for the [Recruitee](https://recruitee.com) recruiting platform. The server speaks JSON-RPC 2.0 over standard input/output so it can be embedded inside compatible AI tooling.

The project intentionally keeps its dependency surface minimal so it can run in restricted environments. HTTP communication with the Recruitee REST API is implemented with the Python standard library.

## Features

* List public job offers for a company.
* Fetch detailed information for a specific job offer or candidate.
* Search candidates by keyword query.
* Create a new candidate in a given pipeline stage.
* Exposes the above operations as MCP resources and tools that can be consumed by an MCP client.

## Configuration

The server requires a Recruitee API token with the appropriate scopes for the operations you intend to perform. Provide configuration through environment variables:

| Variable | Description |
| --- | --- |
| `RECRUITEE_COMPANY_ID` | Recruitee company identifier (the `c/<id>` part of API URLs). |
| `RECRUITEE_API_TOKEN` | API token used for authenticated requests. |
| `RECRUITEE_BASE_URL` | Optional. Override the API base URL (defaults to `https://api.recruitee.com`). |
| `RECRUITEE_TIMEOUT` | Optional. Request timeout in seconds (defaults to `30`). |

## Running the server

Install the package (editable installs work well during development) and start the server:

```bash
pip install -e .
recruitee-mcp-server
```

The server reads JSON-RPC requests from standard input and writes responses to standard output, so it can be managed by an MCP-compatible orchestration layer. You can also run it directly for debugging:

```bash
python -m recruitee_mcp.main
```

## Development

* Format the codebase with `black` and `isort` if desired.
* Run the automated tests with `pytest`.

```bash
pytest
```

## Limitations

The test suite uses mocks and does not contact the real Recruitee API. When integrating with production credentials make sure to review the [Recruitee API documentation](https://api.recruitee.com/docs/index.html) for additional endpoints, payloads, and permission requirements.