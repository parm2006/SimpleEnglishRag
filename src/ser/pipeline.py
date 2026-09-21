from concurrent.futures import Future, ThreadPoolExecutor
import time
from typing import Callable, Iterable, Optional
from qdrant_client import QdrantClient, models

from ser.db import COLLECTION_NAME, insert_points, search_query
from ser.embed import embed_query
from ser.ingest import Document
from ser.points import iter_chunks, iter_point_batches
from ser.rerank import rerank_points


def index_documents(
    docs: Iterable[Document],
    client: QdrantClient,
    batch_size: int = 128,
    chunk_size: int = 1200,
    overlap: int = 200,
    on_progress: Optional[Callable[[int, float], None]] = None,
) -> int:
    """Indexes a stream of documents into Qdrant using pipelined background uploads."""
    chunk_stream = iter_chunks(docs, chunk_size=chunk_size, overlap=overlap)
    point_batches = iter_point_batches(chunk_stream, batch_size=batch_size)

    total_chunks = 0
    t0 = time.time()
    last_future: Optional[Future] = None

    with ThreadPoolExecutor(max_workers=2) as executor:
        for batch in point_batches:
            if last_future is not None:
                last_future.result()

            batch_len = len(batch)
            total_chunks += batch_len

            # Launch cloud upload in background while main thread embeds next batch
            last_future = executor.submit(insert_points, client, batch)

            elapsed = max(time.time() - t0, 0.001)
            rate = total_chunks / elapsed
            if on_progress:
                on_progress(total_chunks, rate)
            else:
                print(f"Indexed {total_chunks} chunks ({rate:.1f} chunks/sec) into '{COLLECTION_NAME}'...", flush=True)

        if last_future is not None:
            last_future.result()

    return total_chunks


def ask(
    client: QdrantClient,
    query: str,
    k: int = 5,
    rerank: bool = False,
) -> list[models.ScoredPoint]:
    """Retrieves top-k chunks from Qdrant with optional 2nd-stage cross-encoder re-ranking."""
    query_vector = embed_query(query)
    # Always fetch a candidate pool (15 candidates) from Qdrant
    candidates = search_query(client, query_vector=query_vector, k=max(k, 15))
    if rerank:
        return rerank_points(query, candidates, top_k=k)
    return candidates[:k]


