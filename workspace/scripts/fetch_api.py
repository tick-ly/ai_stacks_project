from __future__ import annotations

import argparse
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from common import (
    download_text,
    ensure_dir,
    parse_tags_file,
    read_json,
    sha256_text,
    write_json,
)
from runtime_utils import prefetch_config, setup_logging


DEFAULT_TAGS_URL = "https://raw.githubusercontent.com/stacks/stacks-project/master/tags/tags"
DEFAULT_BASE_URL = "https://stacks.math.columbia.edu"
LOGGER = logging.getLogger("fetch_api")


def fetch_endpoint(base_url: str, tag: str, suffix: str) -> dict[str, str | bool | int]:
    url = f"{base_url}/data/tag/{tag}/{suffix}"
    started = time.time()
    try:
        content = download_text(url)
        return {
            "ok": True,
            "url": url,
            "content": content,
            "error": "",
            "duration_ms": int((time.time() - started) * 1000),
        }
    except Exception as exc:  # pragma: no cover
        return {
            "ok": False,
            "url": url,
            "content": "",
            "error": str(exc),
            "duration_ms": int((time.time() - started) * 1000),
        }


def should_refresh(
    out_path: Path,
    full_label: str,
    now_utc: int,
    max_cache_age_hours: float,
    force_refresh: bool,
) -> tuple[bool, str]:
    if force_refresh or not out_path.exists():
        return True, "missing_or_forced"

    payload = read_json(out_path, default={})
    if not isinstance(payload, dict):
        return True, "invalid_cache"

    if payload.get("full_label") != full_label:
        return True, "full_label_changed"

    statement_ok = bool(payload.get("statement", {}).get("ok"))
    full_ok = bool(payload.get("full", {}).get("ok"))
    if not statement_ok or not full_ok:
        return True, "previous_failure"

    fetched_at_utc = int(payload.get("fetched_at_utc", 0))
    if fetched_at_utc <= 0:
        return True, "missing_timestamp"

    if max_cache_age_hours < 0:
        return False, "cache_valid"

    age_hours = (now_utc - fetched_at_utc) / 3600.0
    if age_hours >= max_cache_age_hours:
        return True, "cache_expired"
    return False, "cache_valid"


def build_payload(base_url: str, tag: str, full_label: str) -> dict[str, object]:
    payload: dict[str, object] = {
        "tag": tag,
        "full_label": full_label,
        "fetched_at_utc": int(time.time()),
    }
    payload["structure"] = fetch_endpoint(base_url, tag, "structure")
    payload["statement"] = fetch_endpoint(base_url, tag, "content/statement")
    payload["full"] = fetch_endpoint(base_url, tag, "content/full")

    statement_text = str(payload["statement"].get("content", ""))
    full_text = str(payload["full"].get("content", ""))
    payload["content_hash"] = sha256_text(statement_text + "\n" + full_text)
    return payload


