"""Single place for model calls: call_llm().

Provider is chosen in config.yaml (`llm.provider`). Default: OpenAI (the team has OpenAI access, not Anthropic).
Pattern adapted from BidOps `app/agents/llm_client.py` OpenAIClient: chat completions, bounded retries with exponential
backoff for transient errors, no retry on authentication errors, provider errors translated to our own exception types,
and NO temperature parameter for GPT-5-series models (BidOps verified they reject any non-default temperature).
Adds a disk cache keyed by input hash (reproducible re-runs, no repeated cost) and per-call token logging.
The API key is read from the project-local, git-ignored .env and never logged.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG = yaml.safe_load((ROOT / "config.yaml").read_text())
USAGE_LOG = ROOT / "audit" / "llm_usage.jsonl"
KEY_ENV = {"openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY"}


class LLMError(RuntimeError): ...
class LLMAuthenticationError(LLMError): ...
class LLMUnavailableError(LLMError): ...


@dataclass
class LLMResult:
    text: str
    model: str
    input_tokens: int
    output_tokens: int
    cached: bool


def load_env() -> None:
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def provider() -> str:
    return CONFIG["llm"].get("provider", "openai")


def _require_key() -> None:
    load_env()
    name = KEY_ENV[provider()]
    if not os.environ.get(name):
        raise LLMAuthenticationError(f"{name} not set (expected in project-local .env)")


def _openai_call(model: str, system: str, prompt: str, max_tokens: int) -> tuple[str, int, int]:
    import openai

    client = openai.OpenAI(max_retries=0, timeout=float(CONFIG["llm"].get("timeout_seconds", 120)))
    messages = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
    delay = 2.0
    for attempt in range(4):
        try:
            r = client.chat.completions.create(model=model, messages=messages, max_completion_tokens=max_tokens)
            u = r.usage
            return r.choices[0].message.content or "", getattr(u, "prompt_tokens", 0) or 0, getattr(u, "completion_tokens", 0) or 0
        except openai.AuthenticationError:
            raise LLMAuthenticationError("OpenAI rejected the API key (check OPENAI_API_KEY in .env)") from None
        except (openai.NotFoundError, openai.PermissionDeniedError) as e:
            raise LLMUnavailableError(f"model '{model}' not available to this key: {e}") from None
        except (openai.RateLimitError, openai.APITimeoutError, openai.APIConnectionError, openai.InternalServerError) as e:
            if attempt == 3:
                raise LLMError(f"{type(e).__name__} after retries: {e}") from None
            time.sleep(delay)
            delay *= 2
        except openai.APIStatusError as e:
            raise LLMError(f"OpenAI returned status {e.status_code}: {e}") from None
    raise LLMError("unreachable")


def _anthropic_call(model: str, system: str, prompt: str, max_tokens: int) -> tuple[str, int, int]:
    import anthropic

    client = anthropic.Anthropic(max_retries=3, timeout=120)
    try:
        msg = client.messages.create(model=model, max_tokens=max_tokens, temperature=0.0,
                                     system=system or anthropic.NOT_GIVEN,
                                     messages=[{"role": "user", "content": prompt}])
    except anthropic.AuthenticationError:
        raise LLMAuthenticationError("Anthropic rejected the API key") from None
    except (anthropic.NotFoundError, anthropic.PermissionDeniedError) as e:
        raise LLMUnavailableError(f"model '{model}' not available: {e}") from None
    text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    return text, msg.usage.input_tokens, msg.usage.output_tokens


def call_llm(prompt: str, *, system: str = "", model: str | None = None, max_tokens: int | None = None,
             purpose: str = "unspecified", use_cache: bool = True) -> LLMResult:
    model = model or CONFIG["models"]["agent"]
    max_tokens = max_tokens or CONFIG["llm"]["max_tokens"]
    key = hashlib.sha256(json.dumps([provider(), model, system, prompt, max_tokens]).encode()).hexdigest()
    cache = ROOT / CONFIG["llm"]["cache_dir"] / f"{key}.json"
    if use_cache and cache.exists():
        d = json.loads(cache.read_text())
        return LLMResult(d["text"], model, d["input_tokens"], d["output_tokens"], True)
    _require_key()
    fn = _openai_call if provider() == "openai" else _anthropic_call
    text, tin, tout = fn(model, system, prompt, max_tokens)
    res = LLMResult(text, model, tin, tout, False)
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps({"text": text, "input_tokens": tin, "output_tokens": tout}))
    USAGE_LOG.parent.mkdir(parents=True, exist_ok=True)
    with USAGE_LOG.open("a") as f:
        f.write(json.dumps({"ts": time.time(), "provider": provider(), "model": model, "purpose": purpose,
                            "input_tokens": tin, "output_tokens": tout}) + "\n")
    return res


def list_models() -> list[str]:
    """Model IDs visible to the configured key (used by the Step 00 check to verify configured names)."""
    _require_key()
    if provider() == "openai":
        import openai

        return sorted(m.id for m in openai.OpenAI().models.list())
    import anthropic

    return sorted(m.id for m in anthropic.Anthropic().models.list())
