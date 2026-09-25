import os
import subprocess
import sys
import uuid
from pathlib import Path
from ser.ingest.models import Document

CACHE_DIR = Path.home() / ".cache" / "ser" / "models" / "whisper"


def _ensure_faster_whisper() -> None:
    try:
        import faster_whisper  # noqa: F401
    except ImportError:
        raise RuntimeError(
            "Audio ingestion requires 'faster-whisper'.\n"
            "To enable audio support in this environment, run:\n"
            "    uv sync --extra audio\n"
            "or: pip install faster-whisper"
        )


def extract_audio_file(path: Path) -> Document:
    """Extracts spoken audio into a timestamped Markdown Document using faster-whisper."""
    _ensure_faster_whisper()
    from faster_whisper import WhisperModel

    resolved = path.resolve()
    url = resolved.as_uri()
    page_id = str(uuid.uuid5(uuid.NAMESPACE_URL, url))
    title = resolved.stem.replace("_", " ").replace("-", " ").title()

    model_name = os.getenv("AUDIO_MODEL", "tiny.en")
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    model = WhisperModel(
        model_name,
        device="cpu",
        compute_type="int8",
        download_root=str(CACHE_DIR),
    )

    segments, info = model.transcribe(str(resolved))

    lines = [f"# Audio Transcript: {title} (Language: {info.language})\n"]
    for s in segments:
        start_min, start_sec = divmod(int(s.start), 60)
        end_min, end_sec = divmod(int(s.end), 60)
        timestamp = f"[{start_min:02d}:{start_sec:02d} – {end_min:02d}:{end_sec:02d}]"
        lines.append(f"### {timestamp}\n{s.text.strip()}\n")

    return Document(
        page_id=page_id,
        title=title,
        url=url,
        text="\n".join(lines),
        source_type="audio",
    )
