
import re

from ollama import Client
from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue
from sentence_transformers import SentenceTransformer

from .validators import (
    validate_cricket_record,
    classify_cricket_record,
)


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

QDRANT_URL = "http://127.0.0.1:6333"
COLLECTION_NAME = "cricket_logs"
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
OLLAMA_MODEL = "llama3.2:3b"

qdrant_client = QdrantClient(url=QDRANT_URL)
ollama_client = Client(host="http://172.18.0.1:11434")
embedding_model = SentenceTransformer(MODEL_NAME)


# ---------------------------------------------------------
# Event aliases
# ---------------------------------------------------------

EVENT_ALIASES = {
    "LBW given": [
        "lbw given",
        "given out lbw",
        "given lbw",
        "out lbw",
        "lbw events",
        "lbw event",
        "lbw records",
        "lbw record",
        "lbw dismissals",
        "lbw dismissal",
        "leg before wicket given",
        "given out leg before wicket",
        "leg before wicket",
    ],

    "six hit": [
        "six hit",
        "six hits",
        "six",
        "sixes",
        "hit a six",
        "hit six",
        "hitting a six",
        "hitting sixes",
        "sixes hit",
    ],

    "boundary hit": [
        "boundary hit",
        "hit a boundary",
        "hit boundaries",
    ],

    "wicket taken": [
        "wicket taken",
        "wickets taken",
        "took a wicket",
        "took wickets",
        "taken a wicket",
        "taking a wicket",
    ],

    "catch taken": [
        "catch taken",
        "catches taken",
        "caught the ball",
    ],

    "stumping": [
        "stumping",
        "stumpings",
        "stumped",
    ],

    "run scored": [
        "run scored",
        "runs scored",
    ],

    "no ball": [
        "no ball",
        "no balls",
    ],

    "wide": [
        "wide",
        "wides",
    ],

    "over completed": [
        "over completed",
        "overs completed",
    ],
}


NUMBER_WORDS = (
    "zero|one|two|three|four|five|six|seven|eight|nine|ten|"
    "eleven|twelve|thirteen|fourteen|fifteen|sixteen|"
    "seventeen|eighteen|nineteen|twenty"
)

NUMBER_PATTERN = rf"(?:\d+|{NUMBER_WORDS})"


# ---------------------------------------------------------
# Question understanding
# ---------------------------------------------------------

def normalize_question(question):
    """Normalize whitespace and letter case."""
    return " ".join(question.lower().split())


def is_unsupported_wicket_stat_question(question):
    """Identify wicket statistics unsupported by the dataset schema."""
    text = normalize_question(question)

    player_wicket_total = re.search(
        rf"\b(?:who|which player|what player|which bowler|"
        rf"name the player)\b.{{0,100}}?"
        rf"\b(?:take|takes|took|taken|claim|claimed|got|gets)\b"
        rf".{{0,60}}?\b{NUMBER_PATTERN}\s+wickets?\b",
        text,
    )

    wicket_count_question = re.search(
        r"\bhow many wickets?\b.{0,100}\b"
        r"(?:did|does|do|has|have|had|take|took|taken|"
        r"by|in a match|per match)\b",
        text,
    )

    unsupported_bowling_stat = re.search(
        r"\b(?:bowling figures|wicket haul|six[- ]for|"
        r"five[- ]for|wickets per match|best bowling)\b",
        text,
    )

    return bool(
        player_wicket_total
        or wicket_count_question
        or unsupported_bowling_stat
    )


def detect_exact_event(question):
    """Identify a known event mentioned in a question."""
    text = normalize_question(question)

    aliases = sorted(
        (
            (alias, event)
            for event, phrases in EVENT_ALIASES.items()
            for alias in phrases
        ),
        key=lambda item: len(item[0]),
        reverse=True,
    )

    for alias, event in aliases:
        pattern = rf"(?<!\w){re.escape(alias)}(?!\w)"

        if re.search(pattern, text):
            return event

    record_count_question = re.search(
        r"\b(?:how many|count|number of)\b.{0,80}"
        r"\bwicket(?:s)?[- ]?(?:taking )?"
        r"(?:records?|events?|entries|occurrences)\b",
        text,
    )

    if record_count_question:
        return "wicket taken"

    return None


