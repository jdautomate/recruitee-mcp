# recruitee-mcp

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
