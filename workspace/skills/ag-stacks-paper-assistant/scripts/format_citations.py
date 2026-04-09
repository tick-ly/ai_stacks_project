from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8", errors="replace"))


def format_stacks_item(item: dict[str, Any]) -> str:
    cid = item.get("citation_id", "")
    tag = item.get("tag", "")
    reference = item.get("reference", "")
    title = item.get("title", "")
    url = item.get("url", "")
    parts = [f"[{cid}]"]
    if tag:
        parts.append(f"Tag {tag}")
    if reference:
        parts.append(str(reference))
    if title:
        parts.append(str(title))
    if url:
        parts.append(str(url))
    return ", ".join(parts)


def format_paper_item(item: dict[str, Any]) -> str:
    cid = item.get("citation_id", "")
    title = item.get("title", "")
    authors = item.get("authors", "")
    year = item.get("year", "")
    source = item.get("source", "")
    url = item.get("url", "")
    parts = [f"[{cid}]"]
    if title:
        parts.append(str(title))
    if authors:
        parts.append(str(authors))
    if year:
        parts.append(str(year))
    if source:
        parts.append(str(source))
    if url:
        parts.append(str(url))
    return ", ".join(parts)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Format citation lists from retrieval outputs.")
    parser.add_argument("--stacks-json", type=Path, required=True, help="Path to retrieve_stacks output.")
    parser.add_argument("--papers-json", type=Path, required=True, help="Path to retrieve_papers output.")
    parser.add_argument("--output", type=Path, default=None, help="Optional JSON output path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    stacks = load_json(args.stacks_json).get("results", [])
    papers = load_json(args.papers_json).get("results", [])

    stacks_refs = [format_stacks_item(x) for x in stacks]
    paper_refs = [format_paper_item(x) for x in papers]

    payload = {
        "stacks_references": stacks_refs,
        "paper_references": paper_refs,
        "all_references": stacks_refs + paper_refs,
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
