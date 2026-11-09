"""Retrieval over the KB with the source-authority filters from kb/authority.py applied.

Retriever.search() returns chunks with chunk_id, doc_id, article, url, score (cosine similarity, higher is better) and
a formatted citation. Mode 'current' never returns repealed law (R5); 'global' returns comparison sources only (R6).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import chromadb

from kb.authority import combined_where, format_citation

ROOT = Path(__file__).resolve().parents[1]


@dataclass
class Hit:
    chunk_id: str
    doc_id: str
    article: str
    title: str
    url: str
    score: float
    text: str
    translation_status: str
    authority_status: str
    arabic_text: str
    citation: str

    def brief(self) -> dict:
        return {"chunk_id": self.chunk_id, "doc_id": self.doc_id, "article": self.article, "score": round(self.score, 4)}


class Retriever:
    def __init__(self, embedder, chroma_dir: str | Path | None = None, collection: str = "kb_main"):
        import yaml

        cfg = yaml.safe_load((ROOT / "config.yaml").read_text())
        path = Path(chroma_dir) if chroma_dir else ROOT / cfg["kb"]["chroma_dir"]
        self.col = chromadb.PersistentClient(path=str(path)).get_collection(collection)
        self.embedder = embedder

    def search(self, query: str, *, mode: str = "current", n: int = 5) -> list[Hit]:
        res = self.col.query(query_embeddings=[self.embedder.embed_query(query)], n_results=n,
                             where=combined_where(mode), include=["documents", "metadatas", "distances"])
        hits = []
        for doc, m, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
            hits.append(Hit(chunk_id=m["chunk_id"], doc_id=m["doc_id"], article=m["article"], title=m["title"], url=m["url"],
                            score=1.0 - float(dist), text=doc, translation_status=m["translation_status"],
                            authority_status=m["authority_status"], arabic_text=m.get("arabic_text", ""),
                            citation=format_citation(m["doc_id"], m["article"])))
        return hits

    def get(self, chunk_id: str) -> dict | None:
        r = self.col.get(ids=[chunk_id], include=["documents", "metadatas"])
        return {"text": r["documents"][0], "metadata": r["metadatas"][0]} if r["ids"] else None
