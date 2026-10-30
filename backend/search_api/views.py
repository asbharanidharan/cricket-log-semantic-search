
import logging

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from qdrant_client import QdrantClient, models
from sentence_transformers import SentenceTransformer

from .rag import answer_question
from .validators import (
    validate_cricket_record,
    classify_cricket_record,
)

logger = logging.getLogger(__name__)

QDRANT_URL = "http://127.0.0.1:6333"
COLLECTION_NAME = "cricket_logs"
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

# Load the embedding model once when the API starts.
embedding_model = SentenceTransformer(MODEL_NAME)


def format_search_result(point, include_score=False):
    """
    Format a Qdrant point and attach validation information.

    Original record values are preserved. Validation warnings
    identify potential inconsistencies; they do not prove
    whether a record is factually true.
    """
    record = point.payload or {}

    warnings = validate_cricket_record(record)
    classification = classify_cricket_record(record, warnings)

    result = {
        "match": record.get("match"),
        "team": record.get("team"),
        "player": record.get("player"),
        "event": record.get("event"),
        "runs": record.get("runs"),
        "over": record.get("over"),
        "status": record.get("status"),
        "commentary": record.get("commentary"),
        "validation_warnings": warnings,
        "record_classification": classification,
    }

    if include_score:
        score = getattr(point, "score", None)
        result["score"] = (
            round(float(score), 4)
            if score is not None
            else None
        )

    return result


def build_validation_summary(results):
    """Summarize validation warnings without removing records."""
    warning_records = [
        result
        for result in results
        if result.get("validation_warnings")
    ]

    high_severity_records = [
        result
        for result in results
        if any(
            warning.get("severity") == "high"
            for warning in result.get("validation_warnings", [])
        )
    ]

    return {
        "records_returned": len(results),
        "records_with_warnings": len(warning_records),
        "records_with_high_severity_warnings": len(
            high_severity_records
        ),
    }


def parse_integer(value, field_name):
    """Validate an optional integer filter."""
    if value is None or value == "":
        return None

    if isinstance(value, bool):
        raise ValueError(
            f"{field_name} must be an integer."
        )

    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise ValueError(
            f"{field_name} must be an integer."
        )

    # Reject values such as 5.5 instead of silently converting them.
    if isinstance(value, float) and not value.is_integer():
        raise ValueError(
            f"{field_name} must be an integer."
        )

    if isinstance(value, str):
        if value.strip() != str(parsed):
            raise ValueError(
                f"{field_name} must be a valid integer."
            )

    return parsed


