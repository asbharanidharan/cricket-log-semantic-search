
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

QDRANT_URL = "http://127.0.0.1:6333"
COLLECTION_NAME = "cricket_logs"
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def main():
    print("Loading embedding model...")
    model = SentenceTransformer(MODEL_NAME)

    client = QdrantClient(url=QDRANT_URL)

    try:
        info = client.get_collection(COLLECTION_NAME)
        print(f"Qdrant collection: {COLLECTION_NAME}")
        print(f"Stored points: {info.points_count}")

        query = input("\nEnter your cricket search query: ").strip()

        if not query:
            print("Please enter a search query.")
            return

        # Convert the query into a vector using the same model
        query_vector = model.encode(
            query,
            normalize_embeddings=True,
        ).tolist()

        # Find the most semantically similar records
        results = client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            limit=5,
            with_payload=True,
        ).points

        print("\n--- Semantic Search Results ---")

        if not results:
            print("No matching records found.")
            return

        for rank, point in enumerate(results, start=1):
            record = point.payload or {}

            print(f"\nResult {rank}")
            print(f"Similarity score: {point.score:.4f}")
            print(f"Match: {record.get('match', 'N/A')}")
            print(f"Team: {record.get('team', 'N/A')}")
            print(f"Player: {record.get('player', 'N/A')}")
            print(f"Event: {record.get('event', 'N/A')}")
            print(f"Runs: {record.get('runs', 'N/A')}")
            print(f"Over: {record.get('over', 'N/A')}")
            print(f"Status: {record.get('status', 'N/A')}")
            print(f"Commentary: {record.get('commentary', 'N/A')}")

    finally:
        client.close()


if __name__ == "__main__":
    main()
