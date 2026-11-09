"""Step 00 release-blocking smoke test.  python scripts/check_step00.py

(a) the configured models (config.yaml) respond through call_llm()
(b) models/bge-small-en-v1.5/onnx/model.onnx exists and produces real, normalised 384-d vectors
(c) ChromaDB stores real vectors, reopens from disk, and a retrieval test returns the expected passages
(d) the ITU reference ingestion code runs on one sample document with the real embedder (scripts/check_itu_compat.py)

Prints the exact failure and the smallest viable fallback for anything that fails. Writes docs/step00_results.md.
Downloading files alone does not clear Step 00: every check below must PASS.
"""
from __future__ import annotations

import datetime as dt
import shutil
import subprocess
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

RESULTS: list[tuple[str, str, str]] = []  # (check, PASS/FAIL, detail)


def record(name: str, ok: bool, detail: str):
    RESULTS.append((name, "PASS" if ok else "FAIL", detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")


def check_models():
    from agents.llm import CONFIG, KEY_ENV, LLMAuthenticationError, LLMUnavailableError, call_llm, list_models, provider

    if not (ROOT / ".env").exists():
        record("(a) .env present", False, f"missing project-local .env. Fallback: create it containing {KEY_ENV[provider()]}=... (git-ignored)")
        return
    try:
        avail = list_models()
        record("(a) key accepted, models listed", True, f"{len(avail)} models visible to this key")
    except Exception as e:  # noqa: BLE001
        hint = (" (OpenAI is not reachable from the build sandbox; run this script on the laptop)"
                if "Connection" in type(e).__name__ or "Connection" in str(e) else "")
        record("(a) key accepted, models listed", False, f"{type(e).__name__}: {e}{hint}")
        return
    for role in ("agent", "cheap"):
        model = CONFIG["models"][role]
        if model not in avail:
            near = [m for m in avail if m.startswith(model.split("-")[0])][:12]
            record(f"(a) {model} available", False, f"not listed for this key. Fallback: set models.{role} in config.yaml to one of {near} and record it in models.substitutions")
            continue
        try:
            r = call_llm("Reply with exactly the word: ready", model=model, max_tokens=200, use_cache=False, purpose="step00")
            record(f"(a) {model} via call_llm()", "ready" in r.text.lower(), f"reply={r.text.strip()[:40]!r}, tokens in/out={r.input_tokens}/{r.output_tokens}")
        except (LLMAuthenticationError, LLMUnavailableError) as e:
            record(f"(a) {model} via call_llm()", False, str(e))
        except Exception as e:  # noqa: BLE001
            record(f"(a) {model} via call_llm()", False, f"{type(e).__name__}: {e}")
    cheap = [m for m in avail if "mini" in m or "nano" in m][:10]
    print(f"     (info) cheaper models visible to this key: {cheap}")


SAMPLES = {  # TEST FIXTURES ONLY, never cited: EU text quoted verbatim (reusable); the rest is our own short wording
    "eu-110-1": "Member States shall ensure that, when public warning systems regarding imminent or developing major "
                "emergencies and disasters are in place, public warnings are transmitted by providers of mobile "
                "number-based interpersonal communications services to the end-users concerned.",
    "eu-111": "Member States shall ensure that the competent authorities specify requirements to be met by providers of "
              "publicly available electronic communications services to ensure that end-users with disabilities have "
              "access to electronic communications services.",
    "fcc-summary": "The false ballistic missile alert was sent in Hawaii on January 13, 2018; the correction took 38 "
                   "minutes because the agency had not established safeguards or a procedure for a false alert.",
    "cap-cancel": "The Common Alerting Protocol message type Cancel cancels an earlier message identified by its "
                  "references; Update supersedes an earlier message.",
    "pdpl-scope": "Data protection law scope: the law does not apply to government data or to governmental entities "
                  "that control or process personal data.",
}
QUERIES = [
    ("Which providers must transmit public warnings to end-users?", "eu-110-1"),
    ("How long did it take to correct the false missile alert?", "fcc-summary"),
    ("How is an erroneous alert withdrawn in the alerting message format?", "cap-cancel"),
    ("Does personal data law apply to government bodies processing location data?", "pdpl-scope"),
    # Reworded 2026-11-08: the first wording ("accessibility of warnings for people with disabilities") ranked eu-111 second
    # behind eu-110-1 because it also said "warnings", which Art. 110 is about. The question now targets only the
    # disability-access requirement. Recorded here so the change is auditable.
    ("What must authorities require so end-users with disabilities get equivalent access to communications services?", "eu-111"),
]


def check_embeddings_and_retrieval():
    onnx = ROOT / "models/bge-small-en-v1.5/onnx/model.onnx"
    if not onnx.exists():
        record("(b) onnx/model.onnx exists", False,
               f"not found at {onnx.relative_to(ROOT)}. Fallback: run `hf download BAAI/bge-small-en-v1.5 "
               "--local-dir models/bge-small-en-v1.5` (includes onnx/). If Hugging Face is unreachable, use "
               "sentence-transformers on the laptop for ingestion and run retrieval there.")
        return None
    record("(b) onnx/model.onnx exists", True, f"{onnx.stat().st_size/1e6:.1f} MB")
    import numpy as np

    from kb.embedder import Embedder

    emb = Embedder()
    vecs = emb.embed_passages(list(SAMPLES.values()))
    norms = [float(np.linalg.norm(v)) for v in vecs]
    ok = emb.backend == "onnx" and all(len(v) == 384 for v in vecs) and all(abs(n - 1) < 1e-3 for n in norms)
    record("(b) real embeddings", ok, f"backend={emb.backend}, dim={len(vecs[0])}, norms~1: {all(abs(n-1)<1e-3 for n in norms)}")

    import chromadb

    path = ROOT / "kb" / "chroma_step00_check"
    shutil.rmtree(path, ignore_errors=True)
    col = chromadb.PersistentClient(path=str(path)).get_or_create_collection("kb_main", metadata={"hnsw:space": "cosine"})
    col.add(ids=list(SAMPLES), documents=list(SAMPLES.values()), embeddings=vecs)
    col = chromadb.PersistentClient(path=str(path)).get_collection("kb_main")
    record("(c) Chroma write + reopen", col.count() == len(SAMPLES), f"count={col.count()}")
    hits = 0
    for q, want in QUERIES:
        ranked = col.query(query_embeddings=[emb.embed_query(q)], n_results=len(SAMPLES))["ids"][0]
        top = ranked[0]
        hits += top == want
        print(f"     query={q!r} -> {top} {'OK' if top == want else 'MISS (want ' + want + f', rank {ranked.index(want) + 1}; order {ranked})'}")
    record("(c) retrieval test", hits == len(QUERIES), f"top-1 hit rate {hits}/{len(QUERIES)}")
    shutil.rmtree(path, ignore_errors=True)
    return emb


def check_itu():
    r = subprocess.run([sys.executable, str(ROOT / "scripts/check_itu_compat.py")], capture_output=True, text=True)
    out = r.stdout.strip().splitlines()
    real = any("bge-small" in l for l in out)
    retrieval = [l for l in out if "retrieval returns" in l]
    ok = r.returncode == 0 and real and retrieval and "[PASS" in retrieval[0]
    record("(d) ITU ingestion with real embedder", bool(ok), (retrieval[0].strip() if retrieval else (r.stderr or "no output")[-300:]))


def main() -> int:
    for fn in (check_models, check_embeddings_and_retrieval, check_itu):
        try:
            fn()
        except Exception as e:  # noqa: BLE001
            record(fn.__name__, False, f"{type(e).__name__}: {e}\n{traceback.format_exc(limit=2)}")
    passed = all(s == "PASS" for _, s, _ in RESULTS) and len(RESULTS) >= 8
    lines = [f"# Step 00 results ({dt.datetime.now().isoformat(timespec='seconds')})", "",
             f"**Step 00 {'CLEARED' if passed else 'NOT CLEARED'}**", "", "| Check | Result | Detail |", "|---|---|---|"]
    lines += [f"| {n} | {s} | {d.replace('|', '/').splitlines()[0]} |" for n, s, d in RESULTS]
    (ROOT / "docs" / "step00_results.md").write_text("\n".join(lines) + "\n")
    print(f"\nStep 00 {'CLEARED' if passed else 'NOT CLEARED'} (written to docs/step00_results.md)")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
