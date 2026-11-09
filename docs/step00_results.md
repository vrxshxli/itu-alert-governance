# Step 00 results (2026-11-08T18:12:07)

**Step 00 CLEARED**

| Check | Result | Detail |
|---|---|---|
| (a) key accepted, models listed | PASS | 96 models visible to this key |
| (a) gpt-5.5-2026-04-23 via call_llm() | PASS | reply='ready', tokens in/out=13/14 |
| (a) gpt-5.4-mini-2026-03-17 via call_llm() | PASS | reply='ready', tokens in/out=13/4 |
| (b) onnx/model.onnx exists | PASS | 133.1 MB |
| (b) real embeddings | PASS | backend=onnx, dim=384, norms~1: True |
| (c) Chroma write + reopen | PASS | count=5 |
| (c) retrieval test | PASS | top-1 hit rate 5/5 |
| (d) ITU ingestion with real embedder | PASS | [PASS   ] retrieval returns the relevant chunk: top chunk_index=1 |
