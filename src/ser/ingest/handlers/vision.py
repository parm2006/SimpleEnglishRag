import asyncio
import base64
import os
import uuid
from pathlib import Path
import httpx
from ser.ingest.models import Document


def _windows_ocr(path: Path) -> str:
    """Uses native Windows Media OCR API via winsdk (0 MB download, hardware-accelerated)."""
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

        return asyncio.run(_run())
    except Exception as e:
        return f"[OCR Error: {e}]"


def _ollama_vision(path: Path) -> str:
    """Uses local Ollama vision model (e.g. llama3.2-vision) for deep multimodal scene understanding."""
    model_name = os.getenv("OLLAMA_VISION_MODEL", "llama3.2-vision:11b")
    ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")

    try:
        b64 = base64.b64encode(path.read_bytes()).decode("utf-8")
        resp = httpx.post(
            f"{ollama_host}/api/generate",
            json={
                "model": model_name,
                "prompt": "Describe this image in detail. Transcribe all text, numbers, labels, and summarize any diagrams or charts accurately.",
                "images": [b64],
                "stream": False,
            },
            timeout=30.0,
        )
        if resp.status_code == 200:
            return resp.json().get("response", "").strip()
    except Exception:
        pass
    # Fallback to Windows OCR if Ollama Vision is unavailable
    return _windows_ocr(path)


def ocr_scanned_pdf(path: Path) -> str:
    """Extracts page images from a scanned PDF and OCRs each page."""
    import pymupdf
    doc = pymupdf.open(str(path.resolve()))
    sections: list[str] = [f"# Scanned Document: {path.stem}\n"]

    temp_img_path = Path.home() / ".cache" / "ser" / "temp_page.png"
    temp_img_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        for idx, page in enumerate(doc, 1):
            pix = page.get_pixmap(dpi=150)
            pix.save(str(temp_img_path))
            page_text = _windows_ocr(temp_img_path).strip()
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

    backend = os.getenv("VISION_BACKEND", "windows_ocr").lower()
    if backend == "ollama":
        text_content = _ollama_vision(resolved)
    else:
        text_content = _windows_ocr(resolved)

    doc_text = f"# Image: {title}\n\n{text_content}"

    return Document(
        page_id=page_id,
        title=title,
        url=url,
        text=doc_text,
        source_type="image",
    )
