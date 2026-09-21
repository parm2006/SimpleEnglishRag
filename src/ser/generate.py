import json
import os
from typing import Iterator
import httpx
from qdrant_client import models

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.40"))
PREFERRED_MODELS = [
    "llama3.2:3b",
    "llama3.2",
    "qwen2.5:3b",
    "qwen2.5:7b",
    "qwen3:0.6b",
    "llama3.1:8b",
]


def get_local_model() -> str | None:
    """Detects available models in the local Ollama instance."""
    try:
        resp = httpx.get(f"{OLLAMA_HOST}/api/tags", timeout=2.0)
        if resp.status_code == 200:
            installed = [m["name"] for m in resp.json().get("models", [])]
            for pref in PREFERRED_MODELS:
                for inst in installed:
                    if inst == pref or inst.startswith(pref):
                        return inst
            if installed:
                return installed[0]
    except Exception:
        pass
    return None


SYSTEM_INSTRUCTION = """You are a precise, factual assistant that answers questions using ONLY the provided Simple English Wikipedia excerpts.

Rules:
1. Answer the question using ONLY the facts explicitly stated in the context below. Do NOT assume, extrapolate, or bring in outside knowledge.
2. For every factual statement you make, add footnote citations like [1], [2] pointing to the source snippet used.
3. If the provided excerpts do not contain the answer, reply ONLY with: "I could not find sufficient information in the provided Wikipedia sources to answer this question."
4. Keep your explanation clear, simple, and direct.
"""


def build_context_block(chunks: list[models.ScoredPoint]) -> tuple[str, list[dict]]:
    """Builds numbered context snippets and citation metadata."""
    sources = []
    blocks = []
    for idx, c in enumerate(chunks, 1):
        payload = c.payload or {}
        title = payload.get("title", "Unknown")
        url = payload.get("url", "")
        text = payload.get("text", "").strip()
        sources.append({"index": idx, "title": title, "url": url, "score": c.score})
        blocks.append(f"[{idx}] Source: {title} ({url})\n{text}")
    return "\n\n".join(blocks), sources


def stream_answer(
    query: str,
    chunks: list[models.ScoredPoint],
    model: str | None = None,
) -> Iterator[str]:
    """Streams generated answer tokens using local Ollama with anti-hallucination guardrail."""
    if not chunks or (chunks[0].score is not None and chunks[0].score < CONFIDENCE_THRESHOLD):
        yield "I could not find sufficient information in the provided Wikipedia sources to answer this question."
        return

    selected_model = model or os.getenv("OLLAMA_MODEL") or get_local_model()
    if not selected_model:
        yield "Error: No local Ollama model found. Please run 'ollama run llama3.2:3b' or start Ollama."
        return

    context_text, _ = build_context_block(chunks)
    prompt = f"{SYSTEM_INSTRUCTION}\n\nContext Excerpts:\n{context_text}\n\nQuestion: {query}\n\nAnswer:"

    payload = {
        "model": selected_model,
        "prompt": prompt,
        "stream": True,
        "options": {
            "temperature": 0.2,  # Low temperature for strict factual grounding
        },
    }

    try:
        with httpx.stream(
            "POST",
            f"{OLLAMA_HOST}/api/generate",
            json=payload,
            timeout=30.0,
        ) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if line:
                    data = json.loads(line)
                    token = data.get("response", "")
                    if token:
                        yield token
                    if data.get("done", False):
                        break
    except Exception as e:
        yield f"\n[Generation Error: {e}]"


def generate_answer(
    query: str,
    chunks: list[models.ScoredPoint],
    model: str | None = None,
) -> tuple[str, list[dict]]:
    """Generates a complete answer string along with citation metadata."""
    _, sources = build_context_block(chunks)
    answer = "".join(stream_answer(query, chunks, model=model))
    return answer, sources