def detect_player_event_question(question):
    """Detect a question about one player's specific event."""
    text = normalize_question(question)

    player_match = re.search(r"\bplayer\s+\d+\b", text)

    if not player_match:
        return None

    # Do not infer wicket statistics from event records.
    if re.search(r"\bwickets?\b", text):
        return None

    player = player_match.group().title()
    event = detect_exact_event(question)

    if not event:
        return None

    return {
        "player": player,
        "event": event,
    }


def detect_all_player_events_question(question):
    """Detect requests for all events belonging to one player."""
    text = normalize_question(question)

    player_match = re.search(r"\bplayer\s+\d+\b", text)

    if not player_match:
        return None

    asks_for_all_events = re.search(
        r"\b(all|every|list|show)\b",
        text,
    )

    asks_about_events = re.search(
        r"\b(events?|records|occurrences)\b",
        text,
    )

    if not (asks_for_all_events and asks_about_events):
        return None

    return player_match.group().title()


# ---------------------------------------------------------
# Qdrant retrieval
# ---------------------------------------------------------

def retrieve_exact_event(event):
    """Retrieve records matching one exact event."""
    record_filter = Filter(
        must=[
            FieldCondition(
                key="event",
                match=MatchValue(value=event),
            )
        ]
    )

    points = []
    next_offset = None

    while True:
        batch, next_offset = qdrant_client.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter=record_filter,
            limit=100,
            offset=next_offset,
            with_payload=True,
            with_vectors=False,
        )

        points.extend(batch)

        if next_offset is None:
            break

    return points


def retrieve_player_event(event, player):
    """Retrieve records matching both exact player and event."""
    record_filter = Filter(
        must=[
            FieldCondition(
                key="player",
                match=MatchValue(value=player),
            ),
            FieldCondition(
                key="event",
                match=MatchValue(value=event),
            ),
        ]
    )

    points = []
    next_offset = None

    while True:
        batch, next_offset = qdrant_client.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter=record_filter,
            limit=100,
            offset=next_offset,
            with_payload=True,
            with_vectors=False,
        )

        points.extend(batch)

        if next_offset is None:
            break

    return points


def retrieve_all_player_records(player):
    """Retrieve all records for one exact player."""
    record_filter = Filter(
        must=[
            FieldCondition(
                key="player",
                match=MatchValue(value=player),
            )
        ]
    )

    records = []
    next_offset = None

    while True:
        points, next_offset = qdrant_client.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter=record_filter,
            limit=100,
            offset=next_offset,
            with_payload=True,
            with_vectors=False,
        )

        records.extend(points)

        if next_offset is None:
            break

    return records


def retrieve_all_records():
    """Retrieve all records from Qdrant using pagination."""

    records = []
    next_offset = None

    while True:
        points, next_offset = qdrant_client.scroll(
            collection_name=COLLECTION_NAME,
            limit=100,
            offset=next_offset,
            with_payload=True,
            with_vectors=False,
        )

        records.extend(points)

        if next_offset is None:
            break

    return records

# ---------------------------------------------------------
# Source construction and validation
# ---------------------------------------------------------

def build_source(point, include_score=True):
    """Build a source record with its validation metadata."""
    payload = point.payload or {}

    record = dict(payload)

    validation_warnings = validate_cricket_record(record)

    record_classification = classify_cricket_record(
        record,
        validation_warnings,
    )

    source = {
        **record,
        "validation_warnings": validation_warnings,
        "record_classification": record_classification,
    }

    if include_score:
        source["score"] = getattr(point, "score", None)

    return source


def distinct_player_names(sources):
    """Return sorted distinct player names."""
    return sorted({
        str(source.get("player"))
        for source in sources
        if source.get("player")
    })


def summarize_validation_warnings(sources):
    """Summarize warning counts without changing source records."""
    warning_record_count = 0
    high_severity_count = 0

    for source in sources:
        warnings = source.get("validation_warnings") or []

        if warnings:
            warning_record_count += 1

        if any(
            warning.get("severity") == "high"
            for warning in warnings
        ):
            high_severity_count += 1

    if not sources:
        return ""

    return (
        f"{warning_record_count} record(s) have validation warnings; "
        f"{high_severity_count} record(s) have high-severity warnings. "
        "Treat flagged records as unverified until checked against "
        "an authoritative source."
    )


