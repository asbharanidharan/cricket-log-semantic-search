
import json
import uuid
from pathlib import Path

from qdrant_client import QdrantClient, models
from sentence_transformers import SentenceTransformer

# Project paths
PROJECT_DIR = Path(__file__).resolve().parent.parent
INPUT_FILE = PROJECT_DIR / "data" / "cricket_logs.json"

# Qdrant configuration
QDRANT_URL = "http://127.0.0.1:6333"
COLLECTION_NAME = "cricket_logs"

# Embedding model
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
VECTOR_SIZE = 384


def create_search_text(record):
    """Combine important fields into searchable text."""
    return (
        f"Match: {record['match']}. "
        f"Team: {record['team']}. "
        f"Player: {record['player']}. "
        f"Event: {record['event']}. "
        f"Runs: {record['runs']}. "
        f"Over: {record['over']}. "
        f"Status: {record['status']}. "
        f"Commentary: {record['commentary']}"
    )


def main():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"JSON input file not found: {INPUT_FILE}"
        )

    with INPUT_FILE.open("r", encoding="utf-8") as file:
        records = json.load(file)

    if not records:
        print("No cricket records found.")
        return

    print(f"Loaded {len(records)} cricket records.")

    # Load the embedding model
    print(f"Loading embedding model: {MODEL_NAME}")
    model = SentenceTransformer(MODEL_NAME)

    # Connect to Qdrant
    client = QdrantClient(url=QDRANT_URL)
    print("Connected to Qdrant.")

    try:
        # Recreate this project's collection on each ingestion run
        if client.collection_exists(COLLECTION_NAME):
            client.delete_collection(COLLECTION_NAME)
            print("Removed the existing practice collection.")

        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=models.VectorParams(
                size=VECTOR_SIZE,
                distance=models.Distance.COSINE,
            ),
        )

        print("Qdrant collection created.")

        texts = [create_search_text(record) for record in records]

        print("Generating embeddings...")
        embeddings = model.encode(
            texts,
            batch_size=32,
            show_progress_bar=True,
            normalize_embeddings=True,
        )

        points = []

        for record, text, embedding in zip(
            records, texts, embeddings
        ):
            point_id = str(uuid.uuid4())

            payload = {
                **record,
                "search_text": text,
            }

            points.append(
                models.PointStruct(
                    id=point_id,
                    vector=embedding.tolist(),
                    payload=payload,
                )
            )

        print("Uploading embeddings to Qdrant...")

        client.upload_points(
            collection_name=COLLECTION_NAME,
            points=points,
            batch_size=64,
            wait=True,
        )

        info = client.get_collection(COLLECTION_NAME)

        print("\n--- Qdrant Ingestion Report ---")
        print(f"Input records: {len(records)}")
        print(f"Points uploaded: {len(points)}")
        print(f"Points reported by Qdrant: {info.points_count}")
        print(f"Collection: {COLLECTION_NAME}")
        print(f"Vector dimensions: {VECTOR_SIZE}")

        if info.points_count == len(records):
            print("SUCCESS: All records stored in Qdrant.")
        else:
            print("WARNING: The stored point count differs from input.")

    finally:
        client.close()


if __name__ == "__main__":
    main()
