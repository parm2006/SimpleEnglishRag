import os
from pathlib import Path
from dotenv import load_dotenv
from qdrant_client import QdrantClient, models

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv()

QDRANT_STORAGE = os.getenv("QDRANT_STORAGE", "local").lower()
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

_raw_local_path = os.getenv("QDRANT_LOCAL_PATH", "data/qdrant_db")
QDRANT_LOCAL_PATH = (
    str(PROJECT_ROOT / _raw_local_path)
    if not os.path.isabs(_raw_local_path)
    else _raw_local_path
)
COLLECTION_NAME = os.getenv("QDRANT_COLLECTION", "simple_wiki")


def get_client() -> QdrantClient:
    if QDRANT_STORAGE == "cloud" and QDRANT_URL:
        return QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
    elif QDRANT_STORAGE == "memory":
        return QdrantClient(":memory:")
    # Default: local SSD storage
    os.makedirs(QDRANT_LOCAL_PATH, exist_ok=True)
    return QdrantClient(path=QDRANT_LOCAL_PATH)


client = get_client()

import atexit
atexit.register(client.close)


def init_collection(client: QdrantClient) -> None:
    if not client.collection_exists(COLLECTION_NAME):
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=models.VectorParams(
                size=384,
                distance=models.Distance.COSINE,
                on_disk=True,
            ),
            quantization_config=models.ScalarQuantization(
                scalar=models.ScalarQuantizationConfig(
                    type=models.ScalarType.INT8,
                    quantile=0.99,
                    always_ram=True,
                )
            ),
            on_disk_payload=True,
            hnsw_config=models.HnswConfigDiff(
                m=16,
                ef_construct=100,
                on_disk=True,
            ),
        )


def insert_points(
    client: QdrantClient, points: list[models.PointStruct], max_retries: int = 5
) -> None:
    import time
    for attempt in range(1, max_retries + 1):
        try:
            client.upsert(collection_name=COLLECTION_NAME, points=points, wait=True)
            return
        except Exception as e:
            if attempt == max_retries:
                raise
            delay = min(2 ** attempt, 30)
            print(f"[Warning] Upsert failed (attempt {attempt}/{max_retries}): {e}. Retrying in {delay}s...")
            time.sleep(delay)


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