@api_view(["GET", "POST"])
def search_cricket_logs(request):
    """
    Search cricket logs using semantic search and exact filters.

    Supported parameters:
        query: Natural-language semantic query.
        player: Exact player name.
        team: Exact team name.
        event: Exact event name.
        runs: Exact runs value.
        min_runs: Minimum runs (inclusive).
        max_runs: Maximum runs (inclusive).
        limit: Maximum number of results.

    Filters can be combined.

    If query is provided, semantic search runs with the
    supplied metadata filters applied inside Qdrant.

    If only metadata filters are provided, exact filtered
    retrieval uses Qdrant scroll().
    """

    # --------------------------------------------------
    # Read request parameters
    # --------------------------------------------------
    if request.method == "GET":
        params = request.query_params
        limit_value = params.get("limit", "5")
    else:
        params = request.data
        limit_value = params.get("limit", 5)

    query = params.get("query", "")
    player = params.get("player", "")
    team = params.get("team", "")
    event = params.get("event", "")

    string_fields = {
        "query": query,
        "player": player,
        "team": team,
        "event": event,
    }

    for field_name, value in string_fields.items():
        if not isinstance(value, str):
            return Response(
                {"error": f"{field_name} must be a string."},
                status=status.HTTP_400_BAD_REQUEST,
            )

    query = query.strip()
    player = player.strip()
    team = team.strip()
    event = event.strip()

    # --------------------------------------------------
    # Validate numeric filters
    # --------------------------------------------------
    try:
        runs = parse_integer(
            params.get("runs"),
            "runs",
        )

        min_runs = parse_integer(
            params.get("min_runs"),
            "min_runs",
        )

        max_runs = parse_integer(
            params.get("max_runs"),
            "max_runs",
        )

    except ValueError as exc:
        return Response(
            {"error": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if runs is not None and (min_runs is not None or max_runs is not None):
        return Response(
            {
                "error": (
                    "Use either runs or min_runs/max_runs, "
                    "not both."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    if min_runs is not None and max_runs is not None:
        if min_runs > max_runs:
            return Response(
                {
                    "error": (
                        "min_runs cannot be greater than max_runs."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

    # --------------------------------------------------
    # Validate result limit
    # --------------------------------------------------
    try:
        limit = int(limit_value)
    except (TypeError, ValueError):
        return Response(
            {"error": "Limit must be an integer between 1 and 100."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not 1 <= limit <= 100:
        return Response(
            {"error": "Limit must be between 1 and 100."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # --------------------------------------------------
    # Check whether any search condition exists
    # --------------------------------------------------
    has_filters = any([
        player,
        team,
        event,
        runs is not None,
        min_runs is not None,
        max_runs is not None,
    ])

    if not query and not has_filters:
        return Response(
            {
                "error": (
                    "Provide a search query or at least "
                    "one metadata filter."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # --------------------------------------------------
    # Construct Qdrant metadata filters
    # --------------------------------------------------
    must_conditions = []

    if player:
        must_conditions.append(
            models.FieldCondition(
                key="player",
                match=models.MatchValue(value=player),
            )
        )

    if team:
        must_conditions.append(
            models.FieldCondition(
                key="team",
                match=models.MatchValue(value=team),
            )
        )

    if event:
        must_conditions.append(
            models.FieldCondition(
                key="event",
                match=models.MatchValue(value=event),
            )
        )

    if runs is not None:
        must_conditions.append(
            models.FieldCondition(
                key="runs",
                match=models.MatchValue(value=runs),
            )
        )

    if min_runs is not None or max_runs is not None:
        must_conditions.append(
            models.FieldCondition(
                key="runs",
                range=models.Range(
                    gte=min_runs,
                    lte=max_runs,
                ),
            )
        )

    query_filter = None

    if must_conditions:
        query_filter = models.Filter(
            must=must_conditions
        )

    client = QdrantClient(url=QDRANT_URL)

    try:
        # --------------------------------------------------
        # PATH 1: Semantic search with metadata filters
        # --------------------------------------------------
        if query:
            query_vector = embedding_model.encode(
                query,
                normalize_embeddings=True,
            ).tolist()

            search_response = client.query_points(
                collection_name=COLLECTION_NAME,
                query=query_vector,
                query_filter=query_filter,
                limit=min(limit, 100),
                with_payload=True,
                with_vectors=False,
            )

            points = search_response.points

            formatted_results = [
                format_search_result(
                    point,
                    include_score=True,
                )
                for point in points
            ]

            return Response(
                {
                    "query": query,
                    "filters": {
                        "player": player or None,
                        "team": team or None,
                        "event": event or None,
                        "runs": runs,
                        "min_runs": min_runs,
                        "max_runs": max_runs,
                    },
                    "search_method": (
                        "filtered_semantic_search"
                        if has_filters
                        else "semantic_search"
                    ),
                    "count": len(formatted_results),
                    "results": formatted_results,
                    "validation_summary": build_validation_summary(
                        formatted_results
                    ),
                },
                status=status.HTTP_200_OK,
            )

        # --------------------------------------------------
        # PATH 2: Exact metadata filtering without embeddings
        # --------------------------------------------------
        points, next_offset = client.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter=query_filter,
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )

        formatted_results = [
            format_search_result(
                point,
                include_score=False,
            )
            for point in points
        ]

        return Response(
            {
                "filters": {
                    "player": player or None,
                    "team": team or None,
                    "event": event or None,
                    "runs": runs,
                    "min_runs": min_runs,
                    "max_runs": max_runs,
                },
                "search_method": "exact_metadata_filter",
                "count": len(formatted_results),
                "limit": limit,
                "has_more": next_offset is not None,
                "results": formatted_results,
                "validation_summary": build_validation_summary(
                    formatted_results
                ),
            },
            status=status.HTTP_200_OK,
        )

    except Exception:
        logger.exception("Error while searching cricket logs")

        return Response(
            {
                "error": (
                    "Search failed. Check that Qdrant is running "
                    "and the collection exists."
                )
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    finally:
        client.close()


@api_view(["POST"])
def chat_cricket_logs(request):
    """Answer cricket questions using RAG and the local Ollama model."""
    question = request.data.get("question", "")

    if not isinstance(question, str) or not question.strip():
        return Response(
            {"error": "Please provide a non-empty question."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        result = answer_question(question)

        return Response(
            result,
            status=status.HTTP_200_OK,
        )

    except ValueError as exc:
        return Response(
            {"error": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    except Exception:
        logger.exception(
            "Error while processing cricket chat request"
        )

        return Response(
            {
                "error": (
                    "Chat failed. Check that Ollama is running, "
                    "the model is available, and Qdrant is accessible."
                )
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
