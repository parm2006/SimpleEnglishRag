import os
from pathlib import Path
import httpx

DUMP_URL = "https://dumps.wikimedia.org/simplewiki/latest/simplewiki-latest-pages-articles.xml.bz2"
USER_AGENT = "SimpleEnglishRAG/0.1 (educational project; contact: github.com/parm2006/SimpleEnglishRag)"


def download_dump(
    dest_dir: str = "data",
    filename: str = "simplewiki-latest-pages-articles.xml.bz2",
    url: str = DUMP_URL,
) -> Path:
    """Streams and downloads the compressed Wikipedia dump with progress tracking."""
    dest_path = Path(dest_dir)
    dest_path.mkdir(parents=True, exist_ok=True)
    target_file = dest_path / filename

    headers = {"User-Agent": USER_AGENT}

    # 1. Check if complete file already exists
    with httpx.Client(headers=headers, follow_redirects=True) as client:
        head_resp = client.head(url)
        head_resp.raise_for_status()
        total_bytes = int(head_resp.headers.get("content-length", 0))

    if target_file.exists() and total_bytes > 0 and target_file.stat().st_size == total_bytes:
        print(f"Dump file already downloaded: {target_file} ({total_bytes / (1024*1024):.1f} MB)")
        return target_file

    print(f"Downloading Simple English Wikipedia dump ({total_bytes / (1024*1024):.1f} MB)...")
    temp_file = target_file.with_suffix(".part")

    downloaded = 0
    # Resume partial download if supported
    resume_headers = dict(headers)
    if temp_file.exists():
        downloaded = temp_file.stat().st_size
        resume_headers["Range"] = f"bytes={downloaded}-"

    with httpx.stream("GET", url, headers=resume_headers, follow_redirects=True) as resp:
        # If server doesn't support Range, start over
        if resp.status_code == 416 or (resp.status_code == 200 and downloaded > 0):
            downloaded = 0
            mode = "wb"
        elif resp.status_code == 206:
            mode = "ab"
        else:
            resp.raise_for_status()
            mode = "wb"

        with open(temp_file, mode) as f:
            for chunk in resp.iter_bytes(chunk_size=1024 * 1024):  # 1 MB chunk
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_bytes > 0:
                        pct = (downloaded / total_bytes) * 100
                        mb_done = downloaded / (1024 * 1024)
                        mb_total = total_bytes / (1024 * 1024)
                        print(f"\rProgress: {mb_done:.1f} MB / {mb_total:.1f} MB ({pct:.1f}%)", end="", flush=True)

    print()
    temp_file.replace(target_file)
    print(f"Download complete: {target_file}")
    return target_file


if __name__ == "__main__":
    download_dump()
