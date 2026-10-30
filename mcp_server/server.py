
import os

import httpx
from mcp.server.fastmcp import FastMCP


API_BASE_URL = os.getenv(
    "CRICKET_API_URL",
    "http://127.0.0.1:8000",
).rstrip("/")

QDRANT_URL = os.getenv(
    "QDRANT_URL",
    "http://127.0.0.1:6333",
).rstrip("/")

COLLECTION_NAME = "cricket_logs"

mcp = FastMCP("Cricket Log Semantic Search")


@mcp.tool()
async def search_cricket_logs(
    query: str = "",
    player: str = "",
    team: str = "",
    event: str = "",
    runs: int | None = None,
    min_runs: int | None = None,
    max_runs: int | None = None,
    limit: int = 5,
) -> dict:
    """
    Search cricket logs using semantic search and exact metadata filters.

    Parameters:
        query: Natural-language search query.
        player: Exact player name, e.g. Player 4.
        team: Exact team name, e.g. Team A.
        event: Exact event name, e.g. LBW given.
        runs: Exact runs value.
        min_runs: Minimum runs, inclusive.
        max_runs: Maximum runs, inclusive.
        limit: Maximum number of results.

    Multiple filters can be combined.
    """

    # Validate string parameters.
    for name, value in {
        "query": query,
        "player": player,
        "team": team,
        "event": event,
    }.items():
        if not isinstance(value, str):
            return {"error": f"{name} must be a string."}

    # Validate limit.
    if isinstance(limit, bool) or not isinstance(limit, int):
        return {"error": "Limit must be an integer."}

    if not 1 <= limit <= 100:
        return {"error": "Limit must be between 1 and 100."}

    # Validate numeric filters.
    numeric_filters = {
        "runs": runs,
        "min_runs": min_runs,
        "max_runs": max_runs,
    }

    for name, value in numeric_filters.items():
        if value is not None:
            if isinstance(value, bool) or not isinstance(value, int):
                return {
                    "error": f"{name} must be an integer."
                }

    if runs is not None and (
        min_runs is not None or max_runs is not None
    ):
        return {
            "error": "Use either runs or min_runs/max_runs, not both."
        }

    if (
        min_runs is not None
        and max_runs is not None
        and min_runs > max_runs
    ):
        return {
            "error": "min_runs cannot be greater than max_runs."
        }

    # Build request parameters.
    params = {"limit": limit}

    if query.strip():
        params["query"] = query.strip()

    if player.strip():
        params["player"] = player.strip()

    if team.strip():
        params["team"] = team.strip()

    if event.strip():
        params["event"] = event.strip()

    if runs is not None:
        params["runs"] = runs

    if min_runs is not None:
        params["min_runs"] = min_runs

    if max_runs is not None:
        params["max_runs"] = max_runs

    if len(params) == 1:
        return {
            "error": (
                "Provide a search query or at least one metadata filter."
            )
        }

    # Call Django REST API.
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.get(
            f"{API_BASE_URL}/api/search/",
            params=params,
        )

        response.raise_for_status()

        return response.json()


@mcp.tool()
async def ask_cricket_question(question: str) -> dict:
    """Answer a natural-language question using the cricket-log RAG API."""

    if not question.strip():
        return {
            "error": "Please provide a non-empty question."
        }

    async with httpx.AsyncClient(timeout=180.0) as client:
        response = await client.post(
            f"{API_BASE_URL}/api/chat/",
            json={"question": question},
        )

        response.raise_for_status()

        return response.json()


@mcp.tool()
async def get_cricket_statistics() -> dict:
    """Retrieve collection statistics and explain vector-index status."""

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{QDRANT_URL}/collections/{COLLECTION_NAME}",
        )

        response.raise_for_status()

        collection = response.json().get("result", {})

    config = collection.get("config", {})
    optimizer_config = config.get("optimizer_config", {})

    points_count = collection.get("points_count")
    indexed_vectors_count = collection.get("indexed_vectors_count")
    indexing_threshold = optimizer_config.get("indexing_threshold")

    return {
        "collection": COLLECTION_NAME,
        "total_records": points_count,
        "indexed_vectors": indexed_vectors_count,
        "hnsw_indexing_threshold": indexing_threshold,
        "status": collection.get("status"),
        "optimizer_status": collection.get("optimizer_status"),
        "indexing_note": (
            "A value of zero for indexed_vectors does not, by itself, "
            "mean vectors are missing. Qdrant's indexing configuration "
            "and actual search behavior must also be considered."
        ),
        "note": (
            "total_records represents stored Qdrant points. These values "
            "are collection-level statistics, not cricket match results "
            "or player-performance statistics."
        ),
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
