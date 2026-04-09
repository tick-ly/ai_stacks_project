from __future__ import annotations

import argparse
import logging
from pathlib import Path

from common import download_text, parse_tags_file, write_json
from common import write_jsonl
from runtime_utils import prefetch_config, setup_logging


DEFAULT_MAKEFILE_URL = "https://raw.githubusercontent.com/stacks/stacks-project/master/Makefile"
LOGGER = logging.getLogger("parse_tex")


def parse_makefile_chapter_keys_from_text(text: str) -> list[str]:
    lines = text.splitlines()
    collecting = False
    parts: list[str] = []

    for raw_line in lines:
        line = raw_line.rstrip()
        if not collecting:
            if line.startswith("LIJST ="):
                collecting = True
                piece = line.split("=", 1)[1]
            else:
                continue
        else:
            piece = line

        piece = piece.split("#", 1)[0].strip()
        if not piece:
            if collecting:
                break
            continue

        has_continuation = piece.endswith("\\")
        if has_continuation:
            piece = piece[:-1].strip()
        parts.append(piece)

        if not has_continuation:
            break

    joined = " ".join(parts).strip()
    if not joined:
        return []
    return [x for x in joined.split() if x]


def parse_makefile_chapter_keys(makefile_path: Path) -> list[str]:
    if not makefile_path.exists():
        return []
    text = makefile_path.read_text(encoding="utf-8", errors="replace")
    return parse_makefile_chapter_keys_from_text(text)


def pick_chapter(full_label: str, chapter_keys: list[str]) -> str:
    matches = [k for k in chapter_keys if full_label.startswith(f"{k}-")]
    if matches:
        return sorted(matches, key=len, reverse=True)[0]
    if "-" in full_label:
        return full_label.split("-", 1)[0]
    return "unknown"


def infer_env_hint(full_label: str, chapter_key: str) -> str:
    prefix = f"{chapter_key}-"
    suffix = full_label[len(prefix) :] if full_label.startswith(prefix) else full_label
    if "-" in suffix:
        return suffix.split("-", 1)[0]
    return suffix


def parse_args() -> argparse.Namespace:
    config_path, cfg = prefetch_config("parse_tex")
    parser = argparse.ArgumentParser(
        description="Build tag metadata from tags file and chapter ordering from Makefile."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=config_path,
        help="Path to JSON/YAML config.",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default=str(cfg.get("log_level", "INFO")),
        help="Log level: DEBUG|INFO|WARNING|ERROR",
    )
    parser.add_argument(
        "--tags-file",
        type=Path,
        default=Path(str(cfg.get("tags_file", "data/raw/tags.csv"))),
        help="Path to tags file (tag,full_label).",
    )
    parser.add_argument(
        "--makefile",
        type=Path,
        default=Path(str(cfg.get("makefile", "../stacks-project/Makefile"))),
        help="Path to Stacks Project Makefile for chapter order.",
    )
    parser.add_argument(
        "--makefile-url",
        type=str,
        default=str(cfg.get("makefile_url", DEFAULT_MAKEFILE_URL)),
        help="Fallback URL for Makefile if local path does not exist.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(str(cfg.get("output", "data/processed/tag_metadata.jsonl"))),
        help="Output metadata JSONL path.",
    )
    parser.add_argument(
        "--chapters-output",
        type=Path,
        default=Path(str(cfg.get("chapters_output", "data/processed/chapters.json"))),
        help="Output chapter list JSON path.",
    )
    parser.add_argument(
        "--cache-makefile",
        type=Path,
        default=Path(str(cfg.get("cache_makefile", "data/raw/stacks_makefile.cache"))),
        help="Cache path for downloaded Makefile fallback.",
    )
    parser.add_argument(
        "--refresh-makefile-cache",
        action="store_true",
        default=bool(cfg.get("refresh_makefile_cache", False)),
        help="Force refresh Makefile fallback cache from remote URL.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    setup_logging(args.log_level)
    tags_map = parse_tags_file(args.tags_file)
    if not tags_map:
        raise RuntimeError(
            f"No tags parsed from {args.tags_file}. "
            "Run scripts/fetch_api.py first or provide a valid tags file."
        )

    chapter_keys = parse_makefile_chapter_keys(args.makefile)
    source_makefile = str(args.makefile)
    makefile_fallback_used = False

    if not chapter_keys:
        if args.cache_makefile.exists() and not args.refresh_makefile_cache:
            text = args.cache_makefile.read_text(encoding="utf-8", errors="replace")
            chapter_keys = parse_makefile_chapter_keys_from_text(text)
            source_makefile = str(args.cache_makefile)
            makefile_fallback_used = True
        else:
            try:
                LOGGER.warning("Local Makefile unavailable. Downloading: %s", args.makefile_url)
                text = download_text(args.makefile_url)
                args.cache_makefile.parent.mkdir(parents=True, exist_ok=True)
                args.cache_makefile.write_text(text, encoding="utf-8", newline="\n")
                chapter_keys = parse_makefile_chapter_keys_from_text(text)
                source_makefile = f"{args.makefile_url} (cached at {args.cache_makefile})"
                makefile_fallback_used = True
            except Exception as exc:
                LOGGER.error("Failed to download fallback Makefile: %s", exc)

    if not chapter_keys:
        LOGGER.warning("Chapter list unresolved. Using prefix fallback only.")

    rows = []
    for tag, full_label in sorted(tags_map.items()):
        chapter_key = pick_chapter(full_label, chapter_keys)
        row = {
            "id": tag,
            "tag": tag,
            "full_label": full_label,
            "chapter_key": chapter_key,
            "source_tex": f"{chapter_key}.tex",
            "env_hint": infer_env_hint(full_label, chapter_key),
        }
        rows.append(row)

    count = write_jsonl(args.output, rows)

    chapter_payload = {
        "chapter_keys": chapter_keys,
        "count": len(chapter_keys),
        "source_makefile": source_makefile,
        "fallback_used": makefile_fallback_used,
    }
    write_json(args.chapters_output, chapter_payload)

    LOGGER.info("Wrote %d rows -> %s", count, args.output)
    LOGGER.info("Wrote chapters -> %s", args.chapters_output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
