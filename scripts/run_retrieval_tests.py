"""Run the retrieval test set against the built KB and write docs/retrieval_results.md.  python scripts/run_retrieval_tests.py

Reports hit@1, hit@3, hit@5 over the questions in kb/retrieval_questions.yaml. No pass threshold is asserted: the numbers are
the finding. Also checks the authority rule that repealed law never appears in 'current' results.
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from kb.embedder import get_embedder  # noqa: E402
from kb.retrieval import Retriever  # noqa: E402


def matches(chunk_id: str, expect: list[str]) -> bool:
    return any(chunk_id.startswith(e) if e.endswith(":") else (chunk_id == e or chunk_id.startswith(e + ":")) for e in expect)


def main() -> int:
    qs = yaml.safe_load((ROOT / "kb/retrieval_questions.yaml").read_text())["questions"]
    r = Retriever(get_embedder())
    have = {i for i in r.col.get(include=[])["ids"]}
    rows, h1, h3, h5, n, skipped, repealed_leak = [], 0, 0, 0, 0, [], 0
    for q in qs:
        if q.get("needs_translation") and not any(i.startswith("ae-dl-2-2011-ncema-en-unofficial") for i in have):
            skipped.append(q["id"])
            continue
        hits = r.search(q["q"], mode=q["mode"], n=5)
        repealed_leak += sum(h.doc_id == "ae-dl-35-2024-cda" for h in hits) if q["mode"] == "current" else 0
        ranks = [i for i, h in enumerate(hits, 1) if matches(h.chunk_id, q["expect"])]
        rank = ranks[0] if ranks else None
        n += 1
        h1 += rank == 1
        h3 += bool(rank and rank <= 3)
        h5 += bool(rank)
        rows.append((q["id"], q["q"], q["expect"], rank, [h.chunk_id for h in hits[:3]]))
        print(f"{q['id']} rank={rank} top3={[h.chunk_id for h in hits[:3]]}")
    lines = [f"# Retrieval results ({datetime.now().isoformat(timespec='seconds')})", "",
             f"Questions run: {n}; skipped (needs NCEMA translation): {skipped or 'none'}",
             f"**hit@1 = {h1}/{n}, hit@3 = {h3}/{n}, hit@5 = {h5}/{n}**; repealed-law results in 'current' mode: {repealed_leak}", "",
             "| Q | question | expected | rank | top 3 |", "|---|---|---|---|---|"]
    for qid, q, ex, rank, top in rows:
        lines.append(f"| {qid} | {q} | {', '.join(ex)} | {rank or 'MISS'} | {', '.join(top)} |")
    (ROOT / "docs/retrieval_results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nhit@1={h1}/{n} hit@3={h3}/{n} hit@5={h5}/{n} repealed_leak={repealed_leak}  -> docs/retrieval_results.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