def parse_args() -> argparse.Namespace:
    config_path, cfg = prefetch_config("fetch_api")
    parser = argparse.ArgumentParser(
        description=(
            "Fetch Stacks Project API payloads by tag with parallel download + incremental cache."
        )
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
        help="Path to local tags file. If missing, it will be downloaded.",
    )
    parser.add_argument(
        "--tags-url",
        type=str,
        default=str(cfg.get("tags_url", DEFAULT_TAGS_URL)),
        help="Remote URL for tags file fallback.",
    )
    parser.add_argument(
        "--base-url",
        type=str,
        default=str(cfg.get("base_url", DEFAULT_BASE_URL)),
        help="Stacks API base URL.",
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=Path(str(cfg.get("outdir", "data/raw/api/tags"))),
        help="Output directory where per-tag JSON payloads are stored.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=int(cfg.get("limit", 0)),
        help="Optional max tag count for smoke tests. 0 means all tags.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=int(cfg.get("workers", 8)),
        help="Number of parallel worker threads.",
    )
    parser.add_argument(
        "--refresh-tags",
        action="store_true",
        default=bool(cfg.get("refresh_tags", False)),
        help="Always redownload tags file from remote URL.",
    )
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        default=bool(cfg.get("force_refresh", False)),
        help="Ignore cache and refetch selected tags.",
    )
    parser.add_argument(
        "--max-cache-age-hours",
        type=float,
        default=float(cfg.get("max_cache_age_hours", 24.0 * 7)),
        help="Refetch cache older than this many hours. Use -1 to never expire cache.",
    )
    parser.add_argument(
        "--summary-file",
        type=Path,
        default=Path(str(cfg.get("summary_file", "data/raw/api/fetch_summary.json"))),
        help="Summary JSON output path.",
    )
    parser.add_argument(
        "--changed-tags-file",
        type=Path,
        default=Path(str(cfg.get("changed_tags_file", "data/raw/api/changed_tags.json"))),
        help="JSON array output path for fetched (changed) tag ids.",
    )
    parser.add_argument(
        "--strict-success",
        action="store_true",
        default=bool(cfg.get("strict_success", False)),
        help="Exit non-zero if any fetched tag failed.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    setup_logging(args.log_level)
    ensure_dir(args.tags_file.parent)
    ensure_dir(args.outdir)
    ensure_dir(args.summary_file.parent)
    ensure_dir(args.changed_tags_file.parent)

    if args.refresh_tags or not args.tags_file.exists():
        LOGGER.info("Downloading tags file: %s", args.tags_url)
        tags_text = download_text(args.tags_url)
        args.tags_file.write_text(tags_text, encoding="utf-8", newline="\n")

    tags_map = parse_tags_file(args.tags_file)
    items = list(tags_map.items())
    if args.limit > 0:
        items = items[: args.limit]

    now_utc = int(time.time())
    to_fetch: list[tuple[str, str, str]] = []
    skipped_tags: list[str] = []
    skip_reasons: dict[str, int] = {}

    for tag, full_label in items:
        out_path = args.outdir / f"{tag}.json"
        refresh, reason = should_refresh(
            out_path=out_path,
            full_label=full_label,
            now_utc=now_utc,
            max_cache_age_hours=args.max_cache_age_hours,
            force_refresh=args.force_refresh,
        )
        if refresh:
            to_fetch.append((tag, full_label, reason))
        else:
            skipped_tags.append(tag)
            skip_reasons[reason] = skip_reasons.get(reason, 0) + 1

    total = len(items)
    LOGGER.info(
        "Total=%d to_fetch=%d skipped=%d workers=%d",
        total,
        len(to_fetch),
        len(skipped_tags),
        args.workers,
    )

    fetched_tags: list[str] = []
    successful_tags: list[str] = []
    failed_tags: list[str] = []

    def worker(tag: str, full_label: str) -> tuple[str, bool]:
        payload = build_payload(args.base_url, tag, full_label)
        out_path = args.outdir / f"{tag}.json"
        write_json(out_path, payload)
        ok = bool(payload["statement"]["ok"] and payload["full"]["ok"])
        return tag, ok

    completed = 0
    with ThreadPoolExecutor(max_workers=max(args.workers, 1)) as executor:
        future_map = {
            executor.submit(worker, tag, full_label): (tag, reason)
            for tag, full_label, reason in to_fetch
        }
        for future in as_completed(future_map):
            tag, _reason = future_map[future]
            completed += 1
            try:
                fetched_tag, ok = future.result()
            except Exception as exc:  # pragma: no cover
                failed_tags.append(tag)
                LOGGER.error("ERROR tag=%s: %s", tag, exc)
            else:
                fetched_tags.append(fetched_tag)
                if ok:
                    successful_tags.append(fetched_tag)
                else:
                    failed_tags.append(fetched_tag)

            if completed % 250 == 0 or completed == len(to_fetch):
                LOGGER.info("fetched %d/%d", completed, len(to_fetch))

    summary = {
        "requested_total": total,
        "fetched_total": len(fetched_tags),
        "fetched_success_total": len(successful_tags),
        "skipped_total": len(skipped_tags),
        "failed_total": len(failed_tags),
        "skip_reasons": skip_reasons,
        "fetched_tags": sorted(fetched_tags),
        "changed_tags": sorted(successful_tags),
        "skipped_tags": sorted(skipped_tags),
        "failed_tags": sorted(set(failed_tags)),
        "max_cache_age_hours": args.max_cache_age_hours,
        "outdir": str(args.outdir),
        "tags_file": str(args.tags_file),
        "changed_tags_file": str(args.changed_tags_file),
        "generated_at_utc": int(time.time()),
    }
    write_json(args.summary_file, summary)
    write_json(args.changed_tags_file, sorted(successful_tags))

    LOGGER.info("Summary written: %s", args.summary_file)
    LOGGER.info("Changed tags written: %s", args.changed_tags_file)

    if args.strict_success and failed_tags:
        LOGGER.error("strict mode: failed tags=%d", len(failed_tags))
        return 2
    return 0 if not failed_tags else 1


if __name__ == "__main__":
    raise SystemExit(main())
