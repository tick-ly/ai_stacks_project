from __future__ import annotations

import argparse
import logging
from pathlib import Path

from retrieval_engine import (
    hybrid_search,
    load_corpus,
    load_vector_index,
    make_query_embedder,
    resolve_query_embedding_params,
)
from runtime_utils import prefetch_config, setup_logging


LOGGER = logging.getLogger("search_demo")


def parse_args() -> argparse.Namespace:
    config_path, cfg = prefetch_config("search_demo")
    parser = argparse.ArgumentParser(
        description="Hybrid search demo: BM25(FTS5) + vector retrieval + weighted fusion."
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
    parser.add_argument("--query", type=str, required=True, help="Query string.")
    parser.add_argument(
        "--index-dir",
        type=Path,
        default=Path(str(cfg.get("index_dir", "data/index"))),
        help="Directory containing vector index.",
    )
    parser.add_argument(
        "--corpus",
        type=Path,
        default=Path(str(cfg.get("corpus", "data/processed/corpus.jsonl"))),
        help="Corpus JSONL file used for metadata display.",
    )
    parser.add_argument(
        "--lexical-db",
        type=Path,
        default=Path(str(cfg.get("lexical_db", "data/index/lexical.db"))),
        help="SQLite lexical index db from build_lexical_index.py",
    )
    parser.add_argument("--top-k", type=int, default=int(cfg.get("top_k", 5)), help="Top K results.")
    parser.add_argument(
        "--vector-k",
        type=int,
        default=int(cfg.get("vector_k", 120)),
        help="Candidate count from vector retrieval.",
    )
    parser.add_argument(
        "--bm25-k",
        type=int,
        default=int(cfg.get("bm25_k", 120)),
        help="Candidate count from BM25 retrieval.",
    )
    parser.add_argument(
        "--chapter",
        type=str,
        default=str(cfg.get("chapter", "")),
        help="Optional chapter_key filter (for example: algebra, schemes).",
    )
    parser.add_argument(
        "--env",
        type=str,
        default=str(cfg.get("env", "")),
        help="Optional env_type filter (for example: lemma, theorem, definition).",
    )
    parser.add_argument(
        "--vector-weight",
        type=float,
        default=float(cfg.get("vector_weight", 0.55)),
        help="Weight for vector score in hybrid fusion.",
    )
    parser.add_argument(
        "--bm25-weight",
        type=float,
        default=float(cfg.get("bm25_weight", 0.45)),
        help="Weight for BM25 score in hybrid fusion.",
    )
    parser.add_argument(
        "--provider",
        type=str,
        default=str(cfg.get("provider", "")),
        choices=["", "hash", "openai", "local"],
        help="Optional override for query embedding provider. Empty means use index config.",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=str(cfg.get("model", "")),
        help="Optional override for query embedding model.",
    )
    parser.add_argument(
        "--dim",
        type=int,
        default=int(cfg.get("dim", 0)),
        help="Optional override embedding dimension. 0 means use index config.",
    )
    parser.add_argument(
        "--openai-api-key",
        type=str,
        default=str(cfg.get("openai_api_key", "")),
        help="OpenAI API key override for query embedding.",
    )
    parser.add_argument(
        "--openai-base-url",
        type=str,
        default=str(cfg.get("openai_base_url", "")),
        help="OpenAI base URL override for query embedding.",
    )
    parser.add_argument(
        "--openai-timeout-seconds",
        type=int,
        default=int(cfg.get("openai_timeout_seconds", 0)),
        help="OpenAI timeout override for query embedding.",
    )
    parser.add_argument(
        "--local-device",
        type=str,
        default=str(cfg.get("local_device", "")),
        help="Local embedding device override (cpu/cuda).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    setup_logging(args.log_level)

    matrix, ids, index_meta, query_cfg = load_vector_index(args.index_dir)
    corpus = load_corpus(args.corpus)

    params = resolve_query_embedding_params(
        index_meta=index_meta,
        query_cfg=query_cfg,
        provider_override=args.provider,
        model_override=args.model,
        dim_override=args.dim,
        openai_base_url_override=args.openai_base_url,
        openai_timeout_override=args.openai_timeout_seconds,
        local_device_override=args.local_device,
    )
    embedder = make_query_embedder(
        provider=params["provider"],
        model=params["model"],
        dim=params["dim"],
        batch_size=params["batch_size"],
        openai_base_url=params["openai_base_url"],
        openai_api_key=args.openai_api_key or None,
        openai_timeout_seconds=params["openai_timeout_seconds"],
        local_device=params["local_device"],
    )

    results = hybrid_search(
        query=args.query,
        matrix=matrix,
        ids=ids,
        corpus=corpus,
        lexical_db=args.lexical_db,
        embedder=embedder,
        vector_k=args.vector_k,
        bm25_k=args.bm25_k,
        vector_weight=args.vector_weight,
        bm25_weight=args.bm25_weight,
        chapter_filter=args.chapter,
        env_filter=args.env,
    )
    if not results:
        LOGGER.warning("No result. Try removing filters or rebuilding the index.")
        return 0

    shown = 0
    for doc_id, score, vscore, bscore in results:
        row = corpus.get(doc_id)
        if not row:
            continue
        shown += 1
        snippet = str(row.get("statement_text", "")).replace("\n", " ").strip()
        if len(snippet) > 240:
            snippet = snippet[:237] + "..."
        print(
            f"{shown}. tag={doc_id} hybrid={score:.4f} vec={vscore:.4f} bm25={bscore:.4f} "
            f"env={row.get('env_type','')} chapter={row.get('chapter_key','')} "
            f"ref={row.get('reference','')}"
        )
        if row.get("title"):
            print(f"   title: {row['title']}")
        if snippet:
            print(f"   text:  {snippet}")
        print("")
        if shown >= args.top_k:
            break

    if shown == 0:
        LOGGER.warning("No result after filtering.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

