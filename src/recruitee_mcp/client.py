"""HTTP client for interacting with the Recruitee REST API."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, Mapping, MutableMapping, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .config import RecruiteeConfig

LOGGER = logging.getLogger(__name__)


class RecruiteeError(RuntimeError):
    """Base class for exceptions raised by :class:`RecruiteeClient`."""


class RecruiteeAPIError(RecruiteeError):
    """Raised when the Recruitee API returns an HTTP error response."""

    def __init__(self, status_code: int, message: str | None, url: str):
        detail = f" status={status_code}" if status_code else ""
        body = f" body={message}" if message else ""
        super().__init__(f"API request to {url!r} failed with{detail}.{body}")
        self.status_code = status_code
        self.message = message
        self.url = url


class RecruiteeConnectionError(RecruiteeError):
    """Raised when the client cannot reach the Recruitee API."""

    def __init__(self, message: str, url: str):
        super().__init__(f"Connection error while requesting {url!r}: {message}")
        self.url = url
        self.message = message


@dataclass(slots=True)
class RecruiteeClient:
    """Minimal HTTP client for the Recruitee API."""

    company_id: str
    api_token: str | None = None
    base_url: str = "https://api.recruitee.com"
    timeout: float = 30.0

    @classmethod
    def from_config(cls, config: RecruiteeConfig) -> "RecruiteeClient":
        return cls(
            company_id=config.company_id,
            api_token=config.api_token,
            base_url=config.base_url,
            timeout=config.timeout,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def list_offers(
        self,
        *,
        state: str | None = None,
        limit: int | None = None,
        include_description: bool = False,
    ) -> Mapping[str, Any]:
        """Return a collection of job offers for the configured company."""

        params: Dict[str, Any] = {}
        if state:
            params["state"] = state
        if limit:
            params["limit"] = limit
        if include_description:
            params["include_description"] = "true"
        return self._request("GET", "offers", params=params)

    def get_offer(self, offer_id: int | str) -> Mapping[str, Any]:
        """Return the JSON representation for a single offer."""

        return self._request("GET", f"offers/{offer_id}")

    def list_pipelines(self) -> Mapping[str, Any]:
        """Return available recruiting pipelines."""

        return self._request("GET", "pipelines")

    def search_candidates(
        self,
        query: str,
        *,
        page: int | None = None,
        limit: int | None = None,
    ) -> Mapping[str, Any]:
        """Search candidates by keyword query."""

        params: Dict[str, Any] = {"query": query}
        if page is not None:
            params["page"] = page
        if limit is not None:
            params["limit"] = limit
        return self._request("GET", "candidates", params=params)

    def get_candidate(self, candidate_id: int | str) -> Mapping[str, Any]:
        """Retrieve a single candidate by identifier."""

        return self._request("GET", f"candidates/{candidate_id}")

    def create_candidate(
        self,
        *,
        first_name: str,
        last_name: str,
        email: str,
        phone: str | None = None,
        source: str | None = None,
        offer_id: int | None = None,
        pipeline_id: int | None = None,
        notes: str | None = None,
        custom_fields: Optional[Mapping[str, Any]] = None,
    ) -> Mapping[str, Any]:
        """Create a new candidate record."""

        payload: Dict[str, Any] = {
            "candidate": {
                "first_name": first_name,
                "last_name": last_name,
                "emails": [email],
            }
        }
        candidate: MutableMapping[str, Any] = payload["candidate"]
        if phone:
            candidate["phones"] = [phone]
        if source:
            candidate["source"] = source
        if offer_id is not None:
            candidate["offer_id"] = offer_id
        if pipeline_id is not None:
            candidate["pipeline_id"] = pipeline_id
        if notes:
            candidate["notes"] = notes
        if custom_fields:
            candidate["custom_fields"] = dict(custom_fields)

        return self._request("POST", "candidates", data=payload)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Mapping[str, Any]] = None,
        data: Optional[Mapping[str, Any]] = None,
    ) -> Mapping[str, Any]:
        url = self._build_url(path, params)
        headers = {
            "Accept": "application/json",
        }
        body = None
        if data is not None:
            body = json.dumps(data).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"

        request = Request(url, data=body, headers=headers, method=method)

        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw = response.read()
        except HTTPError as exc:
            error_body: Optional[str]
            try:
                error_body = exc.read().decode("utf-8")
            except Exception:  # pragma: no cover - best effort decoding
                error_body = None
            raise RecruiteeAPIError(exc.code, error_body, url) from exc
        except URLError as exc:  # pragma: no cover - network layer issues
            raise RecruiteeConnectionError(str(exc.reason), url) from exc

        if not raw:
            return {}

        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            LOGGER.debug("Invalid JSON payload from %s: %s", url, raw)
            raise RecruiteeError(f"Invalid JSON response returned by {url!r}") from exc

    def _build_url(
        self, path: str, params: Optional[Mapping[str, Any]] = None
    ) -> str:
        normalized = path.lstrip("/")
        url = f"{self.base_url.rstrip('/')}/c/{self.company_id}/{normalized}"
        if params:
            filtered = {k: v for k, v in params.items() if v is not None}
            if filtered:
                url = f"{url}?{urlencode(filtered, doseq=True)}"
        return url
