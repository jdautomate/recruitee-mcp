"""Entry point for running the Recruitee MCP server."""

from __future__ import annotations

import argparse
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
