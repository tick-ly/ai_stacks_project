from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


AG_KEYWORDS = {
    "scheme",
    "schemes",
    "morphism",
    "morphisms",
    "flat",
    "flatness",
    "etale",
    "smooth",
    "proper",
    "cohomology",
    "sheaf",
    "stacks",
    "algebraic stack",
    "derived",
    "moduli",
    "zariski",
    "spec",
    "krull",
    "descent",
    "affine",
    "projective",
    "variety",
    "varieties",
    "tor",
    "ext",
    "functor",
    "gerbe",
    "stack project",
    "schematic",
    "cotangent complex",
}

NEGATIVE_HINTS = {
    "nba",
    "premier league",
    "movie",
    "recipe",
    "weather",
    "stock price",
    "celebrity",
    "travel itinerary",
    "javascript ui bug",
}

TOKEN_RE = re.compile(r"[a-zA-Z0-9\-\+]+")


def score_relevance(text: str) -> tuple[str, int, int]:
    q = text.lower()
    keyword_hits = 0
    negative_hits = 0

    for kw in AG_KEYWORDS:
        if kw in q:
            keyword_hits += 1
    for kw in NEGATIVE_HINTS:
        if kw in q:
            negative_hits += 1

    tokens = set(TOKEN_RE.findall(q))
    if {"spec", "sheaf"} <= tokens:
        keyword_hits += 1
    if {"scheme", "flat"} <= tokens:
        keyword_hits += 1
    if {"moduli", "stack"} <= tokens:
        keyword_hits += 1

    if keyword_hits >= 2 and negative_hits == 0:
        return "high", keyword_hits, negative_hits
    if keyword_hits >= 1 and negative_hits <= 1:
        return "medium", keyword_hits, negative_hits
    return "low", keyword_hits, negative_hits


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Classify AG relevance for an input query.")
    parser.add_argument("--query", type=str, required=True, help="User query text.")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional JSON output path.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    label, k_hits, n_hits = score_relevance(args.query)
    reason = (
        f"keyword_hits={k_hits}, negative_hits={n_hits}. "
        f"Relevance classified as {label}."
    )
    payload = {
        "label": label,
        "keyword_hits": k_hits,
        "negative_hits": n_hits,
        "reason": reason,
        "query": args.query,
    }

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
            newline="\n",
        )
    out = json.dumps(payload, ensure_ascii=False)
    sys.stdout.buffer.write((out + "\n").encode("utf-8", errors="replace"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
