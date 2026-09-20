from dataclasses import dataclass
from simpleenglishrag.ingest import fetch_wiki_article, Document


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


def create_chunks(doc:Document, chunk_size:int = 500, overlap:int = 100) -> list[Chunk | None]:
    text = doc.text
    chunks = []
    start = 0
    count = 0
    doc_id = doc.page_id
    url = doc.url
    title = doc.title
    while start < len(text):
        end = start+chunk_size
        chunk_text = text[start:end]
        chunk_id = f"{doc_id}-{count}"
        chk = Chunk(
            chunk_id=chunk_id,
            doc_id=doc_id,
            title=title,
            url=url,
            chunk_index=count,
            text=chunk_text,
        )
        chunks.append(chk)
        count+=1
        start += chunk_size-overlap
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
    
    
    
