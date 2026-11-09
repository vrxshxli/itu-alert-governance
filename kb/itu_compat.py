"""Compatibility layer between our KB and the ITU AI Readiness reference code (vendored, unmodified, in
third_party/itu_ai_readiness).

* `itu_modules()` imports upstream `ingest` and `kb` and swaps only the embedding function.
* `to_itu_metadata()` builds chunk metadata that contains every key upstream writes, plus our legal-citation keys.
* `export_jsonl()` / `load_jsonl_into_itu()` are the hand-off format: one JSON object per chunk
  {"id", "text", "metadata"} with NO vectors, so the ITU environment can re-embed with its own model
  (upstream default: Ollama nomic-embed-text) and store via upstream `KnowledgeBase.add_documents`.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

ROOT = Path(__file__).resolve().parents[1]
ITU_DIR = ROOT / "third_party" / "itu_ai_readiness"

# Keys upstream build_metadata() writes for every chunk (plus document_category from ingest_directory).
ITU_KEYS = ["source_file", "source_type", "country", "chunk_index", "total_chunks", "ingested_at", "document_category"]
# Our additional keys, needed for exact legal citations.
OUR_KEYS = ["chunk_id", "doc_id", "title", "jurisdiction", "institution", "article", "date", "language",
            "translation_status", "url", "kb_version"]


def itu_modules(embed_fn: Callable[[list[str]], list[list[float]]]):
    """Import upstream modules with `embed_fn` replacing the Ollama embedder. Returns (ingest, KnowledgeBase)."""
    if str(ITU_DIR) not in sys.path:
        sys.path.insert(0, str(ITU_DIR))
    from server.knowledge import ingest  # noqa: E402  (upstream, unmodified)
    from server.knowledge.kb import KnowledgeBase  # noqa: E402

    ingest.embed_texts = lambda texts, **_: embed_fn(texts)
    return ingest, KnowledgeBase


def to_itu_metadata(meta: dict) -> dict[str, str]:
    """Upstream stores every metadata value as str and ChromaDB rejects None; normalise accordingly."""
    out = {k: "" for k in ITU_KEYS + OUR_KEYS}
    out.update({k: "" if v is None else str(v) for k, v in meta.items()})
    out.setdefault("ingested_at", datetime.now(timezone.utc).isoformat())
    return out


def export_jsonl(records: Iterable[dict], path: Path) -> int:
    """records: {"id", "text", "metadata"}; writes one per line, no embeddings."""
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps({"id": r["id"], "text": r["text"], "metadata": to_itu_metadata(r["metadata"])},
                               ensure_ascii=False) + "\n")
            n += 1
    return n


def load_jsonl_into_itu(path: Path, kb, embed_fn: Callable[[list[str]], list[list[float]]],
                        collection_name: str | None = None) -> int:
    """What the ITU environment would run: read our JSONL, embed with ITS model, store via upstream KB."""
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not rows:
        return 0
    kb.add_documents(
        texts=[r["text"] for r in rows],
        embeddings=embed_fn([r["text"] for r in rows]),
        metadatas=[r["metadata"] for r in rows],
        collection_name=collection_name,
        ids=[r["id"] for r in rows],
    )
    return len(rows)
