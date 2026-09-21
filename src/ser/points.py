import uuid
from itertools import batched
from typing import Iterable, Iterator
from qdrant_client import models
from ser.chunk import Chunk, create_chunks
from ser.embed import embed_chunks
from ser.ingest import Document


def iter_chunks(
    docs: Iterable[Document], chunk_size: int = 1200, overlap: int = 200
) -> Iterator[Chunk]:
    """Lazily yields chunks from an iterable stream of documents."""
    for doc in docs:
        if not doc:
            continue
        for chunk in create_chunks(doc, chunk_size=chunk_size, overlap=overlap):
            if chunk:
                yield chunk


def create_points(chunks: list[Chunk]) -> list[models.PointStruct]:
    """Embeds a batch of chunks and converts them into Qdrant PointStruct instances."""
    if not chunks:
        return []

    texts = [c.text for c in chunks]
    vectors = list(embed_chunks(texts))

    points: list[models.PointStruct] = []
    for chunk, vector in zip(chunks, vectors):
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk.chunk_id))
        payload = {
            "chunk_id": chunk.chunk_id,
            "doc_id": chunk.doc_id,
            "title": chunk.title,
            "url": chunk.url,
            "chunk_index": chunk.chunk_index,
            "text": chunk.text,
        }
        points.append(
            models.PointStruct(
                id=point_id,
                vector=vector.tolist() if hasattr(vector, "tolist") else list(vector),
                payload=payload,
            )
        )
    return points


def iter_point_batches( chunks: Iterable[Chunk], batch_size: int = 64 
    ) -> Iterator[list[models.PointStruct]]:
    """Micro-batches chunks from a stream, embedding and yielding PointStruct lists."""
    for chunk_batch in batched(chunks, batch_size):
        yield create_points(list(chunk_batch))
