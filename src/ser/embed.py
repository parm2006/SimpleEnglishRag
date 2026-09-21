import numpy as np
from fastembed import TextEmbedding
from typing import Iterable

model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")

def embed_query(query: str) -> list[float]:
    return list(model.embed([query]))[0].tolist()

def embed_chunks(texts: Iterable[str]):
    return model.embed(texts)