# ---------------------------------------------------------
# Numeric runs filter
# ---------------------------------------------------------


def detect_runs_filter(question):
    """Detect a numeric condition applied to the runs field."""
    text = normalize_question(question)

    # Detect inclusive ranges first.
    range_patterns = [
        r"\bbetween\s+(\d+)\s+and\s+(\d+)(?:\s+runs?)?\b",
        r"\bruns?\s+(?:are\s+)?between\s+(\d+)\s+and\s+(\d+)\b",
    ]

    for pattern in range_patterns:
        match = re.search(pattern, text)

        if match:
            lower = int(match.group(1))
            upper = int(match.group(2))

            if lower > upper:
                raise ValueError(
                    "The lower runs value cannot exceed the upper value."
                )

            return {
                "field": "runs",
                "operator": "between",
                "min_value": lower,
                "max_value": upper,
            }

    patterns = [
        (
            r"\b(?:exactly|equal to|equals?)\s+(\d+)\s+runs?\b",
            "eq",
        ),
        (
            r"\b(?:more than|greater than|above|over)\s+(\d+)\s+runs?\b",
            "gt",
        ),
        (
            r"\b(?:at least|minimum of)\s+(\d+)\s+runs?\b",
            "gte",
        ),
        (
            r"\b(?:less than|fewer than|below|under)\s+(\d+)\s+runs?\b",
            "lt",
        ),
        (
            r"\b(?:at most|up to|maximum of)\s+(\d+)\s+runs?\b",
            "lte",
        ),
    ]

    for pattern, operator in patterns:
        match = re.search(pattern, text)

        if match:
            return {
                "field": "runs",
                "operator": operator,
                "value": int(match.group(1)),
            }

    return None


def apply_runs_filter(sources, runs_filter):
    """Filter source records using a detected runs comparison."""
    if not runs_filter:
        return sources

    operator = runs_filter["operator"]

    if operator == "between":
        lower = runs_filter["min_value"]
        upper = runs_filter["max_value"]

        compare = lambda value: lower <= value <= upper

    else:
        target = runs_filter["value"]

        comparisons = {
            "eq": lambda value: value == target,
            "gt": lambda value: value > target,
            "gte": lambda value: value >= target,
            "lt": lambda value: value < target,
            "lte": lambda value: value <= target,
        }

        compare = comparisons[operator]

    filtered = []

    for source in sources:
        try:
            runs = int(source.get("runs"))
        except (TypeError, ValueError):
            continue

        if compare(runs):
            filtered.append(source)

    return filtered


def describe_runs_filter(runs_filter):
    """Convert a runs filter into readable answer text."""
    operator = runs_filter["operator"]

    if operator == "between":
        return (
            f"between {runs_filter['min_value']} and "
            f"{runs_filter['max_value']} runs (inclusive)"
        )

    operator_labels = {
        "eq": "exactly",
        "gt": "more than",
        "gte": "at least",
        "lt": "less than",
        "lte": "at most",
    }

    return (
        f"{operator_labels[operator]} "
        f"{runs_filter['value']} runs"
    )


# ---------------------------------------------------------
# Answer generation
# ---------------------------------------------------------

def build_exact_event_answer(event, sources):
    """Build a concise answer for an exact-event query."""
    players = distinct_player_names(sources)
    warning_summary = summarize_validation_warnings(sources)

    if not sources:
        return f"No stored records were found for event '{event}'."

    answer = (
        f"Found {len(sources)} stored record(s) for event '{event}'. "
        f"Distinct players: {len(players)}. "
        "These are stored records, not confirmation of real-world events. "
        f"{warning_summary}"
    )

    return answer


