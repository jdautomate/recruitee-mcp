"""Core package for the Recruitee MCP server, exposing the client, configuration, server, and HTTP helpers."""

from .client import RecruiteeClient, SearchFilters
from .config import RecruiteeConfig
from .http_server import create_http_server, serve_http
from .server import JSONRPCError, RecruiteeMCPServer

__all__ = [
    "JSONRPCError",
    "RecruiteeMCPServer",
    "RecruiteeClient",
    "SearchFilters",
    "RecruiteeConfig",
    "serve_http",
    "create_http_server",
]
