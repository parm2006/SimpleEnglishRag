import uuid
from concurrent.futures import Future, ThreadPoolExecutor
import time
from typing import Callable, Iterable, Optional
from qdrant_client import QdrantClient, models

from ser.db import COLLECTION_NAME, insert_points, search_query
from ser.embed import embed_query
from ser.hybrid import hybrid_search
from ser.ingest import Document
from ser.points import iter_chunks, iter_point_batches
from ser.rerank import rerank_points


def filter_unchanged_docs(
    docs: list[Document],
    client: QdrantClient,
) -> tuple[list[Document], int]:
    """Inspects Qdrant to skip re-embedding documents whose content_hash matches existing stored payload.
    
    Performs a batched O(1) point retrieval on chunk 0 of each candidate document.
    Returns (docs_to_index, skipped_count).
    """
    if not docs:
        return [], 0

    pt_to_doc: dict[str, Document] = {}
    for d in docs:
        if d.content_hash:
            pt_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{d.page_id}-0"))
            pt_to_doc[pt_id] = d

    if not pt_to_doc:
        return docs, 0

    try:
        # Batched retrieval: 1 network call for all candidate documents
        existing_points = client.retrieve(
            collection_name=COLLECTION_NAME,
            ids=list(pt_to_doc.keys()),
            with_payload=True,
            with_vectors=False,
        )
    except Exception:
        # Fall back safely to re-indexing if cluster lookup fails
        return docs, 0

    unchanged_page_ids: set[str] = set()
    for pt in existing_points:
        payload = pt.payload or {}
        stored_hash = payload.get("content_hash")
        matched_doc = pt_to_doc.get(str(pt.id))
        if matched_doc and stored_hash and stored_hash == matched_doc.content_hash:
            unchanged_page_ids.add(matched_doc.page_id)

    to_index = [d for d in docs if d.page_id not in unchanged_page_ids]
    skipped_count = len(unchanged_page_ids)
    return to_index, skipped_count


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
    hybrid: bool = False,
    rerank: bool = False,
) -> list[models.ScoredPoint]:
    """Retrieves top-k chunks from Qdrant with optional hybrid search and 2nd-stage cross-encoder re-ranking."""
    query_vector = embed_query(query)
    if hybrid:
        candidates = hybrid_search(client, query=query, query_vector=query_vector, k=max(k, 15))
    else:
        # Fetch candidate pool (15 candidates) from Qdrant dense vectors
        candidates = search_query(client, query_vector=query_vector, k=max(k, 15))

    if rerank:
        return rerank_points(query, candidates, top_k=k)
    return candidates[:k]