def answer_exact_event(question, event, runs_filter=None):
    """Return exact-event records, optionally filtered by runs."""
    points = retrieve_exact_event(event)

    points = sorted(
        points,
        key=lambda point: str(
            (point.payload or {}).get("timestamp") or ""
        ),
    )

    sources = [build_source(point) for point in points]

    event_record_count = len(sources)

    sources = apply_runs_filter(sources, runs_filter)

    players = distinct_player_names(sources)

    match_ids = sorted({
        str(source.get("match"))
        for source in sources
        if source.get("match")
    })

    warning_count = sum(
        bool(source.get("validation_warnings"))
        for source in sources
    )

    review_count = sum(
        bool(
            (source.get("record_classification") or {}).get(
                "requires_review"
            )
        )
        for source in sources
    )

    if runs_filter:
        condition = describe_runs_filter(runs_filter)

        answer = (
            f"Found {len(sources)} stored record(s) for event '{event}' "
            f"with {condition}. "
            f"Distinct players: {len(players)}. "
            f"{review_count} record(s) still require review and "
            f"{warning_count} record(s) have validation warnings. "
            "These are stored synthetic records, not confirmation of "
            "real-world events."
        )

    else:
        answer = build_exact_event_answer(event, sources)

    return {
        "question": question,
        "answer": answer,
        "retrieval_method": (
            "exact_event_and_runs_filter"
            if runs_filter
            else "exact_event_filter"
        ),
        "event_filter": event,
        "runs_filter": runs_filter,
        "event_records_before_runs_filter": event_record_count,
        "total_matching_records": len(sources),
        "distinct_player_count": len(players),
        "players": players,
        "match_ids": match_ids,
        "records_requiring_review": review_count,
        "validation_warning_record_count": warning_count,
        "sources": sources,
    }

def answer_numeric_runs(question, runs_filter):
    """Return all records matching a numeric runs condition."""

    points = retrieve_all_records()

    sources = [
        build_source(point)
        for point in points
    ]

    total_records_before_filter = len(sources)

    sources = apply_runs_filter(sources, runs_filter)

    players = distinct_player_names(sources)

    match_ids = sorted({
        str(source.get("match"))
        for source in sources
        if source.get("match")
    })

    warning_count = sum(
        bool(source.get("validation_warnings"))
        for source in sources
    )

    review_count = sum(
        bool(
            (source.get("record_classification") or {}).get(
                "requires_review"
            )
        )
        for source in sources
    )

    condition = describe_runs_filter(runs_filter)

    answer = (
        f"Found {len(sources)} stored record(s) with {condition}, "
        f"out of {total_records_before_filter} stored record(s). "
        f"{review_count} matching record(s) require review; "
        f"{warning_count} have validation warnings. "
        "These are stored synthetic records, not confirmation "
        "of real-world events."
    )

    return {
        "question": question,
        "answer": answer,
        "retrieval_method": "exact_runs_filter",
        "runs_filter": runs_filter,
        "total_records_before_filter": total_records_before_filter,
        "total_matching_records": len(sources),
        "distinct_player_count": len(players),
        "players": players,
        "match_ids": match_ids,
        "records_requiring_review": review_count,
        "validation_warning_record_count": warning_count,
        "sources": sources,
    }


def answer_player_event(
    question,
    event,
    player,
    runs_filter=None,
):
    """Return records matching one exact player, event, and optional runs condition."""
    points = retrieve_player_event(event, player)

    points.sort(
        key=lambda point: (
            str((point.payload or {}).get("match", "")),
            str((point.payload or {}).get("team", "")),
            str((point.payload or {}).get("over", "")),
        )
    )

    sources = [
        build_source(point, include_score=False)
        for point in points
    ]

    sources = apply_runs_filter(sources, runs_filter)

    warning_count = sum(
        bool(source.get("validation_warnings"))
        for source in sources
    )

    high_severity_count = sum(
        any(
            warning.get("severity") == "high"
            for warning in source.get("validation_warnings", [])
        )
        for source in sources
    )

    if not sources:
        if runs_filter:
            condition = describe_runs_filter(runs_filter)

            answer = (
                f"No stored records were found for {player} "
                f"with the exact event '{event}' and {condition}."
            )
        else:
            answer = (
                f"No stored records were found for {player} "
                f"with the exact event '{event}'."
            )

    else:
        if runs_filter:
            condition = describe_runs_filter(runs_filter)

            answer = (
                f"Found {len(sources)} stored record(s) for {player} "
                f"with the exact event '{event}' and {condition}. "
            )

        else:
            answer = (
                f"Found {len(sources)} stored record(s) for {player} "
                f"with the exact event '{event}'. "
            )

        answer += (
            "This is a count of matching stored records, not "
            "confirmation of real-world events. "
            f"{warning_count} record(s) have validation warnings; "
            f"{high_severity_count} record(s) have high-severity warnings. "
            "Treat flagged records as unverified until checked against "
            "an authoritative source."
        )

    return {
        "question": question,
        "answer": answer,
        "retrieval_method": (
            "exact_player_event_and_runs_filter"
            if runs_filter
            else "exact_player_event_filter"
        ),
        "event_filter": event,
        "player_filter": player,
        "runs_filter": runs_filter,
        "total_matching_records": len(sources),
        "validation_warning_record_count": warning_count,
        "high_severity_warning_record_count": high_severity_count,
        "sources": sources,
    }

