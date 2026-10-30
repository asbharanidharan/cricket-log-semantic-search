
import re
import json
from pathlib import Path

# Find the project directory and input/output files
PROJECT_DIR = Path(__file__).resolve().parent.parent
INPUT_FILE = PROJECT_DIR / "data" / "cricket_log.txt"
OUTPUT_FILE = PROJECT_DIR / "data" / "cricket_logs.json"

# Match each field using the known labels in the raw log format
LOG_PATTERN = re.compile(
    r"^\[(?P<timestamp>[^\]]+)\]\s+"
    r"Match:(?P<match>\S+)\s+"
    r"Team:(?P<team>.*?)\s+"
    r"Player:(?P<player>.*?)\s+"
    r"Event:(?P<event>.*?)\s+"
    r"Runs:(?P<runs>-?\d+)\s+"
    r"Over:(?P<over>-?\d+)\s+"
    r"Status:(?P<status>.*?)\s+"
    r"Commentary:(?P<commentary>.*)$"
)


def parse_log_line(line):
    """Parse one cricket log line into a structured dictionary."""
    match = LOG_PATTERN.match(line.strip())

    if not match:
        return None

    record = match.groupdict()

    # Convert numeric fields to integers
    record["runs"] = int(record["runs"])
    record["over"] = int(record["over"])

    # Normalize whitespace in text fields
    for field in ["team", "player", "event", "status", "commentary"]:
        record[field] = record[field].strip()

    return record


def main():
    if not INPUT_FILE.exists():
        print(f"ERROR: Input file not found: {INPUT_FILE}")
        return

    records = []
    invalid_lines = []

    with INPUT_FILE.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue

            record = parse_log_line(line)

            if record is None:
                invalid_lines.append(line_number)
            else:
                records.append(record)

    # Save parsed records as JSON
    with OUTPUT_FILE.open("w", encoding="utf-8") as file:
        json.dump(records, file, indent=2, ensure_ascii=False)

    print("\n--- Cricket Log Parsing Report ---")
    print(f"Total valid records: {len(records)}")
    print(f"Total invalid lines: {len(invalid_lines)}")
    print(f"Invalid line numbers: {invalid_lines}")
    print(f"Output saved to: {OUTPUT_FILE}")

    if records:
        print("\nFirst parsed record:")
        print(json.dumps(records[0], indent=2))


if __name__ == "__main__":
    main()
