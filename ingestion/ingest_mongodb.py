
import json
from pathlib import Path

from pymongo import MongoClient
from pymongo.errors import PyMongoError

PROJECT_DIR = Path(__file__).resolve().parent.parent
INPUT_FILE = PROJECT_DIR / "data" / "cricket_logs.json"

MONGO_URI = "mongodb://127.0.0.1:27017/"
DATABASE_NAME = "cricket_db"
COLLECTION_NAME = "match_logs"


def main():
    if not INPUT_FILE.exists():
        print(f"ERROR: JSON file not found: {INPUT_FILE}")
        return

    with INPUT_FILE.open("r", encoding="utf-8") as file:
        records = json.load(file)

    if not records:
        print("ERROR: No records found in JSON.")
        return

    client = MongoClient(
        MONGO_URI,
        serverSelectionTimeoutMS=5000
    )

    try:
        client.admin.command("ping")
        print("Connected to MongoDB successfully!")

        collection = client[DATABASE_NAME][COLLECTION_NAME]

        # Replace the contents of this practice collection
        collection.delete_many({})

        result = collection.insert_many(records)
        total = collection.count_documents({})

        print("\n--- MongoDB Ingestion Report ---")
        print(f"Records in JSON: {len(records)}")
        print(f"Records inserted: {len(result.inserted_ids)}")
        print(f"Documents in MongoDB: {total}")
        print(f"Database: {DATABASE_NAME}")
        print(f"Collection: {COLLECTION_NAME}")

        print("\nSample document:")
        print(json.dumps(
            collection.find_one({}, {"_id": 0}),
            indent=2,
            default=str
        ))

    except PyMongoError as error:
        print(f"MongoDB error: {error}")

    finally:
        client.close()


if __name__ == "__main__":
    main()
