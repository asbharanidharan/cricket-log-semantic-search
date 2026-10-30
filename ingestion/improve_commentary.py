
import json
from pathlib import Path


# --------------------------------------------------
# File paths
# --------------------------------------------------

PROJECT_DIR = Path(__file__).resolve().parent.parent
INPUT_FILE = PROJECT_DIR / "data" / "cricket_logs.json"
OUTPUT_FILE = PROJECT_DIR / "data" / "cricket_logs_improved.json"


# --------------------------------------------------
# Commentary generation
# --------------------------------------------------

def generate_commentary(record):
    """Generate clearer commentary using recorded event details."""

    player = str(record.get("player") or "").strip()
    team = str(record.get("team") or "").strip()
    event = str(record.get("event") or "").strip().lower()
    status = str(record.get("status") or "").strip()

    runs = record.get("runs")
    over = record.get("over")

    player_text = player if player else "The player"
    team_text = f" for {team}" if team else ""
    over_text = f"over {over}" if over is not None else "an unspecified over"

    # Run-scoring event
    if event == "run scored":
        if runs == 1:
            sentence = (
                f"{player_text}{team_text} recorded 1 run "
                f"in {over_text}."
            )
        elif runs is not None:
            sentence = (
                f"{player_text}{team_text} recorded {runs} runs "
                f"in {over_text}."
            )
        else:
            sentence = (
                f"A run-scoring event involving {player_text}"
                f"{team_text} was recorded in {over_text}."
            )

    # Boundary events
    elif event == "six hit":
        sentence = (
            f"A six-hit event involving {player_text}"
            f"{team_text} was recorded in {over_text}."
        )

    elif event == "four hit":
        sentence = (
            f"A four-hit event involving {player_text}"
            f"{team_text} was recorded in {over_text}."
        )

    # Wicket events
    elif event == "wicket taken":
        sentence = (
            f"A wicket was recorded{team_text} in {over_text}. "
            f"The record identifies {player_text}."
        )

    elif event == "lbw given":
        sentence = (
            f"An LBW decision involving {player_text}"
            f"{team_text} was recorded in {over_text}."
        )

    elif event == "stumping":
        sentence = (
            f"A stumping event involving {player_text}"
            f"{team_text} was recorded in {over_text}."
        )

    elif event == "catch taken":
        sentence = (
            f"A catch event involving {player_text}"
            f"{team_text} was recorded in {over_text}."
        )

    elif event == "run out":
        sentence = (
            f"A run-out event involving {player_text}"
            f"{team_text} was recorded in {over_text}."
        )

    # Other event types
    else:
        event_text = event if event else "an unspecified event"
        sentence = (
            f"The recorded event '{event_text}' involved "
            f"{player_text}{team_text} in {over_text}."
        )

    # Add the existing record status, if available
    if status:
        sentence += f" Record status: {status}."

    return sentence


# --------------------------------------------------
# Main processing
# --------------------------------------------------

def main():
    if not INPUT_FILE.exists():
        print(f"ERROR: Input file not found: {INPUT_FILE}")
        return

    try:
        with INPUT_FILE.open("r", encoding="utf-8") as file:
            records = json.load(file)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: Could not read input JSON: {exc}")
        return

    if not isinstance(records, list):
        print("ERROR: Expected the JSON file to contain a list of records.")
        return

    improved_records = []

    for original_record in records:
        if not isinstance(original_record, dict):
            print("WARNING: Skipping a record that is not a JSON object.")
            continue

        # Preserve all existing fields; change commentary only.
        record = original_record.copy()
        record["commentary"] = generate_commentary(record)
        improved_records.append(record)

    # Write to a separate output file. Never overwrite the original JSON.
    try:
        with OUTPUT_FILE.open("w", encoding="utf-8") as file:
            json.dump(
                improved_records,
                file,
                indent=2,
                ensure_ascii=False,
            )
    except OSError as exc:
        print(f"ERROR: Could not write output JSON: {exc}")
        return

    print("\n--- Commentary Improvement Report ---")
    print(f"Original records: {len(records)}")
    print(f"Processed records: {len(improved_records)}")
    print(f"Original file preserved: {INPUT_FILE.name}")
    print(f"New file created: {OUTPUT_FILE.name}")

    if improved_records:
        print("\n--- Example Before and After ---")
        print("BEFORE:")
        print(records[0].get("commentary", ""))
        print("\nAFTER:")
        print(improved_records[0]["commentary"])

    print("\n--- Wicket Commentary Check ---")
    wicket_records = [
        record
        for record in improved_records
        if str(record.get("event") or "").strip().lower() == "wicket taken"
    ]

    if wicket_records:
        for record in wicket_records[:3]:
            print(record["commentary"])
    else:
        print("No 'wicket taken' records found.")


if __name__ == "__main__":
    main()
