# mcp_server.py
from __future__ import annotations

import os
import asyncio
from typing import Any, Dict, Optional, List, Mapping

from mcp.server.fastmcp import FastMCP, Context
from mcp.server.session import ServerSession

from client import RecruiteeClient  # adjust import if your package layout differs

COMPANY_ID = os.getenv("RECRUITEE_COMPANY_ID")
API_TOKEN = os.getenv("RECRUITEE_API_TOKEN")
BASE_URL = os.getenv("RECRUITEE_BASE_URL", "https://api.recruitee.com")

if not COMPANY_ID or not API_TOKEN:
    raise RuntimeError(
        "Set RECRUITEE_COMPANY_ID and RECRUITEE_API_TOKEN in your environment."
    )

client = RecruiteeClient(
    company_id=COMPANY_ID,
    api_token=API_TOKEN,
    base_url=BASE_URL,
)

mcp = FastMCP("Recruitee")

# ---------- Tools ----------

@mcp.tool()
async def ping() -> str:
    """Sanity check that the server is alive and credentials are loaded."""
    masked = API_TOKEN[:6] + "…" if API_TOKEN else "<missing>"
    return f"Recruitee MCP ok. company_id={COMPANY_ID}, token={masked}"

@mcp.tool()
async def list_offers(
    scope: Optional[str] = None,         # "archived" | "active" | "not_archived"
    view_mode: Optional[str] = "brief",  # "brief" | "default"
    limit: Optional[int] = 50,
    offset: Optional[int] = 0,
) -> Mapping[str, Any]:
    """List job offers (postings)."""
    return await asyncio.to_thread(
        client.list_offers,
        scope=scope,
        view_mode=view_mode,
        limit=limit,
        offset=offset,
    )

@mcp.tool()
async def get_offer(offer_id: int) -> Mapping[str, Any]:
    """Fetch a single offer by ID."""
    return await asyncio.to_thread(client.get_offer, offer_id)

@mcp.tool()
async def list_candidates(
    limit: Optional[int] = 60,
    offset: Optional[int] = 0,
) -> Mapping[str, Any]:
    """List candidates (simple pagination)."""
    return await asyncio.to_thread(client.list_candidates, limit=limit, offset=offset)

@mcp.tool()
async def search_candidates(
    filters: Optional[List[Mapping[str, Any]]] = None,
    limit: Optional[int] = 60,
    offset: Optional[int] = 0,
) -> Mapping[str, Any]:
    """
    Advanced candidate search using JSON-array `filters`.
    See Recruitee docs for supported filters and timestamp rules.
    """
    return await asyncio.to_thread(
        client.search_candidates_advanced,
        filters,
        limit=limit,
        offset=offset,
    )

@mcp.tool()
async def get_candidate(candidate_id: int) -> Mapping[str, Any]:
    """Fetch a single candidate by ID."""
    return await asyncio.to_thread(client.get_candidate, candidate_id)

@mcp.tool()
async def create_candidate(
    first_name: str,
    last_name: str,
    email: str,
    phone: Optional[str] = None,
    source: Optional[str] = None,
    offer_id: Optional[int] = None,
    pipeline_id: Optional[int] = None,
    notes: Optional[str] = None,
    custom_fields: Optional[Mapping[str, Any]] = None,
) -> Mapping[str, Any]:
    """Create a candidate (ATS API)."""
    return await asyncio.to_thread(
        client.create_candidate,
        first_name=first_name,
        last_name=last_name,
        email=email,
        phone=phone,
        source=source,
        offer_id=offer_id,
        pipeline_id=pipeline_id,
        notes=notes,
        custom_fields=custom_fields,
    )

if __name__ == "__main__":
    mcp.run_stdio()
