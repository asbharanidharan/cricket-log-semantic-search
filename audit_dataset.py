
import csv
import json
from collections import Counter
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
DATA_FILE = PROJECT_DIR / "data" / "cricket_logs.json"
REPORT_FILE = PROJECT_DIR / "audit_report.csv"

REQUIRED_FIELDS = [
    "timestamp", "match", "team", "player",
    "event", "runs", "over", "status", "commentary"
]


def main():
    if not DATA_FILE.exists():
        print(f"Dataset not found: {DATA_FILE}")
        return

    with DATA_FILE.open("r", encoding="utf-8") as file:
        records = json.load(file)

    if not isinstance(records, list):
        print("ERROR: Expected the dataset to contain a JSON list.")
        return

    issues = []
    exact_records = Counter(
        json.dumps(record, sort_keys=True, ensure_ascii=False)
        for record in records
    )
    seen = set()
    event_counts = Counter()
    flagged_indices = set()

    def flag(index, record, category, severity, explanation):
        flagged_indices.add(index)
        issues.append({
            "record_number": index + 1,
            "category": category,
            "severity": severity,
            "explanation": explanation,
            "match": record.get("match", ""),
            "player": record.get("player", ""),
            "event": record.get("event", ""),
            "runs": record.get("runs", ""),
            "over": record.get("over", ""),
            "status": record.get("status", ""),
            "timestamp": record.get("timestamp", ""),
            "commentary": record.get("commentary", "")
        })

    for index, record in enumerate(records):
        if not isinstance(record, dict):
            flag(index, {}, "invalid_record", "HIGH",
                 "Record is not a JSON object.")
            continue

        for field in REQUIRED_FIELDS:
            if field not in record or record[field] is None:
                flag(index, record, "missing_field", "HIGH",
                     f"Missing required field: {field}")
            elif isinstance(record[field], str) and not record[field].strip():
                flag(index, record, "empty_field", "MEDIUM",
                     f"Empty required field: {field}")

        event = str(record.get("event", "")).strip().lower()
        event_counts[event] += 1

        # Exact duplicate check
        serialized = json.dumps(
            record, sort_keys=True, ensure_ascii=False
        )
        if serialized in seen:
            flag(index, record, "exact_duplicate", "MEDIUM",
                 "Record is an exact duplicate of an earlier record.")
        seen.add(serialized)

        # Numeric validation
        runs = record.get("runs")
        over = record.get("over")

        if isinstance(runs, bool) or not isinstance(runs, int):
            flag(index, record, "invalid_runs_type", "HIGH",
                 "Runs should be an integer.")
        elif not 0 <= runs <= 6:
            flag(index, record, "runs_out_of_range", "MEDIUM",
                 "Runs are outside the expected 0-6 range; confirm the field's meaning.")

        if isinstance(over, bool) or not isinstance(over, int):
            flag(index, record, "invalid_over_type", "HIGH",
                 "Over should be an integer.")
        elif not 1 <= over <= 50:
            flag(index, record, "over_out_of_range", "MEDIUM",
                 "Over is outside the assumed 1-50 range.")

        # Event-specific consistency checks
        if event == "six hit" and isinstance(runs, int) and not isinstance(runs, bool) and runs != 6:
            flag(index, record, "six_hit_runs_mismatch", "HIGH",
                 "A six hit normally means 6 runs from the hit; verify the runs field.")

        if event == "boundary hit" and isinstance(runs, int) and not isinstance(runs, bool) and runs not in (4, 6):
            flag(index, record, "boundary_runs_suspicious", "MEDIUM",
                 "A boundary commonly means 4 or 6 runs; verify the event and runs.")

        # Placeholder and commentary consistency checks
        commentary = str(record.get("commentary", ""))
        if "()" in commentary:
            flag(index, record, "empty_commentary_placeholder", "MEDIUM",
                 "Commentary contains an empty parenthesis placeholder.")

        import re
        match = re.search(r"\bscored\s+(\d+)\s+runs?\b", commentary, re.I)
        if match and isinstance(runs, int) and not isinstance(runs, bool):
            commentary_runs = int(match.group(1))
            if commentary_runs != runs:
                flag(index, record, "commentary_runs_mismatch", "HIGH",
                     f"Commentary says {commentary_runs} runs but structured runs is {runs}.")

    columns = [
        "record_number", "category", "severity", "explanation",
        "match", "player", "event", "runs", "over", "status",
        "timestamp", "commentary"
    ]

    with REPORT_FILE.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(issues)

    category_counts = Counter(issue["category"] for issue in issues)
    duplicate_groups = sum(
        count > 1 for count in exact_records.values()
    )

    print("\n===== DATASET AUDIT SUMMARY =====")
    print(f"Total records: {len(records)}")
    print(f"Records with at least one warning: {len(flagged_indices)}")
    print(f"Total warnings: {len(issues)}")
    print(f"Exact duplicate groups: {duplicate_groups}")
    print("\nWarnings by category:")

    for category, count in category_counts.most_common():
        print(f"  {category}: {count}")

    print("\nEvent counts:")
    for event, count in event_counts.most_common():
        print(f"  {event or '(empty event)'}: {count}")

    print(f"\nDetailed report saved to: {REPORT_FILE}")
    print("Original dataset was not modified.")


if __name__ == "__main__":
    main()
