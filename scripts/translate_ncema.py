"""Produce the UNOFFICIAL English translation of the NCEMA founding law, article by article, for retrieval.

  python scripts/translate_ncema.py

Why: the official text is Arabic only and the local embedding model (bge-small-en-v1.5) is English-only. The translation
is the retrievable text; every record carries the Arabic article text and the Arabic URL, is labelled
"UNOFFICIAL TRANSLATION, NON-AUTHORITATIVE", and can support at most `partially_supported` evidence (kb/authority.py).

Output: kb/text/ae-dl-2-2011-ncema.en-unofficial.json  (git-ignored, like all KB text)
Needs OPENAI_API_KEY (run on the laptop). Calls are cached by input hash, so a re-run costs nothing.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agents.llm import CONFIG, call_llm  # noqa: E402
from kb.chunker import arabic_articles  # noqa: E402

OUT = ROOT / "kb" / "text" / "ae-dl-2-2011-ncema.en-unofficial.json"
SYSTEM = (
    "You are a legal translator working from Arabic into English. Translate the article faithfully and completely. "
    "Rules: translate only what is in the text; do not add, explain, summarise or soften; keep every numbered item with "
    "its original number; keep defined terms consistent (e.g. 'Authority' for الهيئة, 'Board of Directors' for مجلس الإدارة, "
    "'National Security Adviser' for مستشار الأمن الوطني, 'relevant bodies' for الجهات المعنية). The Arabic comes from a PDF "
    "text layer whose letter order is sometimes scrambled around the definite article (e.g. 'املادة' means 'المادة'); read "
    "through that. If a passage is unreadable, write [illegible] rather than guessing. Output the English text only."
)


def items(s: str) -> int:
    """Numbered items ("1." ... "12."), excluding the article heading itself ("املادة ( 10 )" / "Article 10")."""
    s = re.sub(r"^\s*(?:املادة\s*\(\s*\d+\s*\)|املا\(\s*دة\s*\d+\s*\)|Article\s*\(?\s*\d+\s*\)?)", "", s.strip())
    return len(re.findall(r"(?:^|\s)\d{1,2}\s*[.)]\s", s))


def main() -> int:
    ar = arabic_articles("translate")
    result, problems = {}, []
    for num in sorted(ar, key=int):
        r = call_llm(f"Translate this article (Article {num}) of Federal Decree-Law No. 2 of 2011:\n\n{ar[num]}",
                     system=SYSTEM, model=CONFIG["models"]["agent"], max_tokens=6000, purpose=f"translate_ncema_art{num}")
        en = r.text.strip()
        a_items, e_items = items(ar[num]), items(en)
        if not en or a_items != e_items or "[illegible]" in en:
            problems.append((num, a_items, e_items, "illegible" if "[illegible]" in en else ""))
        result[num] = en
        print(f"Art. {num:>2}: ar_items={a_items:2} en_items={e_items:2} {'cached' if r.cached else 'new'}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nwrote {OUT.relative_to(ROOT)} ({len(result)} articles)")
    if problems:
        print("REVIEW these articles (numbered-item count differs or illegible text):")
        for p in problems:
            print("  ", p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
