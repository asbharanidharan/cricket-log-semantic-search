
import json
import re
from collections import Counter
from pathlib import Path

data_file = Path("data/cricket_logs.json")

with data_file.open("r", encoding="utf-8") as file:
    records = json.load(file)

patterns = Counter()
examples = {}

for index, record in enumerate(records):
    commentary = record.get("commentary", "")

    if not isinstance(commentary, str) or "()" not in commentary:
        continue

    if re.search(r"\bat\s*\(\)", commentary, re.IGNORECASE):
        pattern = "Missing location/context after 'at'"
    elif re.search(r"\bPlayer\s+\d+\s*\(\)", commentary, re.IGNORECASE):
        pattern = "Missing information after player name"
    else:
        pattern = "Other empty-parentheses pattern"

    patterns[pattern] += 1
    examples.setdefault(pattern, {
        "row": index,
        "match": record.get("match"),
        "player": record.get("player"),
        "event": record.get("event"),
        "commentary": commentary,
    })

print("COMMENTARY PLACEHOLDER CLASSIFICATION")
print("=" * 45)

for pattern, count in patterns.most_common():
    print(f"\n{pattern}: {count}")
    print("Example:", examples[pattern])

print(f"\nTotal affected records: {sum(patterns.values())}")
