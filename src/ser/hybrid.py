"""Hybrid Search Engine for SER.
Combines Dense Semantic Vectors (FastEmbed ONNX) with Lexical BM25 Scoring
and Qdrant Full-Text Title Matching via Reciprocal Rank Fusion (RRF).
"""

from typing import Optional
import numpy as np
from fastembed import SparseTextEmbedding
from qdrant_client import QdrantClient, models

from ser.db import COLLECTION_NAME, search_query

_bm25_instance: Optional[SparseTextEmbedding] = None


def get_bm25_model() -> SparseTextEmbedding:
    """Lazy-loads the FastEmbed BM25 sparse model singleton."""
    global _bm25_instance
    if _bm25_instance is None:
        _bm25_instance = SparseTextEmbedding("Qdrant/bm25")
    return _bm25_instance


def search_lexical_titles(client: QdrantClient, query: str, limit: int = 10) -> list[models.ScoredPoint]:
    """Retrieves candidate chunks matching exact query words in the article title."""
    try:
        response = client.query_points(
            collection_name=COLLECTION_NAME,
            query_filter=models.Filter(
                should=[
                    models.FieldCondition(key="title", match=models.MatchText(text=query)),
                ]
            ),
            limit=limit,
            with_payload=True,
        )
        return response.points
    except Exception:
        # Graceful fallback if title index is optimizing
        return []


def hybrid_search(
    client: QdrantClient,
    query: str,
    query_vector: list[float],
    k: int = 15,
    w_dense: float = 0.6,
    w_bm25: float = 0.4,
    rrf_k: int = 60,
) -> list[models.ScoredPoint]:
    """Performs hybrid retrieval fusing dense vector search with BM25 lexical scoring via RRF.

    1. Retrieves top dense semantic candidates from Qdrant Cloud.
    2. Retrieves lexical title candidates from Qdrant full-text index.
    3. Merges candidates and computes sparse BM25 scores across the combined pool.
    4. Applies Reciprocal Rank Fusion (RRF) to blend semantic and lexical rankings.
    """
    # 1. Fetch dense candidates
    dense_candidates = search_query(client, query_vector=query_vector, k=max(k, 15))

    # 2. Fetch lexical title matches
    lexical_candidates = search_lexical_titles(client, query=query, limit=10)

    # 3. Deduplicate candidate pool
    candidates_dict: dict[str, models.ScoredPoint] = {}
    dense_rank_map: dict[str, int] = {}

    for rank, point in enumerate(dense_candidates, 1):
        candidates_dict[str(point.id)] = point
        dense_rank_map[str(point.id)] = rank

    for point in lexical_candidates:
        p_id = str(point.id)
        if p_id not in candidates_dict:
            candidates_dict[p_id] = point

    all_candidates = list(candidates_dict.values())
    if not all_candidates:
        return []

    # 4. Compute BM25 scores on the candidate pool
    bm25 = get_bm25_model()
    q_sparse = list(bm25.embed([query]))[0]
    q_dict = dict(zip(q_sparse.indices, q_sparse.values))

    candidate_texts = [
        f"{p.payload.get('title', '')} {p.payload.get('breadcrumb', '')}\n{p.payload.get('text', '')}"
        if p.payload
        else ""
        for p in all_candidates
    ]

    doc_sparses = list(bm25.embed(candidate_texts))

    bm25_scores = []
    for d_vec in doc_sparses:
        d_dict = dict(zip(d_vec.indices, d_vec.values))
        score = sum(q_dict[i] * d_dict[i] for i in set(q_dict) & set(d_dict))
        bm25_scores.append(score)

    # Rank by BM25 (1-based rank)
    bm25_order = np.argsort(bm25_scores)[::-1]
    bm25_rank_map: dict[str, int] = {}
    for r, idx in enumerate(bm25_order, 1):
        bm25_rank_map[str(all_candidates[idx].id)] = r

    # 5. Reciprocal Rank Fusion (RRF)
    fused_points = []
    max_dense_rank = len(dense_candidates) + 10
    max_bm25_rank = len(all_candidates) + 10

    for p in all_candidates:
        p_id = str(p.id)
        r_dense = dense_rank_map.get(p_id, max_dense_rank)
        r_bm25 = bm25_rank_map.get(p_id, max_bm25_rank)

        rrf_score = (w_dense / (rrf_k + r_dense)) + (w_bm25 / (rrf_k + r_bm25))

        fused_points.append(
            models.ScoredPoint(
                id=p.id,
                version=p.version,
                score=float(rrf_score),
                payload=p.payload,
                vector=p.vector,
            )
        )

    fused_points.sort(key=lambda pt: pt.score, reverse=True)
    return fused_points[:k]
