"""HTTP client for interacting with the Recruitee REST API."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, MutableMapping, Optional, Sequence, Union
import time
from datetime import datetime, date, timezone, timedelta
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
        # Back-compat params:
        state: str | None = None,
        limit: int | None = None,
        include_description: bool = False,
        # New / canonical params per API:
        status: str | None = None,        # "archived" | "active" | "not_archived"
        view_mode: str | None = None,    # "brief" | "default"
        offset: int | None = None,
    ) -> Mapping[str, Any]:
        """
        Return a collection of job offers.

        `status` controls which offers are returned ("archived" | "active" | "not_archived").
        `view_mode="brief"` returns a lean payload; "default" includes most details.
        Use `limit` + `offset` for pagination.

        Notes from API: scope + view_mode are the standard query params. :contentReference[oaicite:1]{index=1}
        """
        params: Dict[str, Any] = {}

        # Back-compat: map your older `state` to the API's `scope`.
        if state:
            params["scope"] = state

        if limit is not None:
            params["limit"] = limit
        if include_description:
            params["include_description"] = "true"

        # Canonical params:
        if status:
            params["status"] = status
        if view_mode:
            params["view_mode"] = view_mode
        if offset is not None:
            params["offset"] = offset

        return self._request("GET", "offers", params=params)

    def get_offer(self, offer_id: int | str) -> Mapping[str, Any]:
        """Return the JSON representation for a single offer."""
        return self._request("GET", f"offers/{offer_id}")

    def list_pipelines(self) -> Mapping[str, Any]:
        """Return available recruiting pipelines."""
        return self._request("GET", "pipelines")

    def list_candidates(
        self,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> Mapping[str, Any]:
        """
        List candidates (simple pagination).
        For keyword search, continue using `search_candidates`.
        """
        params: Dict[str, Any] = {}
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        return self._request("GET", "candidates", params=params)

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

    def search_candidates_advanced(
        self,
        filters: FilterLike = None,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> Mapping[str, Any]:
        """
        Advanced search for candidates using Recruitee's dedicated endpoint:
        GET /c/{company_id}/search/new/candidates

        Accepts either a plain list of filter dicts or a SearchFilters builder.
        """
        if isinstance(filters, SearchFilters):
            filters = filters.build()

        params: Dict[str, Any] = {}
        if filters is not None:
            params["filters"] = json.dumps(filters)
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset

        return self._request("GET", "search/new/candidates", params=params)


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
    # ------------------------------------------------------------------
    # Pre-baked search recipes (call search_candidates_advanced under the hood)
    # ------------------------------------------------------------------

    def recipe_fresh_leads(
        self,
        *,
        hours: int = 72,
        min_rating: int | None = None,
        require_cv: bool = True,
        tags: Optional[Sequence[str]] = None,
        offer_ids: Optional[Sequence[int]] = None,
        limit: int = 200,
        offset: int = 0,
    ) -> Mapping[str, Any]:
        """
        Recently updated candidates (default last 72h). Optionally enforce CV,
        minimum star rating, tags (OR), and specific offers (OR).
        """
        sf = SearchFilters().updated_since(hours=hours)
        if require_cv:
            sf.has_cv(True)
        if min_rating is not None:
            sf.rating_at_least(min_rating)
        if tags:
            sf.with_tags(tags, match="any")
        if offer_ids:
            sf.in_offers([int(x) for x in offer_ids])
        return self.search_candidates_advanced(sf, limit=limit, offset=offset)

    def recipe_referrals_with_cv(
        self,
        *,
        days: int = 7,
        min_rating: int | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> Mapping[str, Any]:
        """
        Internal/referral candidates created in the last N days, with CV present.
        """
        now = datetime.now(tz=timezone.utc)
        start = now - timedelta(days=days)
        sf = (
            SearchFilters()
            .with_tags(["referral", "internal"], match="any")
            .has_cv(True)
            .created_between(start, now)
        )
        if min_rating is not None:
            sf.rating_at_least(min_rating)
        return self.search_candidates_advanced(sf, limit=limit, offset=offset)

    def recipe_top_rated_for_offer(
        self,
        offer_id: int,
        *,
        min_stars: int = 4,
        updated_within_hours: int | None = 7 * 24,
        require_cv: bool = False,
        limit: int = 200,
        offset: int = 0,
    ) -> Mapping[str, Any]:
        """
        High-signal candidates (>= min_stars) associated with a specific offer.
        Optionally require recent activity and CV.
        """
        sf = SearchFilters().in_offers([int(offer_id)]).rating_at_least(min_stars)
        if updated_within_hours:
            sf.updated_since(hours=updated_within_hours)
        if require_cv:
            sf.has_cv(True)
        return self.search_candidates_advanced(sf, limit=limit, offset=offset)

    def recipe_stage_bucket(
        self,
        stage_ids: Sequence[int],
        *,
        include_disqualified: bool = False,
        limit: int = 200,
        offset: int = 0,
    ) -> Mapping[str, Any]:
        """
        Pull candidates that are currently in any of the given stage IDs.
        """
        sf = SearchFilters().in_stages([int(s) for s in stage_ids])
        if not include_disqualified:
            sf.disqualified(False)
        return self.search_candidates_advanced(sf, limit=limit, offset=offset)

    def recipe_keyword_window(
        self,
        query: str,
        *,
        days: int = 30,
        limit: int = 500,
        offset: int = 0,
    ) -> Mapping[str, Any]:
        """
        Full-text keyword search within a rolling creation window.
        """
        now = datetime.now(tz=timezone.utc)
        start = now - timedelta(days=days)
        sf = SearchFilters().text(query).created_between(start, now)
        return self.search_candidates_advanced(sf, limit=limit, offset=offset)

    def recipe_source_window(
        self,
        sources: Sequence[str],
        *,
        days: int | None = 30,
        require_cv: bool = False,
        limit: int = 200,
        offset: int = 0,
    ) -> Mapping[str, Any]:
        """
        Candidates from specific sources (e.g., 'LinkedIn', 'Referral').
        Optionally restrict to a recent creation window and/or require CV.
        """
        sf = SearchFilters().source(list(sources), match="any")
        if days is not None:
            now = datetime.now(tz=timezone.utc)
            start = now - timedelta(days=days)
            sf.created_between(start, now)
        if require_cv:
            sf.has_cv(True)
        return self.search_candidates_advanced(sf, limit=limit, offset=offset)
    
    # ------------------------------------------------------------------
    # Pagination helpers with max-record cap
    # ------------------------------------------------------------------

    def iter_search_candidates_advanced(
        self,
        filters: FilterLike = None,
        *,
        page_size: int = 500,
        start_offset: int = 0,
        max_records: int | None = None,
        throttle_seconds: float = 0.0,
    ):
        """
        Iterate candidates from /search/new/candidates with an optional max record cap.

        Args:
            filters: SearchFilters builder or raw list[filter].
            page_size: records per page (Recruitee defaults to 60; supports larger).
            start_offset: initial offset (useful to resume).
            max_records: stop after yielding this many (None = no cap).
            throttle_seconds: sleep between page fetches to reduce API pressure.

        Yields:
            dicts representing candidate records.
        """
        # Accept builder directly
        if isinstance(filters, SearchFilters):
            filters = filters.build()

        offset = int(start_offset)
        yielded = 0

        while True:
            # Respect cap per page
            if max_records is not None:
                remaining = max_records - yielded
                if remaining <= 0:
                    return
                limit = min(page_size, remaining)
            else:
                limit = page_size

            resp = self.search_candidates_advanced(filters, limit=limit, offset=offset)

            # Try common shapes; default to empty list if unknown
            items = resp.get("candidates")
            if not isinstance(items, list):
                for key in ("items", "results", "data", "hits"):
                    if isinstance(resp.get(key), list):
                        items = resp[key]
                        break
            if not items:
                return

            for it in items:
                yield it
                yielded += 1
                if max_records is not None and yielded >= max_records:
                    return

            got = len(items)
            offset += got

            # If the API returned fewer than requested, we reached the end
            if got < limit:
                return

            if throttle_seconds:
                time.sleep(throttle_seconds)

    def search_candidates_advanced_all(
        self,
        filters: FilterLike = None,
        *,
        max_records: int = 1000,
        page_size: int = 500,
        throttle_seconds: float = 0.0,
        start_offset: int = 0,
    ) -> list[Mapping[str, Any]]:
        """
        Collect candidates into a list with a max-record cap (wrapper over the iterator).
        """
        return list(
            self.iter_search_candidates_advanced(
                filters,
                page_size=page_size,
                start_offset=start_offset,
                max_records=max_records,
                throttle_seconds=throttle_seconds,
            )
        )

    def iter_candidates(
        self,
        *,
        page_size: int = 200,
        start_offset: int = 0,
        max_records: int | None = None,
        throttle_seconds: float = 0.0,
    ):
        """
        Iterate simple /candidates listing with an optional max-record cap.
        """
        offset = int(start_offset)
        yielded = 0

        while True:
            # Respect cap per page
            if max_records is not None:
                remaining = max_records - yielded
                if remaining <= 0:
                    return
                limit = min(page_size, remaining)
            else:
                limit = page_size

            resp = self.list_candidates(limit=limit, offset=offset)

            items = resp.get("candidates")
            if not isinstance(items, list):
                for key in ("items", "results", "data", "hits"):
                    if isinstance(resp.get(key), list):
                        items = resp[key]
                        break
            if not items:
                return

            for it in items:
                yield it
                yielded += 1
                if max_records is not None and yielded >= max_records:
                    return

            got = len(items)
            offset += got
            if got < limit:
                return

            if throttle_seconds:
                time.sleep(throttle_seconds)

# ------------------------------------------------------------------
# Search filter helpers for /search/new/candidates
# ------------------------------------------------------------------

Filter = Mapping[str, Any]
FilterList = list[Filter]
FilterLike = Union["SearchFilters", FilterList, None]


def _now_ts() -> int:
    return int(time.time())


def _to_ts(value: Union[int, float, datetime, date]) -> int:
    """Coerce date/datetime/epoch number to UNIX seconds (UTC)."""
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return int(value.timestamp())
    if isinstance(value, date):
        # midnight UTC for a date
        dt = datetime(value.year, value.month, value.day, tzinfo=timezone.utc)
        return int(dt.timestamp())
    raise TypeError(f"Unsupported timestamp type: {type(value)!r}")


# ----- atomic filter constructors -----

def f_text(query: str) -> Filter:
    """Fulltext across all candidate fields."""
    return {"field": "all", "query": query}

def f_updated_since(*, hours: int = 24) -> Filter:
    """Candidates updated within the last N hours."""
    return {"field": "updated_at", "gte": _now_ts() - hours * 3600}

def f_created_between(start: Union[int, float, datetime, date],
                      end: Union[int, float, datetime, date]) -> Filter:
    """Candidates created within [start, end]."""
    return {"field": "created_at", "gte": _to_ts(start), "lte": _to_ts(end)}

def f_has_cv(value: bool = True) -> Filter:
    return {"field": "has_cv", "eq": bool(value)}

def f_disqualified(value: bool = True) -> Filter:
    return {"field": "disqualified", "eq": bool(value)}

def f_hired(value: bool = True) -> Filter:
    return {"field": "hired", "eq": bool(value)}

def f_rating_at_least(stars: int) -> Filter:
    """Minimum star rating (e.g., 3..5)."""
    return {"field": "rating", "gte": int(stars)}

def f_in_offers(offer_ids: Sequence[int]) -> Filter:
    """Match candidates associated with any of the given offer IDs."""
    return {"field": "offers", "any": list(map(int, offer_ids))}

def f_in_departments(dept_ids: Sequence[int]) -> Filter:
    return {"field": "departments", "any": list(map(int, dept_ids))}

def f_in_pipelines(pipeline_ids: Sequence[int]) -> Filter:
    return {"field": "pipelines", "any": list(map(int, pipeline_ids))}

def f_in_stages(stage_ids: Sequence[int]) -> Filter:
    return {"field": "stages", "any": list(map(int, stage_ids))}

def f_with_tags(tags: Sequence[str], *, match: str = "any") -> Filter:
    """
    Tag match helper.
    match: "any" (OR) or "all" (AND)
    """
    if match not in ("any", "all"):
        raise ValueError("match must be 'any' or 'all'")
    return {"field": "tags", match: list(tags)}

def f_source(sources: Sequence[str], *, match: str = "any") -> Filter:
    """Limit to candidates with given sources (string labels in your ATS)."""
    if match not in ("any", "all"):
        raise ValueError("match must be 'any' or 'all'")
    return {"field": "source", match: list(sources)}

def f_location(countries_or_cities: Sequence[str], *, match: str = "any") -> Filter:
    """Simple location label match; adjust values to what your ATS uses."""
    if match not in ("any", "all"):
        raise ValueError("match must be 'any' or 'all'")
    return {"field": "location", match: list(countries_or_cities)}


# ----- fluent builder -----

@dataclass(slots=True)
class SearchFilters:
    items: list[Filter] = field(default_factory=list)

    def add(self, f: Filter) -> "SearchFilters":
        self.items.append(f)
        return self

    # Fluent conveniences (chainable)
    def text(self, query: str) -> "SearchFilters":
        return self.add(f_text(query))

    def updated_since(self, *, hours: int = 24) -> "SearchFilters":
        return self.add(f_updated_since(hours=hours))

    def created_between(self, start: Union[int, float, datetime, date],
                        end: Union[int, float, datetime, date]) -> "SearchFilters":
        return self.add(f_created_between(start, end))

    def has_cv(self, value: bool = True) -> "SearchFilters":
        return self.add(f_has_cv(value))

    def disqualified(self, value: bool = True) -> "SearchFilters":
        return self.add(f_disqualified(value))

    def hired(self, value: bool = True) -> "SearchFilters":
        return self.add(f_hired(value))

    def rating_at_least(self, stars: int) -> "SearchFilters":
        return self.add(f_rating_at_least(stars))

    def in_offers(self, offer_ids: Sequence[int]) -> "SearchFilters":
        return self.add(f_in_offers(offer_ids))

    def in_departments(self, dept_ids: Sequence[int]) -> "SearchFilters":
        return self.add(f_in_departments(dept_ids))

    def in_pipelines(self, pipeline_ids: Sequence[int]) -> "SearchFilters":
        return self.add(f_in_pipelines(pipeline_ids))

    def in_stages(self, stage_ids: Sequence[int]) -> "SearchFilters":
        return self.add(f_in_stages(stage_ids))

    def with_tags(self, tags: Sequence[str], *, match: str = "any") -> "SearchFilters":
        return self.add(f_with_tags(tags, match=match))

    def source(self, sources: Sequence[str], *, match: str = "any") -> "SearchFilters":
        return self.add(f_source(sources, match=match))

    def location(self, labels: Sequence[str], *, match: str = "any") -> "SearchFilters":
        return self.add(f_location(labels, match=match))

    def build(self) -> FilterList:
        return list(self.items)
