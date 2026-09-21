import os
from qdrant_client import QdrantClient, models


QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")


def get_client() -> QdrantClient:
    if QDRANT_URL:
        return QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
    return QdrantClient(":memory:")


client = get_client()

COLLECTION_NAME = os.getenv("QDRANT_COLLECTION", "test_collection")


def init_collection(client: QdrantClient) -> None:
    if not client.collection_exists(COLLECTION_NAME):
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=models.VectorParams(
                size=384,
                distance=models.Distance.COSINE,
            ),
            hnsw_config=models.HnswConfigDiff(
                m=16,
                ef_construct=100,
            ),
        )


def insert_points(client: QdrantClient, points: list[models.PointStruct]) -> None:
    client.upsert(collection_name=COLLECTION_NAME, points=points)


def search_query(
    client: QdrantClient, query_vector: list[float], k: int = 5
) -> list[models.ScoredPoint]:
    response = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        limit=k,
        with_payload=True,
    )
    return response.points


