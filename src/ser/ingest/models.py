from dataclasses import dataclass


@dataclass
class Document:
    page_id: str
    title: str
    url: str
    text: str
    source_type: str = "wiki"
