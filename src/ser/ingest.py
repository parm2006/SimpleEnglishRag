from dataclasses import dataclass
import httpx
import json


@dataclass
class Document:
    page_id: str
    title: str
    url: str
    text: str


def fetch_wiki_article(title:str) -> Document | None: 
    url = "https://simple.wikipedia.org/w/api.php"
    headers = {
        "User-Agent" : "SimpleEnglishRAG/0.1 (educational project)"
    }
    params = {
        "action" : "query",
        "prop" : "extracts",
        "explaintext" : "1",
        "titles" : title,
        "format" : "json",
        "redirects" : "1",
    }

    response = httpx.get(url,params=params,headers=headers)
    response.raise_for_status() 
    data = response.json()
    # print(json.dumps(data,indent=4,ensure_ascii=False))
    pages = data.get("query",{}).get("pages",{})
    if not pages: #the article gave no pages
        return None
    for page_id, page_info in pages.items():
        if page_id == "-1":
            return None
        return Document(
            page_id=page_id,
            title=page_info.get("title", "NOT FOUND"),
            url=f"https://simple.wikipedia.org/wiki/{page_info.get('title', title).replace(' ', '_')}",
            text=page_info.get("extract", "NOT FOUND"),
        )

def main() -> None:
    doc = fetch_wiki_article("Math")
    if doc:
        print(doc)
    else:
        print("could not find document")


if __name__ == "__main__":
    main()

    