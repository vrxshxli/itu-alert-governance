"""Static, read-only export of the viewer for one run: a single HTML file that opens with a double-click (no server, no key).
   python scripts/export_viewer.py [run_id]      ->  report/viewer_export.html

The export holds the agents' records, the gap report and the scorecard, with source CITATIONS only. It does not embed KB passage
text (the publishers reserve rights), so chips open a citation card, not an excerpt.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from viewer import data  # noqa: E402


def referenced_chunks(run: dict, report: dict) -> set[str]:
    ids = set()
    for rec in run["grounded"]:
        ids |= {c["chunk_id"] for c in rec["retrieved_chunks"]}
        for c in rec["claims"]:
            ids |= set(c["cited_chunk_ids"])
    for g in (report.get("gap_analysis") or {}).get("gaps", []):
        ids |= {e["chunk_id"] for e in g["evidence"]}
        if g.get("global_comparison"):
            ids.add(g["global_comparison"]["chunk_id"])
    return ids


def build(run_id: str | None = None, collection=None) -> str:
    runs = data.list_runs()
    run_id = run_id or runs[0]
    run = data.load_run(run_id)
    report = data.report_bundle()
    chunks = {}
    for cid in sorted(referenced_chunks(run, report)):
        info = data.chunk_info(cid, collection, with_text=False)
        if info:
            chunks[cid] = info
    payload = {"runs": [run_id], "run": run, "report": report, "chunks": chunks}
    blob = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    html = (ROOT / "viewer" / "index.html").read_text(encoding="utf-8")
    return html.replace("<script>\nconst EXPORT", f"<script>window.__EXPORT__ = {blob};</script>\n<script>\nconst EXPORT", 1)


def main(argv: list[str]) -> int:
    out = ROOT / "report" / "viewer_export.html"
    out.write_text(build(argv[0] if argv else None), encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)} ({out.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
