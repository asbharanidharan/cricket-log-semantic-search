
import re


def validate_cricket_record(record):
    """
    Return data-quality warnings without modifying the original record.

    Warnings indicate possible inconsistencies, not confirmed factual errors.
    """

    warnings = []

    event = str(record.get("event") or "").strip().lower()
    commentary = str(record.get("commentary") or "")
    runs = record.get("runs")
    over = record.get("over")
    status = str(record.get("status") or "").strip().lower()

    def add_warning(code, severity, message):
        warnings.append({
            "code": code,
            "severity": severity,
            "message": message,
        })

    valid_integer_runs = (
        isinstance(runs, int)
        and not isinstance(runs, bool)
    )

    # Rule 1: A six hit normally contributes six runs from the hit.
    if event == "six hit" and valid_integer_runs and runs != 6:
        add_warning(
            "six_hit_runs_mismatch",
            "high",
            f"Event is 'six hit', but runs is {runs}. "
            "Verify the meaning of the runs field."
        )

    # Rule 2: A boundary hit commonly contributes four or six runs.
    if (
        event == "boundary hit"
        and valid_integer_runs
        and runs not in (4, 6)
    ):
        add_warning(
            "boundary_runs_suspicious",
            "medium",
            f"Event is 'boundary hit', but runs is {runs}. "
            "Verify the event and runs field."
        )

    
    # Rule 3: Check for missing or placeholder commentary.
    if not commentary.strip():
        add_warning(
            "empty_commentary",
            "medium",
            "Commentary is missing or empty."
        )
    elif "()" in commentary:
        add_warning(
            "empty_commentary_placeholder",
            "medium",
            "Commentary contains an empty placeholder: ()."
        )

        # Identify the context of the placeholder.
        if re.search(
            r"\bPlayer\s+\d+\s*\(\)",
            commentary,
            re.IGNORECASE,
        ):
            add_warning(
                "missing_player_context",
                "medium",
                "An empty placeholder follows a player name in commentary."
            )

        elif re.search(
            r"\bat\s*\(\)",
            commentary,
            re.IGNORECASE,
        ):
            add_warning(
                "missing_location_context",
                "medium",
                "An empty placeholder follows 'at' in commentary."
            )

        elif re.search(
            r"\bStadium\s+\d+\s*\(\)",
            commentary,
            re.IGNORECASE,
        ):
            add_warning(
                "missing_stadium_context",
                "medium",
                "An empty placeholder follows a stadium name in commentary."
            )

        else:
            add_warning(
                "unclassified_commentary_placeholder",
                "low",
                "An empty commentary placeholder needs manual classification."
            )

    # Rule 4: Compare run counts explicitly stated in commentary.
    # Covers phrases such as "scored 3 runs" and "adding 4 runs".
    run_patterns = [
        r"\bscored\s+(\d+)\s+runs?\b",
        r"\badding\s+(\d+)\s+runs?\b",
        r"\badded\s+(\d+)\s+runs?\b",
    ]

    commentary_counts = set()

    for pattern in run_patterns:
        for match in re.finditer(pattern, commentary, re.I):
            commentary_counts.add(int(match.group(1)))

    if valid_integer_runs and commentary_counts:
        if any(count != runs for count in commentary_counts):
            add_warning(
                "commentary_runs_mismatch",
                "high",
                f"Commentary mentions run count(s) "
                f"{sorted(commentary_counts)}, but the structured "
                f"runs field is {runs}."
            )

    # Rule 5: Flag implausible over values without assuming a match format.
    # The valid range depends on the competition and data schema.
    if isinstance(over, int) and not isinstance(over, bool):
        if over < 0:
            add_warning(
                "negative_over",
                "high",
                f"Over value is negative ({over}); verify the record."
            )
        elif over > 50:
            add_warning(
                "over_outside_common_range",
                "medium",
                f"Over value is {over}. Verify the match format "
                "and whether this field uses whole overs or ball notation."
            )

    # Rule 6: Verification status does not override quality warnings.
    if status == "verified" and warnings:
        add_warning(
            "verified_record_has_warnings",
            "medium",
            "Record is marked 'verified' but has data-quality "
            "warnings. Review the record; its status was not changed."
        )

    return warnings

def classify_cricket_record(record, warnings=None):
    """
    Classify data quality and review status separately.

    This is a rule-based classification, not proof of factual accuracy.
    It does not modify the original record.
    """

    if warnings is None:
        warnings = validate_cricket_record(record)

    status = str(record.get("status") or "").strip().lower()

    # Preserve the record's original status as a separate dimension.
    if status == "disputed":
        review_status = "disputed"
    elif status in {"pending review", "pending_review"}:
        review_status = "pending_review"
    elif status == "confirmed":
        review_status = "confirmed"
    elif status == "verified":
        review_status = "verified"
    else:
        review_status = "unknown"

    # Classify only the checks this validator actually performs.
    if any(w.get("severity") == "high" for w in warnings):
        data_quality = "high_risk"
    elif warnings:
        data_quality = "needs_review"
    else:
        data_quality = "no_detected_issues"

    return {
        "review_status": review_status,
        "data_quality": data_quality,
        "validation_warning_count": len(warnings),
        "requires_review": (
            data_quality != "no_detected_issues"
            or review_status in {"disputed", "pending_review", "unknown"}
        ),
        "confidence_note": (
            "Rule-based data-quality classification only; "
            "it does not establish whether the record is factually true."
        ),
    }
