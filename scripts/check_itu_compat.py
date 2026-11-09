"""Step 00 (d): run the ITU reference ingestion code on one sample document and check compatibility.

    python scripts/check_itu_compat.py

Checks:
  1. upstream ingest_file() parses, chunks, embeds and stores the sample in ChromaDB (upstream code paths)
  2. stored chunks carry every metadata key upstream writes
  3. the KB reopens from disk and returns the chunks
  4. our JSONL export round-trips into an upstream KnowledgeBase via add_documents (the ITU re-embedding path)
  5. retrieval returns the relevant chunk (only meaningful with the real embedding model)

If the local embedding model is not installed yet, a deterministic PLACEHOLDER embedder is used so that checks 1-4
(pipeline/format compatibility) can still run; check 5 is then reported as NOT RUN and Step 00 (b) stays open.
"""
from __future__ import annotations

import hashlib
import json
import logging
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from kb.embedder import EmbeddingUnavailable, get_embedder  # noqa: E402
from kb.itu_compat import ITU_DIR, ITU_KEYS, export_jsonl, itu_modules, load_jsonl_into_itu  # noqa: E402

SAMPLE = ITU_DIR / "server/knowledge/InputDocs/AI_Use_Cases/ITU-T_Y.3172_summary.txt"
WORK = ROOT / "kb" / "chroma_compat_check"


def placeholder(texts: list[str]) -> list[list[float]]:
    """NOT an embedding model. Hash-derived vectors, used only to exercise the storage/format path."""
    out = []
    for t in texts:
        h = hashlib.sha256(t.encode()).digest()
        out.append([b / 255.0 for b in h[:32]])
    return out


def main() -> int:
    logging.basicConfig(level=logging.WARNING)
    try:
        emb = get_embedder()
        embed_fn, label = emb.embed_passages, f"bge-small-en-v1.5 ({emb.backend} backend)"
        real = True
    except EmbeddingUnavailable as e:
        embed_fn, label, real = placeholder, f"PLACEHOLDER hash vectors ({e})", False

    print(f"Embedder: {label}")
    shutil.rmtree(WORK, ignore_errors=True)
    ingest, KnowledgeBase = itu_modules(embed_fn)
    results: list[tuple[str, bool, str]] = []

    # 1. upstream ingestion on one sample document
    kb = KnowledgeBase(persist_dir=str(WORK))
    n = ingest.ingest_file(SAMPLE, kb, extra_metadata={"document_category": "AI_Use_Cases"})
    results.append(("upstream ingest_file() on sample", n > 0, f"{n} chunks, sha256(sample)={hashlib.sha256(SAMPLE.read_bytes()).hexdigest()[:16]}..."))

    # 2. metadata keys
    got = kb.get_all()
    missing = sorted({k for m in got["metadatas"] for k in ITU_KEYS if k not in m})
    results.append(("upstream metadata keys present", not missing, f"missing={missing}" if missing else "all 7 keys"))

    # 3. reopen from disk
    kb2 = KnowledgeBase(persist_dir=str(WORK))
    results.append(("KB reopens from disk", kb2.count() == n, f"count={kb2.count()}"))

    # 4. JSONL export -> upstream add_documents (ITU re-embedding path)
    recs = [{"id": f"y3172sum-{i}", "text": t, "metadata": {**m, "chunk_id": f"y3172sum-{i}", "doc_id": "itu-y3172-summary",
             "title": "ITU-T Y.3172 summary (ITU reference repo)", "jurisdiction": "international", "language": "en"}}
            for i, (t, m) in enumerate(zip(got["documents"], got["metadatas"]))]
    jl = WORK / "export_sample.jsonl"
    export_jsonl(recs, jl)
    first = json.loads(jl.read_text().splitlines()[0])
    loaded = load_jsonl_into_itu(jl, kb2, embed_fn, collection_name="kb_reimport_test")
    back = kb2.get_by_id("y3172sum-0", collection_name="kb_reimport_test")
    ok4 = loaded == n and back["metadatas"][0]["doc_id"] == "itu-y3172-summary" and "embedding" not in first
    results.append(("JSONL export re-imports via upstream add_documents", ok4, f"{loaded} rows, vectors not stored in JSONL"))

    # 5. retrieval quality (real model only)
    if real:
        # Gate = plumbing (embed -> store -> search with the real model). Query chosen by reading the sample doc BEFORE
        # running it: the "ML Sandbox" sentence sits ~100 words after the start of chunk 1.
        # Informational finding (NOT gating, 2026-11-08): two Policy-node questions ranked chunk 1 (which starts at the
        # Distributor line) above chunk 0 (which holds the P line). Upstream's 256-word chunks put 7 nodes in one chunk,
        # which dilutes single-sentence lookups. Our own KB therefore chunks by article/section, and its retrieval
        # quality is measured by the separate ~15-question hit-rate test.
        q = emb.embed_query("Which supporting component is a validation environment that prevents ML applications from affecting the live network?")
        r = kb2.search(q, n_results=3)
        docs = r["documents"][0]
        for rank, (d, m) in enumerate(zip(docs, r["metadatas"][0]), 1):
            print(f"     rank {rank}: chunk_index={m['chunk_index']} has 'ML Sandbox:'={'ML Sandbox:' in d} | {d[:90]!r}")
        hit = "ML Sandbox:" in docs[0]
        results.append(("retrieval returns the relevant chunk", hit, f"top chunk_index={r['metadatas'][0][0]['chunk_index']}"))
        qp = emb.embed_query("Which node ensures ML decisions comply with safety constraints and regulatory requirements?")
        rp = kb2.search(qp, n_results=4)
        order = [m["chunk_index"] for m in rp["metadatas"][0]]
        pol = [m["chunk_index"] for d, m in zip(rp["documents"][0], rp["metadatas"][0]) if "(Policy)" in d]
        print(f"     (info, not gating) Policy-node question: chunk order {order}; chunks containing '(Policy)': {pol}")
    else:
        results.append(("retrieval returns the relevant chunk", None, "NOT RUN: local embedding model not installed"))

    print()
    for name, ok, note in results:
        mark = "PASS" if ok else ("NOT RUN" if ok is None else "FAIL")
        print(f"  [{mark:7}] {name}: {note}")
    shutil.rmtree(WORK, ignore_errors=True)
    failed = any(ok is False for _, ok, _ in results)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
