import csv
import io
import uuid
from pathlib import Path
from ser.ingest.models import Document


def extract_tabular_file(path: Path, rows_per_batch: int = 30) -> Document:
    """Extracts CSV and TSV files into schema-aware Markdown tables with repeated headers."""
    resolved = path.resolve()
    url = resolved.as_uri()
    page_id = str(uuid.uuid5(uuid.NAMESPACE_URL, url))
    title = resolved.stem.replace("_", " ").replace("-", " ").title()

    try:
        content = resolved.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        content = resolved.read_text(encoding="latin-1", errors="replace")

    delimiter = "\t" if resolved.suffix.lower() == ".tsv" else ","
    reader = csv.reader(io.StringIO(content), delimiter=delimiter)

    try:
        headers = [h.strip() for h in next(reader)]
    except StopIteration:
        return Document(
            page_id=page_id,
            title=title,
            url=url,
            text=f"# Empty Table: {title}\n",
            source_type="table",
        )

    # Format Markdown header row
    header_line = "| " + " | ".join(headers) + " |"
    separator_line = "| " + " | ".join(["---"] * len(headers)) + " |"

    sections: list[str] = [f"# Dataset: {title}\n\nSchema: {', '.join(headers)}\n"]

    current_rows: list[str] = []
    batch_start = 1
    row_count = 0

    for row in reader:
        if not any(cell.strip() for cell in row):
            continue
        row_count += 1
        # Pad or trim row to match header count
        padded_row = [row[i].strip() if i < len(row) else "" for i in range(len(headers))]
        current_rows.append("| " + " | ".join(padded_row) + " |")

        if len(current_rows) >= rows_per_batch:
            batch_end = batch_start + len(current_rows) - 1
            section_md = (
                f"## Rows {batch_start}–{batch_end}\n\n"
                f"{header_line}\n{separator_line}\n" + "\n".join(current_rows) + "\n"
            )
            sections.append(section_md)
            current_rows = []
            batch_start = batch_end + 1

    if current_rows:
        batch_end = batch_start + len(current_rows) - 1
        section_md = (
            f"## Rows {batch_start}–{batch_end}\n\n"
            f"{header_line}\n{separator_line}\n" + "\n".join(current_rows) + "\n"
        )
        sections.append(section_md)

    return Document(
        page_id=page_id,
        title=title,
        url=url,
        text="\n\n".join(sections),
        source_type="table",
    )
