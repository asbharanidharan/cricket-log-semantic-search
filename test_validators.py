
from backend.search_api.validators import validate_cricket_record

record = {
    "event": "six hit",
    "runs": 2,
    "commentary": "Player 6 () performed six hit, adding 2 runs.",
}

original_record = record.copy()
warnings = validate_cricket_record(record)

print("Original record:", record)
print("\nWarnings:")
for warning in warnings:
    print(warning)

assert record == original_record, "Validator modified the original record!"
assert any(
    warning["code"] == "six_hit_runs_mismatch"
    for warning in warnings
)

print("\nPASS: Warning generated and original record preserved.")
