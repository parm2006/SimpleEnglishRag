from dataclasses import dataclass
from ser.ingest import fetch_wiki_article, Document


# class Document:
#     page_id: str
#     title: str
#     url: str
#     text: str
@dataclass
class Chunk:
    chunk_id: str
    doc_id:str
    title:str
    url:str
    chunk_index:int
    text:str


def create_chunks(
    doc: Document, chunk_size: int = 1200, overlap: int = 200
) -> list[Chunk]:
    text = doc.text.strip()
    if len(text) < 150 or text == "NOT FOUND":
        return []

    chunks: list[Chunk] = []
    start = 0
    count = 0
    doc_id = doc.page_id
    url = doc.url
    title = doc.title

    while start < len(text):
        end = start + chunk_size
        if end < len(text):
            space_pos = text.rfind(" ", start + (chunk_size // 2), end)
            if space_pos != -1:
                end = space_pos

        chunk_text = text[start:end].strip()
        if chunk_text:
            chk = Chunk(
                chunk_id=f"{doc_id}-{count}",
                doc_id=doc_id,
                title=title,
                url=url,
                chunk_index=count,
                text=chunk_text,
            )
            chunks.append(chk)
            count += 1

        start = end - overlap
        if start >= len(text) - overlap:
            break

    return chunks

def main() -> None:
    doc = fetch_wiki_article("Math")
    if not doc:
        print("could not fetch document")
        return
    chunks = create_chunks(doc)
    if not chunks:
        print("could not create chunks")
        return
    print(chunks)


if __name__ == "__main__":
    main()
    
    
    
