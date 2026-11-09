"""Local embedding model (BAAI/bge-small-en-v1.5), loaded only from disk.

Two backends, same model, same vectors (CLS pooling + L2 normalisation, as specified by the BGE model card):
  * onnx  - onnxruntime + tokenizers, no PyTorch needed (used in the build sandbox)
  * st    - sentence-transformers (convenient on a laptop)
Nothing is downloaded at runtime; see README for the one-time download command.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIR = ROOT / "models" / "bge-small-en-v1.5"
# BGE: prefix queries (not passages) with this instruction for retrieval.
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


class EmbeddingUnavailable(RuntimeError):
    pass


class Embedder:
    def __init__(self, model_dir: Path = DEFAULT_DIR, max_len: int = 512):
        self.model_dir = Path(model_dir)
        self.max_len = max_len
        if not self.model_dir.exists():
            raise EmbeddingUnavailable(f"model folder not found: {self.model_dir}")
        onnx_path = next((p for p in (self.model_dir / "onnx" / "model.onnx", self.model_dir / "model.onnx") if p.exists()), None)
        if onnx_path and (self.model_dir / "tokenizer.json").exists():
            import onnxruntime as ort
            from tokenizers import Tokenizer

            self.backend = "onnx"
            self.tok = Tokenizer.from_file(str(self.model_dir / "tokenizer.json"))
            self.tok.enable_truncation(max_length=max_len)
            self.tok.enable_padding(pad_id=0, pad_token="[PAD]")
            self.sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
            self.input_names = {i.name for i in self.sess.get_inputs()}
        else:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as e:
                raise EmbeddingUnavailable(
                    f"no onnx/model.onnx in {self.model_dir} and sentence-transformers is not installed"
                ) from e
            self.backend = "st"
            self.st = SentenceTransformer(str(self.model_dir), device="cpu")

    def _encode(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if self.backend == "st":
            return self.st.encode(texts, normalize_embeddings=True, batch_size=16).tolist()
        out = []
        for i in range(0, len(texts), 16):
            enc = self.tok.encode_batch(texts[i : i + 16])
            feed = {
                "input_ids": np.array([e.ids for e in enc], dtype=np.int64),
                "attention_mask": np.array([e.attention_mask for e in enc], dtype=np.int64),
            }
            if "token_type_ids" in self.input_names:
                feed["token_type_ids"] = np.array([e.type_ids for e in enc], dtype=np.int64)
            hidden = self.sess.run(None, feed)[0]  # (batch, seq, dim)
            cls = hidden[:, 0, :]
            cls = cls / np.linalg.norm(cls, axis=1, keepdims=True)
            out.extend(cls.tolist())
        return out

    def embed_passages(self, texts: list[str]) -> list[list[float]]:
        return self._encode(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._encode([QUERY_PREFIX + text])[0]


@lru_cache
def get_embedder() -> Embedder:
    return Embedder()
