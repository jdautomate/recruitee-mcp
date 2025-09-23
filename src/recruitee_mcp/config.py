"""Configuration helpers for the Recruitee MCP server."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(slots=True)
class RecruiteeConfig:
    """Runtime configuration for accessing the Recruitee API."""

    company_id: str
    api_token: str | None = None
    base_url: str = "https://api.recruitee.com"
    timeout: float = 30.0

    @classmethod
    def from_env(cls, environ: os._Environ[str] | None = None) -> "RecruiteeConfig":
        """Create a configuration object from environment variables."""

        env = os.environ if environ is None else environ
        company_id = env.get("RECRUITEE_COMPANY_ID")
        if not company_id:
            raise ValueError("RECRUITEE_COMPANY_ID must be provided")

        api_token = env.get("RECRUITEE_API_TOKEN")
        base_url = env.get("RECRUITEE_BASE_URL", "https://api.recruitee.com")
        timeout_raw = env.get("RECRUITEE_TIMEOUT")
        timeout = float(timeout_raw) if timeout_raw else 30.0

        return cls(
            company_id=company_id.strip(),
            api_token=api_token.strip() if api_token else None,
            base_url=base_url.rstrip("/"),
            timeout=timeout,
        )
