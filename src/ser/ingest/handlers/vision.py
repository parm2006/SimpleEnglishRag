import asyncio
import base64
import os
import sys
import uuid
from pathlib import Path
import httpx
from ser.ingest.models import Document


def has_windows_ocr() -> bool:
    """Checks if native Windows Media OCR is available on this system."""
    if sys.platform != "win32":
        return False
    try:
        import winsdk.windows.media.ocr  # noqa: F401
        return True
    except ImportError:
        return False


def _windows_ocr(path: Path) -> str:
    """Uses native Windows Media OCR API via winsdk (0 MB download, hardware-accelerated)."""
    if not has_windows_ocr():
        return "[Windows OCR is only available on Windows with winsdk installed]"

    try:
        import winsdk.windows.media.ocr as ocr
        import winsdk.windows.graphics.imaging as imaging
        import winsdk.windows.storage as storage

        async def _run():
            resolved_str = str(path.resolve())
            sf = await storage.StorageFile.get_file_from_path_async(resolved_str)
            stream = await sf.open_async(storage.FileAccessMode.READ)
            dec = await imaging.BitmapDecoder.create_async(stream)
            bmp = await dec.get_software_bitmap_async()
            engine = ocr.OcrEngine.try_create_from_user_profile_languages()
            if not engine:
                engine = ocr.OcrEngine.try_create_from_language(ocr.OcrEngine.available_recognizer_languages[0])
            result = await engine.recognize_async(bmp)
            return "\n".join(line.text for line in result.lines)

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(asyncio.run, _run()).result()
        else:
            return asyncio.run(_run())
    except Exception as e:
        return f"[OCR Error: {e}]"


PREFERRED_VISION_MODELS = [
    "moondream",
    "llama3.2-vision:11b",
    "llama3.2-vision",
    "minicpm-v",
    "llava",
    "qwen2-vl",
]


def get_vision_model(ollama_host: str = "http://localhost:11434") -> str:
    """Detects installed vision model in Ollama or falls back to env variable / moondream."""
    env_model = os.getenv("OLLAMA_VISION_MODEL")
    if env_model:
        return env_model
    try:
        resp = httpx.get(f"{ollama_host}/api/tags", timeout=2.0)
        if resp.status_code == 200:
            installed = [m["name"] for m in resp.json().get("models", [])]
            for pref in PREFERRED_VISION_MODELS:
                for inst in installed:
                    if inst == pref or inst.startswith(pref) or pref in inst:
                        return inst
    except Exception:
        pass
    return "moondream:latest"


def check_ollama_vision(ollama_host: str = "http://localhost:11434") -> tuple[bool, str]:
    """Checks if Ollama is running and whether a supported vision model is installed.
    Returns:
      (True, <model_name>) if a vision model is installed and Ollama is reachable.
      (False, "ollama_not_running") if Ollama is not installed or unreachable.
      (False, "no_vision_model") if Ollama is running, but no vision model is installed.
    """
    try:
        resp = httpx.get(f"{ollama_host}/api/tags", timeout=1.5)
        if resp.status_code == 200:
            installed = [m.get("name", "") for m in resp.json().get("models", [])]
            for pref in PREFERRED_VISION_MODELS:
                for inst in installed:
                    if inst == pref or inst.startswith(pref) or pref in inst:
                        return True, inst
            return False, "no_vision_model"
    except Exception:
        return False, "ollama_not_running"
    return False, "no_vision_model"


_notified_no_ollama = False


def _notify_no_ollama(status: str) -> None:
    """Notifies the user once that no Ollama vision model was found, shows command, and explains fallback."""
    global _notified_no_ollama
    if _notified_no_ollama:
        return
    _notified_no_ollama = True

    from rich.console import Console
    console = Console()

    if status == "ollama_not_running":
        if has_windows_ocr():
            console.print("[yellow]Notice: Ollama is not running. Using Windows OCR as a fallback.[/yellow]")
            console.print("[dim cyan]To enable multimodal visual understanding, start Ollama and run: 'ollama run moondream'[/dim cyan]")
        else:
            console.print("[yellow]Notice: Ollama is not running and Windows OCR is unavailable.[/yellow]")
            console.print("[dim cyan]To enable image ingestion, start Ollama and run: 'ollama run moondream'[/dim cyan]")
    else:  # "no_vision_model"
        if has_windows_ocr():
            console.print("[yellow]Notice: No Ollama vision model found. Using Windows OCR as a fallback.[/yellow]")
            console.print("[dim cyan]To enable multimodal visual understanding, run: 'ollama run moondream' or 'ollama pull moondream'[/dim cyan]")
        else:
            console.print("[yellow]Notice: No Ollama vision model found and Windows OCR is unavailable.[/yellow]")
            console.print("[dim cyan]To enable image ingestion, run: 'ollama run moondream' or 'ollama pull moondream'[/dim cyan]")


