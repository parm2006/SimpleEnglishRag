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


_clients: dict[str, QdrantClient] = {}


def get_storage_client(storage: str) -> QdrantClient:
    """Returns a cached QdrantClient for a specific storage mode ('cloud', 'local', or 'memory')."""
    storage = storage.lower()
    if storage in _clients:
        return _clients[storage]

    url = os.getenv("QDRANT_URL", QDRANT_URL)
    api_key = os.getenv("QDRANT_API_KEY", QDRANT_API_KEY)
    if storage == "cloud":
        if not url:
            raise ValueError("QDRANT_URL is required for cloud storage.")
        c = QdrantClient(url=url, api_key=api_key, timeout=60.0)
    elif storage == "local":
        os.makedirs(QDRANT_LOCAL_PATH, exist_ok=True)
        c = QdrantClient(path=QDRANT_LOCAL_PATH)
    elif storage == "memory":
        c = QdrantClient(":memory:")
    else:
        raise ValueError(f"Unknown storage type: {storage}")

    _clients[storage] = c
    return c


def get_client() -> QdrantClient:
    storage = os.getenv("QDRANT_STORAGE", QDRANT_STORAGE).lower()
    return get_storage_client(storage)


client = get_client()

import atexit


def _cleanup_clients():
    for c in list(_clients.values()):
        try:
            c.close()
        except Exception:
            pass


atexit.register(_cleanup_clients)


def init_collection(client: QdrantClient, collection_name: str = COLLECTION_NAME) -> None:
    if not client.collection_exists(collection_name):
        client.create_collection(
            collection_name=collection_name,
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
        # Create full-text payload indexes for hybrid search (server-only, harmless on local)
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            try:
                client.create_payload_index(
                    collection_name=collection_name,
                    field_name="title",
                    field_schema=models.TextIndexParams(
                        type=models.TextIndexType.TEXT,
                        tokenizer=models.TokenizerType.WORD,
                        lowercase=True,
                    ),
                )
                client.create_payload_index(
                    collection_name=collection_name,
                    field_name="text",
                    field_schema=models.TextIndexParams(
                        type=models.TextIndexType.TEXT,
                        tokenizer=models.TokenizerType.WORD,
                        lowercase=True,
                        on_disk=True,
                    ),
                    wait=False,
                )
            except Exception:
                pass


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


