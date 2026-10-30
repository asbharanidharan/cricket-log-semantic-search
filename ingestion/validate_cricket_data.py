
import json
from collections import Counter, defaultdict
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = PROJECT_DIR / "data" / "cricket_logs.json"

# These are expected batter runs for the event types,
# assuming "runs" means runs scored by the batter on that event.
EXPECTED_RUNS = {
    "six hit": 6,
    "four hit": 4,
}


def main():
    if not DATA_FILE.exists():
        print(f"ERROR: Dataset not found: {DATA_FILE}")
        return

    with DATA_FILE.open("r", encoding="utf-8") as file:
        records = json.load(file)

    if not isinstance(records, list):
        print("ERROR: Expected a JSON list of records.")
        return

    print("=" * 60)
    print("CRICKET DATA VALIDATION REPORT")
    print("=" * 60)
    print(f"Total records: {len(records)}")

    # 1. Check required fields.
    required_fields = [
        "timestamp", "match", "team", "player",
        "event", "runs", "over", "status", "commentary"
    ]

    missing_counts = Counter()
    invalid_records = []

    for index, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            invalid_records.append(index)
            continue

        for field in required_fields:
            value = record.get(field)
            if value is None or value == "":
                missing_counts[field] += 1

    print("\n--- Missing or Empty Fields ---")
    if missing_counts:
        for field, count in missing_counts.items():
            print(f"{field}: {count}")
    else:
        print("No missing required fields found.")

    if invalid_records:
        print(f"Records that are not JSON objects: {invalid_records}")

    # 2. Count event types.
    event_counts = Counter(
        str(record.get("event") or "").strip().lower()
        for record in records
        if isinstance(record, dict)
    )

    print("\n--- Event Distribution ---")
    for event, count in event_counts.most_common():
        print(f"{event or '[missing event]'}: {count}")

    # 3. Check sixes and fours against runs.
    mismatches = defaultdict(list)
    invalid_run_values = []

    for index, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            continue

        event = str(record.get("event") or "").strip().lower()
        runs = record.get("runs")

        if event in EXPECTED_RUNS:
            expected = EXPECTED_RUNS[event]

            # Reject booleans and non-numeric values.
            if isinstance(runs, bool) or not isinstance(runs, (int, float)):
                invalid_run_values.append((index, event, runs))
            elif runs != expected:
                mismatches[event].append({
                    "record_number": index,
                    "match": record.get("match"),
                    "team": record.get("team"),
                    "player": record.get("player"),
                    "runs": runs,
                    "over": record.get("over"),
                    "status": record.get("status"),
                })

    print("\n--- Six and Four Run Validation ---")
    for event, expected in EXPECTED_RUNS.items():
        event_records = [
            record for record in records
            if isinstance(record, dict)
            and str(record.get("event") or "").strip().lower() == event
        ]
        bad_records = mismatches[event]

        print(f"\nEvent: {event}")
        print(f"Records found: {len(event_records)}")
        print(f"Expected runs under this assumption: {expected}")
        print(f"Records with different runs: {len(bad_records)}")

        for item in bad_records[:10]:
            print(
                f"  Record #{item['record_number']}: "
                f"player={item['player']}, team={item['team']}, "
                f"runs={item['runs']}, over={item['over']}, "
                f"status={item['status']}"
            )

        if len(bad_records) > 10:
            print(f"  ... and {len(bad_records) - 10} more")

    if invalid_run_values:
        print("\nNon-numeric or missing runs for four/six events:")
        for item in invalid_run_values[:10]:
            print(f"  Record #{item[0]}: event={item[1]}, runs={item[2]}")

    # 4. Check general run-value validity.
    negative_runs = []
    for index, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            continue

        runs = record.get("runs")
        if (
            isinstance(runs, (int, float))
            and not isinstance(runs, bool)
            and runs < 0
        ):
            negative_runs.append((index, runs))

    print("\n--- General Numeric Checks ---")
    print(f"Negative run values: {len(negative_runs)}")
    for item in negative_runs[:10]:
        print(f"  Record #{item[0]}: runs={item[1]}")

    print("\n--- Validation Complete ---")
    print("Original dataset was only read; no records were changed.")


if __name__ == "__main__":
    main()
