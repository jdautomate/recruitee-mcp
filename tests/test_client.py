"""Tests for the RecruiteeClient helper."""

from __future__ import annotations

import io
import json
from urllib.error import HTTPError
from typing import Any, Dict
from unittest.mock import patch

import pytest

from recruitee_mcp.client import (
    RecruiteeAPIError,
    RecruiteeClient,
    RecruiteeError,
)


class DummyResponse:
    def __init__(self, payload: Dict[str, Any]):
        self._payload = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._payload

    def __enter__(self) -> "DummyResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # pragma: no cover - nothing to clean up
        return None


def test_list_offers_builds_correct_request() -> None:
    client = RecruiteeClient(
        company_id="acme",
        api_token="token-123",
        base_url="https://api.recruitee.com",
    )

    def fake_urlopen(request, timeout):
        assert request.full_url == "https://api.recruitee.com/c/acme/offers?scope=published&limit=5"
        assert request.get_method() == "GET"
        assert request.get_header("Authorization") == "Bearer token-123"
        assert timeout == 30.0
        return DummyResponse(
            {
                "meta": {"total_count": 3},
                "offers": [
                    {"id": 1, "status": "published"},
                    {"id": 2, "status": "archived"},
                    {"id": 3, "status": "published"},
                ],
            }
        )

    with patch("recruitee_mcp.client.urlopen", side_effect=fake_urlopen):
        response = client.list_offers(status="published", limit=5)

    assert response == {
        "meta": {"total_count": 3},
        "offers": [
            {"id": 1, "status": "published"},
            {"id": 3, "status": "published"},
        ],
    }


def test_list_jobs_delegates_to_list_offers() -> None:
    client = RecruiteeClient(company_id="acme")

    with patch.object(
        RecruiteeClient,
        "list_offers",
        return_value={"offers": ["job"]},
    ) as mock_list_offers:
        response = client.list_jobs(
            state="published",
            limit=10,
            include_description=True,
            scope="active",
            view_mode="brief",
            offset=5,
        )

    assert response == {"offers": ["job"]}
    mock_list_offers.assert_called_once_with(
        state="published",
        limit=10,
        include_description=True,
        scope="active",
        view_mode="brief",
        offset=5,
    )


def test_create_candidate_serialises_payload() -> None:
    client = RecruiteeClient(
        company_id="acme",
        api_token="secret",
        timeout=10,
        base_url="https://api.recruitee.com",
    )

    def fake_urlopen(request, timeout):
        assert request.full_url == "https://api.recruitee.com/c/acme/candidates"
        assert request.get_method() == "POST"
        body = json.loads(request.data.decode("utf-8"))
        assert body == {
            "candidate": {
                "first_name": "Jane",
                "last_name": "Doe",
                "emails": ["jane@example.com"],
                "phones": ["+123"],
                "source": "referral",
                "offer_id": 42,
                "pipeline_id": 7,
                "notes": "Strong portfolio",
            }
        }
        assert request.headers["Content-type"] == "application/json"
        assert timeout == 10
        return DummyResponse({"candidate": {"id": 101}})

    with patch("recruitee_mcp.client.urlopen", side_effect=fake_urlopen):
        response = client.create_candidate(
            first_name="Jane",
            last_name="Doe",
            email="jane@example.com",
            phone="+123",
            source="referral",
            offer_id=42,
            pipeline_id=7,
            notes="Strong portfolio",
        )

    assert response == {"candidate": {"id": 101}}


def test_http_error_is_wrapped() -> None:
    client = RecruiteeClient(company_id="acme")

    error = HTTPError(
        url="https://api.recruitee.com/c/acme/offers",
        code=404,
        msg="Not Found",
        hdrs=None,
        fp=io.BytesIO(b"{\"error\":\"missing\"}"),
    )

    with patch("recruitee_mcp.client.urlopen", side_effect=error):
        with pytest.raises(RecruiteeAPIError) as excinfo:
            client.get_offer(123)

    assert "404" in str(excinfo.value)


def test_invalid_json_raises_error() -> None:
    client = RecruiteeClient(company_id="acme")

    class BadResponse:
        def read(self) -> bytes:
            return b"not-json"

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

    with patch("recruitee_mcp.client.urlopen", return_value=BadResponse()):
        with pytest.raises(RecruiteeError):
            client.get_offer(1)