def _ollama_vision(
    path: Path,
    prompt: str = "Describe this image in detail. Transcribe all text, numbers, labels, and summarize any diagrams or charts accurately.",
    model_override: str | None = None,
) -> str:
    """Uses local Ollama vision model (e.g. moondream, llama3.2-vision) for deep multimodal scene understanding."""
    ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    model_name = model_override or get_vision_model(ollama_host)
    timeout_sec = float(os.getenv("OLLAMA_VISION_TIMEOUT", "120.0"))

    try:
        b64 = base64.b64encode(path.read_bytes()).decode("utf-8")
        resp = httpx.post(
            f"{ollama_host}/api/generate",
            json={
                "model": model_name,
                "prompt": prompt,
                "images": [b64],
                "stream": False,
            },
            timeout=timeout_sec,
        )
        if resp.status_code == 200:
            return resp.json().get("response", "").strip()
    except Exception:
        pass
    # Fallback to Windows OCR if available on Windows, else empty
    if has_windows_ocr():
        return _windows_ocr(path)
    return ""


def ocr_scanned_pdf(path: Path) -> str:
    """Extracts page images from a scanned PDF and OCRs each page via Ollama vision or Windows OCR."""
    import pymupdf
    doc = pymupdf.open(str(path.resolve()))
    sections: list[str] = [f"# Scanned Document: {path.stem}\n"]

    temp_img_path = Path.home() / ".cache" / "ser" / "temp_page.png"
    temp_img_path.parent.mkdir(parents=True, exist_ok=True)

    has_vision, status_or_model = check_ollama_vision()
    if not has_vision:
        _notify_no_ollama(status_or_model)

    try:
        for idx, page in enumerate(doc, 1):
            pix = page.get_pixmap(dpi=150)
            pix.save(str(temp_img_path))
            if has_vision:
                page_text = _ollama_vision(
                    temp_img_path,
                    prompt="Transcribe all text from this scanned document page accurately verbatim.",
                    model_override=status_or_model,
                ).strip()
            elif has_windows_ocr():
                page_text = _windows_ocr(temp_img_path).strip()
            else:
                page_text = ""
            if page_text:
                sections.append(f"## Page {idx}\n\n{page_text}\n")
    finally:
        doc.close()
        if temp_img_path.exists():
            temp_img_path.unlink()

    return "\n".join(sections)


def extract_image_file(path: Path) -> Document:
    """Extracts text or scene understanding from image files (.png, .jpg, etc.)."""
    resolved = path.resolve()
    url = resolved.as_uri()
    page_id = str(uuid.uuid5(uuid.NAMESPACE_URL, url))
    title = resolved.stem.replace("_", " ").replace("-", " ").title()

    backend = os.getenv("VISION_BACKEND", "auto").lower()

    if backend == "windows_ocr" and has_windows_ocr():
        text_content = _windows_ocr(resolved)
    elif backend == "ollama":
        text_content = _ollama_vision(resolved)
    else:  # "auto": check if Ollama vision model is installed first, fallback to Windows OCR
        has_vision, status_or_model = check_ollama_vision()
        if has_vision:
            text_content = _ollama_vision(resolved, model_override=status_or_model)
        else:
            _notify_no_ollama(status_or_model)
            if has_windows_ocr():
                text_content = _windows_ocr(resolved)
            else:
                text_content = (
                    "[Notice: No Ollama vision model found and Windows OCR is unavailable. "
                    "Run 'ollama run moondream' to enable image processing.]"
                )

    doc_text = f"# Image: {title}\n\n{text_content}"

    return Document(
        page_id=page_id,
        title=title,
        url=url,
        text=doc_text,
        source_type="image",
    )