def answer_player_records(question, player, runs_filter):
    """Return all records for one player matching a numeric runs condition."""

    points = retrieve_all_player_records(player)

    points.sort(
        key=lambda point: (
            str((point.payload or {}).get("match", "")),
            str((point.payload or {}).get("team", "")),
            str((point.payload or {}).get("over", "")),
        )
    )

    all_sources = [
        build_source(point, include_score=False)
        for point in points
    ]

    sources = apply_runs_filter(all_sources, runs_filter)

    warning_count = sum(
        bool(source.get("validation_warnings"))
        for source in sources
    )

    high_severity_count = sum(
        any(
            warning.get("severity") == "high"
            for warning in source.get("validation_warnings", [])
        )
        for source in sources
    )

    condition = describe_runs_filter(runs_filter)

    if not sources:
        answer = (
            f"No stored records were found for {player} with {condition}. "
            f"The player has {len(all_sources)} stored record(s) before "
            "applying the runs condition."
        )
    else:
        answer = (
            f"Found {len(sources)} stored record(s) for {player} "
            f"with {condition}, out of {len(all_sources)} stored "
            "record(s) before applying the runs condition. "
            f"{warning_count} matching record(s) have validation warnings; "
            f"{high_severity_count} matching record(s) have high-severity "
            "warnings. These are stored synthetic records, not confirmation "
            "of real-world events."
        )

    return {
        "question": question,
        "answer": answer,
        "retrieval_method": "exact_player_and_runs_filter",
        "player_filter": player,
        "runs_filter": runs_filter,
        "player_records_before_runs_filter": len(all_sources),
        "total_matching_records": len(sources),
        "validation_warning_record_count": warning_count,
        "high_severity_warning_record_count": high_severity_count,
        "sources": sources,
    }

def answer_all_player_events(question, player):
    """Return all stored events for one exact player."""
    points = retrieve_all_player_records(player)

    points.sort(
        key=lambda point: (
            str((point.payload or {}).get("match", "")),
            str((point.payload or {}).get("team", "")),
            str((point.payload or {}).get("over", "")),
        )
    )

    sources = [
        build_source(point, include_score=False)
        for point in points
    ]

    warning_count = sum(
        bool(source.get("validation_warnings"))
        for source in sources
    )

    if not sources:
        answer = f"No stored records were found for {player}."

    else:
        events = sorted({
            str(source["event"])
            for source in sources
            if source.get("event")
        })

        warning_summary = summarize_validation_warnings(sources)

        answer = (
            f"Found {len(sources)} stored record(s) for {player}. "
            f"Events listed: {', '.join(events)}. "
            "These are stored records, not confirmation of real-world events. "
            f"{warning_summary}"
        )

    return {
        "question": question,
        "answer": answer,
        "retrieval_method": "exact_player_filter",
        "player_filter": player,
        "total_matching_records": len(sources),
        "validation_warning_record_count": warning_count,
        "sources": sources,
    }


# ---------------------------------------------------------
# Semantic search fallback
# ---------------------------------------------------------

