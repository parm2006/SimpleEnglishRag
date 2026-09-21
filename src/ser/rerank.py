"""Local ONNX Cross-Encoder Re-ranker for Second-Stage Retrieval.
Uses INT8-quantized BAAI/bge-reranker-base to re-score candidate passages
retrieved from Qdrant via joint query-document cross-attention.
"""


from typing import Optional
import numpy as np
import onnxruntime as ort
from huggingface_hub import hf_hub_download
from qdrant_client import models
from tokenizers import Tokenizer

MODEL_REPO = "Xenova/bge-reranker-base"
MODEL_FILE = "onnx/model_quantized.onnx"
TOKENIZER_FILE = "tokenizer.json"


class LocalReranker:
    def __init__(self, max_length: int = 256):
        tok_path = hf_hub_download(repo_id=MODEL_REPO, filename=TOKENIZER_FILE)
        model_path = hf_hub_download(repo_id=MODEL_REPO, filename=MODEL_FILE)

        self.tokenizer = Tokenizer.from_file(tok_path)
        self.tokenizer.enable_padding()
        self.tokenizer.enable_truncation(max_length = max_length)

        opts = ort.SessionOptions()
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        opts.intra_op_num_threads = 4

        self.session = ort.InferenceSession(model_path,sess_options=opts)


    def score_pairs(self,query: str, texts: list[str]) -> np.ndarray:
        """Compute cross-encoder scores for (query, text) pairs.
        Returns raw logits array of shape (N,)"""
        if not texts:
            return np.array([],dtype=np.float32)

        pairs = [(query,text) for text in texts]

        enc = self.tokenizer.encode_batch(pairs)

        input_ids = np.array([e.ids for e in enc], dtype = np.int64)
        attention_mask  = np.array([e.attention_mask for e in enc], dtype = np.int64)

        inputs = {"input_ids":input_ids, "attention_mask":attention_mask}
        outputs = self.session.run(None,inputs)

        logits = outputs[0].squeeze(-1)

        #Siggmod activation: maps raw logits to confidence prodabilties [0.0 to 1.0]
        scores = 1 / (1 + np.exp(-logits)).astype(np.float32)

        return scores

_reranker_instance: Optional[LocalReranker] = None

def get_reranker() -> LocalReranker:
    global _reranker_instance
    if _reranker_instance is None:
        _reranker_instance = LocalReranker()
    return _reranker_instance


def rerank_points(
    query:str,
    points: list[models.ScoredPoint],
    top_k: int = 5,
    ) -> list[models.ScoredPoint]:

    if not points or len(points) <= 1:
        return points[:top_k]

    reranker = get_reranker()

    candidate_texts = [
        f"{p.payload.get('breadcrumb', '')}\n\n{p.payload.get('text', '')}".strip()
        if p.payload.get("breadcrumb")
        else p.payload.get("text", "")
        for p in points
    ]

    scores = reranker.score_pairs(query, candidate_texts)

    reranked = []
    
    for point, new_score in zip(points,scores):
        reranked_point = models.ScoredPoint(
            id = point.id, 
            version = point.version,
            score=float(new_score),
            payload = point.payload,
            vector=point.vector,
        )
        reranked.append(reranked_point)

    
    reranked.sort(key=lambda p: p.score, reverse=True)
    return reranked[:top_k]