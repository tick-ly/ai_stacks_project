from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from pathlib import Path

from runtime_utils import prefetch_config, setup_logging


LOGGER = logging.getLogger("run_pipeline")

def run(cmd: list[str], cwd: Path) -> None:
    LOGGER.info("$ %s", " ".join(cmd))
    subprocess.run(cmd, cwd=str(cwd), check=True)


def parse_args() -> argparse.Namespace:
    config_path, cfg = prefetch_config("run_pipeline")
    parser = argparse.ArgumentParser(
        description="Run production-oriented pipeline: fetch -> parse -> corpus -> vectors -> BM25."
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
        "--workspace-root",
        type=Path,
        default=Path(str(cfg.get("workspace_root", "."))),
        help="Workspace root that contains scripts/ and data/ directories.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=int(cfg.get("limit", 300)),
        help="Limit tags for quick smoke tests. Set 0 for full dataset.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=int(cfg.get("workers", 8)),
        help="Parallel workers for fetch_api.",
    )
    parser.add_argument(
        "--incremental",
        action="store_true",
        default=bool(cfg.get("incremental", False)),
        help="Enable incremental updates across corpus/vector/lexical index.",
    )
    parser.add_argument(
        "--max-cache-age-hours",
        type=float,
        default=float(cfg.get("max_cache_age_hours", 24.0 * 7)),
        help="Refetch cached API payload older than this many hours.",
    )
    parser.add_argument(
        "--provider",
        type=str,
        default=str(cfg.get("provider", "hash")),
        choices=["hash", "openai", "local"],
        help="Embedding provider.",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=str(cfg.get("model", "hash-embedding-v1")),
        help="Embedding model name.",
    )
    parser.add_argument(
        "--dim",
        type=int,
        default=int(cfg.get("dim", 1536)),
        help="Embedding dimension for hash/openai.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=int(cfg.get("batch_size", 64)),
        help="Embedding batch size.",
    )
    parser.add_argument(
        "--openai-api-key",
        type=str,
        default=str(cfg.get("openai_api_key", "")),
        help="OpenAI API key (optional; fallback env OPENAI_API_KEY).",
    )
    parser.add_argument(
        "--openai-base-url",
        type=str,
        default=str(cfg.get("openai_base_url", "https://api.openai.com/v1")),
        help="OpenAI base URL.",
    )
    parser.add_argument(
        "--openai-timeout-seconds",
        type=int,
        default=int(cfg.get("openai_timeout_seconds", 60)),
        help="OpenAI timeout seconds.",
    )
    parser.add_argument(
        "--local-device",
        type=str,
        default=str(cfg.get("local_device", "cpu")),
        help="Local embedding model device.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    setup_logging(args.log_level)
    root = args.workspace_root.resolve()
    changed_tags_file = "data/raw/api/changed_tags.json"
    config_flag: list[str] = ["--config", str(args.config)] if args.config else []
    log_flag: list[str] = ["--log-level", str(args.log_level)]

    fetch_cmd = [
        sys.executable,
        "scripts/fetch_api.py",
        *config_flag,
        *log_flag,
        "--workers",
        str(args.workers),
        "--max-cache-age-hours",
        str(args.max_cache_age_hours),
        "--changed-tags-file",
        changed_tags_file,
    ]
    if args.limit > 0:
        fetch_cmd += ["--limit", str(args.limit)]
    if args.incremental:
        # fetch_api already behaves incrementally via cache rules.
        pass
    run(fetch_cmd, root)

    run([sys.executable, "scripts/parse_tex.py", *config_flag, *log_flag], root)
    corpus_cmd = [sys.executable, "scripts/build_corpus.py", *config_flag, *log_flag]
    if args.incremental:
        corpus_cmd += ["--incremental", "--changed-tags-file", changed_tags_file]
    run(corpus_cmd, root)

    emb_cmd = [
        sys.executable,
        "scripts/build_embeddings.py",
        *config_flag,
        *log_flag,
        "--provider",
        args.provider,
        "--model",
        args.model,
        "--dim",
        str(args.dim),
        "--batch-size",
        str(args.batch_size),
        "--openai-base-url",
        args.openai_base_url,
        "--openai-timeout-seconds",
        str(args.openai_timeout_seconds),
        "--local-device",
        args.local_device,
    ]
    if args.openai_api_key:
        emb_cmd += ["--openai-api-key", args.openai_api_key]
    if args.incremental:
        emb_cmd += ["--incremental", "--changed-tags-file", changed_tags_file]
    run(emb_cmd, root)

    lex_cmd = [
        sys.executable,
        "scripts/build_lexical_index.py",
        *config_flag,
        *log_flag,
        "--prune-missing",
    ]
    if args.incremental:
        lex_cmd += ["--incremental", "--changed-tags-file", changed_tags_file]
    run(lex_cmd, root)

    LOGGER.info("Pipeline completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
