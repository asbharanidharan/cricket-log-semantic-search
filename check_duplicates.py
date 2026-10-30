
import json
from collections import defaultdict
from pathlib import Path

DATA_FILE = Path("data/cricket_logs.json")


def make_key(record, fields):
    return tuple(record.get(field) for field in fields)


def find_groups(records, fields):
    groups = defaultdict(list)

    for index, record in enumerate(records):
        groups[make_key(record, fields)].append((index, record))

    return {
        key: items
        for key, items in groups.items()
        if len(items) > 1
    }


def main():
    with DATA_FILE.open("r", encoding="utf-8") as file:
        records = json.load(file)

    if not isinstance(records, list):
        raise ValueError("Expected the JSON dataset to contain a list.")

    exact_groups = find_groups(
        records,
        list(records[0].keys()) if records else [],
    )

    event_identity_fields = [
        "match",
        "player",
        "event",
        "over",
        "timestamp",
    ]

    event_identity_groups = find_groups(
        records,
        event_identity_fields,
    )

    broader_groups = find_groups(
        records,
        ["match", "player", "event", "over"],
    )

    conflicting_groups = {}

    for key, items in broader_groups.items():
        timestamps = {
            record.get("timestamp")
            for _, record in items
        }
        runs_values = {
            record.get("runs")
            for _, record in items
        }

        if len(timestamps) > 1 or len(runs_values) > 1:
            conflicting_groups[key] = items

    empty_commentary = [
        (index, record)
        for index, record in enumerate(records)
        if (
            isinstance(record.get("commentary"), str)
            and "()" in record["commentary"]
        )
    ]

    print(f"Total records: {len(records)}")
    print(f"Exact duplicate groups: {len(exact_groups)}")
    print(f"Same event identity groups: {len(event_identity_groups)}")
    print(f"Potential conflict groups: {len(conflicting_groups)}")
    print(f"Commentary placeholder records: {len(empty_commentary)}")

    print("\nEXACT DUPLICATE GROUPS")
    for key, items in exact_groups.items():
        print(f"Rows {[index for index, _ in items]}: {key}")

    print("\nSAME EVENT IDENTITY GROUPS")
    for key, items in event_identity_groups.items():
        print(f"Rows {[index for index, _ in items]}: {key}")

    print("\nPOTENTIAL CONFLICT GROUPS")
    for key, items in conflicting_groups.items():
        print(f"\nIdentity: {key}")

        for index, record in items:
            print(
                f"  Row {index}: "
                f"timestamp={record.get('timestamp')!r}, "
                f"runs={record.get('runs')!r}, "
                f"status={record.get('status')!r}"
            )

    print("\nCOMMENTARY PLACEHOLDER EXAMPLES")
    for index, record in empty_commentary[:10]:
        print(
            f"Row {index}: "
            f"{record.get('match')} / {record.get('player')} / "
            f"{record.get('event')} / "
            f"{record.get('commentary')!r}"
        )


if __name__ == "__main__":
    main()