def answer_semantic_question(question, limit):
    """Use vector similarity for descriptive, non-exact questions."""
    query_vector = embedding_model.encode(question).tolist()

    points = qdrant_client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        limit=limit,
        with_payload=True,
        with_vectors=False,
    ).points

    sources = [build_source(point) for point in points]

    if not sources:
        answer = "No relevant stored records were found."

    else:
        context = "\n".join(
            str({
                key: source.get(key)
                for key in (
                    "timestamp",
                    "match",
                    "team",
                    "player",
                    "event",
                    "runs",
                    "over",
                    "status",
                    "commentary",
                    "validation_warnings",
                    "record_classification",
                )
            })
            for source in sources
        )

        prompt = (
            "You are an assistant analyzing stored synthetic cricket records.\n\n"

            "STRICT RULES:\n"
            "1. Answer using only the supplied records.\n"
            "2. Never invent players, matches, events, timestamps, "
            "statuses, or statistics.\n"
            "3. Do not infer wickets, runs, or other events unless "
            "explicitly supported by the records.\n"
            "4. Every observation must be traceable to a supplied record. "
            "Mention its match and player wherever available.\n"
            "5. Separate directly observed facts from interpretations. "
            "Do not infer player roles, match outcomes, or event causes "
            "unless explicitly stated in the records.\n"
            "Preserve the full meaning of the commentary. If commentary "
            "explicitly mentions another event, name that event accurately. "
            "Do not replace a named event with vague wording such as "
            "'another unspecified event'. Distinguish events mentioned "
            "in commentary from separately stored records.\n"
            "6. Treat the status field as a stored value. Report statuses "
            "such as disputed or pending review accurately, but do not "
            "automatically classify them as validation warnings.\n"
            "6. Mention validation warnings when relevant, including "
            "their severity and meaning.\n"
            "7. Do not treat a stored status such as 'confirmed' as proof "
            "of real-world accuracy.\n"
            "8. Never claim that records are disputed or pending review "
            "unless those statuses appear in the supplied records.\n"
            "9. If evidence is insufficient, explicitly say so.\n"
            "10. Do not silently correct or modify stored values.\n\n"

            f"Question: {question}\n\n"
            f"Records:\n{context}\n\n"

            "Structure your answer as follows when applicable:\n"
            "- Observations supported by records\n"
            "- Relevant data-quality concerns\n"
            "- Possible anomalies (clearly labelled as interpretations)\n"
            "- Limitations\n\n"

            "Remember: These are synthetic stored records, not verified "
            "real-world cricket events.\n\n"
            "Answer:"
        )

        response = ollama_client.generate(
            model=OLLAMA_MODEL,
            prompt=prompt,
        )

        answer = response["response"].strip()

    warning_count = sum(
        bool(source.get("validation_warnings"))
        for source in sources
    )

    return {
        "question": question,
        "answer": answer,
        "retrieval_method": "semantic_search",
        "total_matching_records": len(sources),
        "validation_warning_record_count": warning_count,
        "sources": sources,
    }


# ---------------------------------------------------------
# Main router
# ---------------------------------------------------------


def answer_question(question, limit=5):
    """Route a question to the most appropriate retrieval method."""

    try:
        limit = max(1, min(int(limit), 100))
    except (TypeError, ValueError):
        raise ValueError("Limit must be an integer.")

    # Handle unsupported wicket-statistic questions.
    if is_unsupported_wicket_stat_question(question):
        return {
            "question": question,
            "answer": (
                "I cannot reliably identify a player who took a specific "
                "number of wickets from the current dataset. The available "
                "fields contain event labels and runs, but do not provide "
                "verified bowling figures or a dedicated wickets-taken "
                "statistic. The runs field must not be interpreted as "
                "a wicket count."
            ),
            "retrieval_method": "statistic_unavailable",
            "sources": [],
        }

    # Detect numeric runs conditions.
    runs_filter = detect_runs_filter(question)

    # 1. Exact player-and-event questions.
    player_event = detect_player_event_question(question)

    if player_event:
        return answer_player_event(
            question,
            player_event["event"],
            player_event["player"],
            runs_filter=runs_filter,
        )

    # 2. Player-specific questions with numeric conditions.
    player_match = re.search(
        r"\bplayer\s+\d+\b",
        normalize_question(question),
    )

    if player_match and runs_filter:
        player = player_match.group().title()

        return answer_player_records(
            question,
            player,
            runs_filter,
        )

    # 3. Questions requesting all records for a player.
    player = detect_all_player_events_question(question)

    if player:
        return answer_all_player_events(question, player)

    # 4. Exact event questions with optional numeric conditions.
    exact_event = detect_exact_event(question)

    if exact_event:
        return answer_exact_event(
            question,
            exact_event,
            runs_filter=runs_filter,
        )

    
    # 5. Numeric-only questions across all stored records.
    if runs_filter:
        return answer_numeric_runs(
            question,
            runs_filter,
        )

    # 6. Semantic search fallback.
    return answer_semantic_question(question, limit)

