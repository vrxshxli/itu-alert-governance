# Vendored: ITU AI Readiness reference code

| Field | Value |
|---|---|
| Upstream repository | https://github.com/CrashingGuru/ITUAIReadiness |
| Upstream licence | MIT, Copyright (c) 2026 Vishnu Ram OV (see `LICENSE` in this folder, copied unchanged) |
| Upstream commit | `84010da9e9c443afcceeccb86d1700a662223395` (2026-10-20, "Change default example country from Ethiopia to UAE") |
| Retrieved | 2026-11-08, via raw.githubusercontent.com |
| Modifications | **None.** Files are byte-identical to upstream (verified with `git hash-object` against the upstream blob SHAs below). |

| Local path | Upstream path | Upstream blob SHA (verified identical) |
|---|---|---|
| `LICENSE` | `LICENSE` | `adf59655cda61ebc70238d31f522dfdcc83f7804` |
| `server/config.py` | `simulation/server/config.py` | `98e828cef4d8de523af97646d1d3b7a956b772ef` |
| `server/knowledge/kb.py` | `simulation/server/knowledge/kb.py` | `289f6023c0fb7effd8c9be7af028dc82dc96138b` |
| `server/knowledge/ingest.py` | `simulation/server/knowledge/ingest.py` | `58b2cb50ea31e74303532fe68ee01edb00d3d197` |
| `server/knowledge/InputDocs/AI_Use_Cases/ITU-T_Y.3172_summary.txt` | same path under `simulation/` | `6d4aee847ab27f9daa9d05f3d3481c7376d2e927` |

`server/__init__.py` and `server/knowledge/__init__.py` are empty upstream (blob `e69de29...`) and are recreated empty here.

## How we use it

We do not edit these files. Our code (`kb/itu_compat_check.py`) imports them and replaces only the embedding
function at runtime (`ingest.embed_texts`), because upstream embeds through a local Ollama server
(`nomic-embed-text`) that is not available in our build environment. Chunking, metadata and ChromaDB storage are
upstream's own code paths.

Re-verify at any time:

```
cd third_party/itu_ai_readiness && git hash-object server/knowledge/ingest.py   # expect 58b2cb50...
```

Note: `ITU-T_Y.3172_summary.txt` is upstream's own summary, not the standard. Statements about Y.3172 in our report
must be checked against the official Recommendation text (ITU-T Y.3172, 06/2019).
