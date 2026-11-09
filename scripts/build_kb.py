"""Build the KB: chunk -> embed (local ONNX) -> ChromaDB -> JSONL export -> coverage table.   python scripts/build_kb.py

Needs kb/raw/* (scripts/fetch_sources.sh), the local embedding model, and (for the NCEMA English retrieval text)
kb/text/ae-dl-2-2011-ncema.en-unofficial.json from scripts/translate_ncema.py. Without the translation the NCEMA
Arabic law is still registered, but it is NOT retrievable; the build says so loudly instead of hiding the gap.
"""
from __future__ import annotations

import json
import shutil
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import chromadb  # noqa: E402
import yaml  # noqa: E402

from kb.authority import registry  # noqa: E402
from kb.chunker import build_all  # noqa: E402
from kb.embedder import get_embedder  # noqa: E402
from kb.itu_compat import export_jsonl, to_itu_metadata  # noqa: E402

CFG = yaml.safe_load((ROOT / "config.yaml").read_text())
TRANS = ROOT / "kb/text/ae-dl-2-2011-ncema.en-unofficial.json"


def main() -> int:
    version = CFG["kb"]["version"]
    translations = json.loads(TRANS.read_text(encoding="utf-8")) if TRANS.exists() else None
    if translations is None:
        print("WARNING: NCEMA unofficial translation not found; NCEMA law will NOT be retrievable. "
              "Run scripts/translate_ncema.py first.")
    recs = build_all(version, translations)
    per_doc = Counter(r["metadata"]["doc_id"] for r in recs)
    idx = defaultdict(int)
    for r in recs:
        d = r["metadata"]["doc_id"]
        idx[d] += 1
        r["metadata"].update({"source_file": d, "source_type": "legal_or_standard_text",
                              "country": r["metadata"]["jurisdiction"], "chunk_index": idx[d] - 1,
                              "total_chunks": per_doc[d], "document_category": "alert_governance_kb",
                              "ingested_at": datetime.now(timezone.utc).isoformat()})
        r["metadata"] = to_itu_metadata(r["metadata"])
    emb = get_embedder()
    texts = [r["text"] for r in recs]
    vecs = []
    for i in range(0, len(texts), 64):
        vecs += emb.embed_passages(texts[i:i + 64])
    path = ROOT / CFG["kb"]["chroma_dir"]
    shutil.rmtree(path, ignore_errors=True)
    col = chromadb.PersistentClient(path=str(path)).get_or_create_collection(CFG["kb"]["collection"], metadata={"hnsw:space": "cosine"})
    for i in range(0, len(recs), 200):
        s = recs[i:i + 200]
        col.add(ids=[r["id"] for r in s], documents=[r["text"] for r in s], embeddings=vecs[i:i + 200],
                metadatas=[r["metadata"] for r in s])
    n_export = export_jsonl(recs, ROOT / "kb/export/kb_chunks.jsonl")
    print(f"chunks={len(recs)} stored={col.count()} exported={n_export} (kb/export is git-ignored; pending organiser confirmation)")

    reg = registry()
    lines = [f"# KB coverage ({version}, built {datetime.now().isoformat(timespec='seconds')})", "",
             "Counts come from the build, not from hand entry. No source text is reproduced here.", "",
             "| doc_id | institution | authority_status | translation_status | chunks | articles verified by hand |", "|---|---|---|---|---|---|"]
    for d, n in sorted(per_doc.items()):
        s = reg[d]
        ver = reg.get(s.get("translation_of", d), s).get("articles_verified") or []
        lines.append(f"| {d} | {s.get('institution','')} | {s['authority_status']} | {s.get('translation_status','original')} | {n} | {len(ver)} |")
    missing = [d for d in reg if d not in per_doc and not reg[d].get("translation_of")]
    lines += ["", "Registered but with NO chunks in the index (reason in `kb/sources.yaml`): " + (", ".join(missing) or "none")]
    (ROOT / "docs/kb_coverage.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("wrote docs/kb_coverage.md; registered without chunks:", missing or "none")
    return 0


if __name__ == "__main__":
    sys.exit(main())
