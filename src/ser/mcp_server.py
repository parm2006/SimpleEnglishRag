from mcp.server.mcpserver import MCPServer
from ser.db import client
from ser.pipeline import ask
from ser.generate import generate_answer
from ser.ingest import fetch_wiki_article
from ser.pipeline import index_documents

# Create your MCP server instance
mcp = MCPServer("ser")

@mcp.tool()

def search_wikipedia(query:str, limit:int = 3) -> str:
    """Performs semantic search across Simple English Wikipedia.
    
    Returns matching excerpts, titles, similarity scores, and Wikipedia URLs.
    Use this when you need factual verification or background sources.
    """
    chunks = ask(client,query=query,k=limit)
    if not chunks:
        return "No relevant Wikipedia articles found."
    
    results = []
    for idx, c in enumerate(chunks,1):
        payload = c.payload or {}
        title = payload.get("title","Unknown")
        url = payload.get("url","")
        text = payload.get("text", "")
        score = c.score or 0

        results.append(
            f"[{idx}] {title} (Score: {score:.4f})\nURL: {url}\n{text}\n"
        )

    return "\n---\n".join(results)


@mcp.tool()
def ask_wikipedia(question: str) -> str:
    """Answers a question using Simple English Wikipedia with strict citations.
    
    Generates a clear answer grounded strictly in retrieved sources.
    """
    chunks = ask(client, query=question, k=4)
    if not chunks or (chunks[0].score and chunks[0].score < 0.40):
        return "I could not find sufficient information in Simple English Wikipedia to answer this question."
    answer, citations = generate_answer(question, chunks)
    
    cite_text = "\n\nSources Cited:\n" + "\n".join(
        [f"[{c['index']}] {c['title']} - {c['url']}" for c in citations]
    )
    return answer + cite_text


@mcp.tool()
def index_article(title: str) -> str:
    """Fetches an article live from Simple English Wikipedia and indexes it into Qdrant Cloud.
    
    Use this if a user asks about an article that is missing from the database.
    """
    doc = fetch_wiki_article(title)
    if not doc:
        return f"Could not find article '{title}' on Simple English Wikipedia."
    
    count = index_documents([doc], client=client)
    return f"Successfully indexed {count} chunks for '{doc.title}' ({doc.url}) into Qdrant Cloud."

if __name__ == "__main__":
    mcp.run(transport="stdio")
