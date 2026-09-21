from simpleenglishrag.db import client, init_collection
from simpleenglishrag.ingest import fetch_wiki_article
from simpleenglishrag.pipeline import ask, index_documents


def main() -> None:
    print("=== Simple English Wikipedia RAG Pipeline ===")
    init_collection(client)

    # 1. Stream sample articles
    sample_topics = ["Mathematics", "Physics", "Computer science"]
    print(f"Fetching articles: {sample_topics}...")
    docs = [doc for topic in sample_topics if (doc := fetch_wiki_article(topic))]

    # 2. Index documents via generator & micro-batching
    print("Indexing documents into Qdrant...")
    total = index_documents(docs, client=client, batch_size=32)
    print(f"Successfully indexed {total} chunks across {len(docs)} articles.\n")

    # 3. Query the collection
    test_queries = [
        "What is the study of matter and energy?",
        "How do algorithms and computers solve problems?",
        "What are the different branches of math?",
    ]

    for q in test_queries:
        print(f"Query: \"{q}\"")
        results = ask(client, q, k=2)
        for rank, r in enumerate(results, 1):
            payload = r.payload or {}
            title = payload.get("title", "Unknown")
            url = payload.get("url", "")
            snippet = payload.get("text", "")[:180].replace("\n", " ")
            print(f"  [{rank}] Score: {r.score:.4f} | {title} ({url})")
            print(f"      Snippet: {snippet}...\n")


if __name__ == "__main__":
    main()
