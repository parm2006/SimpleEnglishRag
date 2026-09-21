from typing import Iterable
from qdrant_client import QdrantClient, models

from simpleenglishrag.db import COLLECTION_NAME, insert_points, search_query
from simpleenglishrag.embed import embed_query
from simpleenglishrag.ingest import Document
from simpleenglishrag.points import iter_chunks, iter_point_batches


def index_documents(
    docs: Iterable[Document],
    client: QdrantClient,
    batch_size: int = 64,
    chunk_size: int = 500,
    overlap: int = 100,
) -> int:
    """Streams documents, chunks them, micro-batches embeddings, and upserts to Qdrant.

    Operates in constant memory O(batch_size).
    """
    chunk_stream = iter_chunks(docs, chunk_size=chunk_size, overlap=overlap)
    point_batches = iter_point_batches(chunk_stream, batch_size=batch_size)

    total_chunks = 0
    for batch in point_batches:
        insert_points(client, batch)
        total_chunks += len(batch)
        print(f"Indexed {total_chunks} chunks into '{COLLECTION_NAME}'...")

    return total_chunks


def ask(client: QdrantClient, query: str, k: int = 5) -> list[models.ScoredPoint]:
    """Embeds a natural language question and retrieves top-k matching passages."""
    query_vector = embed_query(query)
    return search_query(client, query_vector=query_vector, k=k)
