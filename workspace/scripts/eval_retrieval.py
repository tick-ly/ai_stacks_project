from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Any

from common import read_json, read_jsonl, write_json
from retrieval_engine import (
    hybrid_search,
    load_corpus,
    load_vector_index,
    make_query_embedder,
    resolve_query_embedding_params,
)
from runtime_utils import prefetch_config, setup_logging


LOGGER = logging.getLogger("eval_retrieval")


def parse_k_values(raw: str) -> list[int]:
    values = []
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        values.append(int(chunk))
    if not values:
        raise RuntimeError("k-values cannot be empty")
    return sorted(set(values))


def parse_args() -> argparse.Namespace:
    config_path, cfg = prefetch_config("eval_retrieval")
    parser = argparse.ArgumentParser(
        description="Evaluate hybrid retrieval quality with Recall@K and MRR@K."
    )
    parser.add_argument("--config", type=Path, default=config_path, help="Path to JSON/YAML config.")
    parser.add_argument(
        "--log-level",
        type=str,
        default=str(cfg.get("log_level", "INFO")),
        help="Log level: DEBUG|INFO|WARNING|ERROR",
    )
    parser.add_argument(
        "--queries",
        type=Path,
        default=Path(str(cfg.get("queries", "config/eval_queries.sample.jsonl"))),
        help="JSONL query set with relevant tags.",
    )
    parser.add_argument(
        "--index-dir",
        type=Path,
        default=Path(str(cfg.get("index_dir", "data/index"))),
        help="Vector index directory.",
    )
    parser.add_argument(
        "--corpus",
        type=Path,
        default=Path(str(cfg.get("corpus", "data/processed/corpus.jsonl"))),
        help="Corpus JSONL path.",
    )
    parser.add_argument(
        "--lexical-db",
        type=Path,
        default=Path(str(cfg.get("lexical_db", "data/index/lexical.db"))),
        help="Lexical SQLite db.",
    )
    parser.add_argument(
        "--k-values",
        type=str,
        default=str(cfg.get("k_values", "1,3,5,10")),
        help="Comma-separated K values, e.g. 1,3,5,10",
    )
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
        "--vector-weight",
        type=float,
        default=float(cfg.get("vector_weight", 0.55)),
        help="Hybrid fusion weight for vector score.",
    )
    parser.add_argument(
        "--bm25-weight",
        type=float,
        default=float(cfg.get("bm25_weight", 0.45)),
        help="Hybrid fusion weight for BM25 score.",
    )
    parser.add_argument(
        "--provider",
        type=str,
        default=str(cfg.get("provider", "")),
        choices=["", "hash", "openai", "local"],
        help="Query embedding provider override.",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=str(cfg.get("model", "")),
        help="Query embedding model override.",
    )
    parser.add_argument("--dim", type=int, default=int(cfg.get("dim", 0)), help="Embedding dim override.")
    parser.add_argument(
        "--openai-api-key",
        type=str,
        default=str(cfg.get("openai_api_key", "")),
        help="OpenAI API key override.",
    )
    parser.add_argument(
        "--openai-base-url",
        type=str,
        default=str(cfg.get("openai_base_url", "")),
        help="OpenAI base URL override.",
    )
    parser.add_argument(
        "--openai-timeout-seconds",
        type=int,
        default=int(cfg.get("openai_timeout_seconds", 0)),
        help="OpenAI timeout override.",
    )
    parser.add_argument(
        "--local-device",
        type=str,
        default=str(cfg.get("local_device", "")),
        help="Local model device override.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(str(cfg.get("output", "data/eval/latest_metrics.json"))),
        help="Output metrics JSON path.",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=Path(str(cfg.get("baseline", "data/eval/baseline_metrics.json"))),
        help="Baseline metrics JSON path for regression checks.",
    )
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="Replace baseline file with current aggregate metrics.",
    )
    parser.add_argument(
        "--regress-if-below",
        type=str,
        default=str(cfg.get("regress_if_below", "mrr@10,recall@10")),
        help="Comma-separated metric keys to compare against baseline.",
    )
    parser.add_argument(
        "--regression-tolerance",
        type=float,
        default=float(cfg.get("regression_tolerance", 0.0)),
        help="Allowed drop before regression failure.",
    )
    return parser.parse_args()


def recall_at_k(ranked_tags: list[str], relevant_tags: set[str], k: int) -> float:
    if not relevant_tags:
        return 0.0
    hit = sum(1 for tag in ranked_tags[:k] if tag in relevant_tags)
    return hit / float(len(relevant_tags))


def mrr_at_k(ranked_tags: list[str], relevant_tags: set[str], k: int) -> float:
    for i, tag in enumerate(ranked_tags[:k], start=1):
        if tag in relevant_tags:
            return 1.0 / float(i)
    return 0.0


def aggregate_metrics(per_query: list[dict[str, Any]], k_values: list[int]) -> dict[str, float]:
    if not per_query:
        return {f"recall@{k}": 0.0 for k in k_values} | {f"mrr@{k}": 0.0 for k in k_values}
    out: dict[str, float] = {}
    for k in k_values:
        out[f"recall@{k}"] = sum(row[f"recall@{k}"] for row in per_query) / len(per_query)
        out[f"mrr@{k}"] = sum(row[f"mrr@{k}"] for row in per_query) / len(per_query)
    out["query_count"] = float(len(per_query))
    return out


def compare_with_baseline(
    current: dict[str, float],
    baseline: dict[str, Any],
    monitored_keys: list[str],
    tolerance: float,
) -> list[str]:
    failures: list[str] = []
    for key in monitored_keys:
        if key not in current:
            continue
        if key not in baseline:
            continue
        cur = float(current[key])
        base = float(baseline[key])
        if cur + tolerance < base:
            failures.append(f"{key}: current={cur:.6f} < baseline={base:.6f} (tol={tolerance})")
    return failures


def main() -> int:
    args = parse_args()
    setup_logging(args.log_level)
    k_values = parse_k_values(args.k_values)
    monitored_keys = [x.strip() for x in args.regress_if_below.split(",") if x.strip()]

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

    queries = list(read_jsonl(args.queries))
    if not queries:
        raise RuntimeError(f"No queries loaded from {args.queries}")

    per_query: list[dict[str, Any]] = []
    max_k = max(k_values)
    for item in queries:
        query = str(item.get("query", "")).strip()
        relevant_tags = {str(x) for x in item.get("relevant_tags", []) if str(x)}
        chapter = str(item.get("chapter", "") or "")
        env = str(item.get("env", "") or "")
        query_id = str(item.get("id", query))
        if not query or not relevant_tags:
            LOGGER.warning("Skip invalid eval row id=%s", query_id)
            continue

        results = hybrid_search(
            query=query,
            matrix=matrix,
            ids=ids,
            corpus=corpus,
            lexical_db=args.lexical_db,
            embedder=embedder,
            vector_k=max(args.vector_k, max_k),
            bm25_k=max(args.bm25_k, max_k),
            vector_weight=args.vector_weight,
            bm25_weight=args.bm25_weight,
            chapter_filter=chapter,
            env_filter=env,
        )
        ranked_tags = [tag for tag, _score, _vs, _bs in results]
        row: dict[str, Any] = {
            "id": query_id,
            "query": query,
            "relevant_tags": sorted(relevant_tags),
            "ranked_top": ranked_tags[:max_k],
        }
        for k in k_values:
            row[f"recall@{k}"] = recall_at_k(ranked_tags, relevant_tags, k)
            row[f"mrr@{k}"] = mrr_at_k(ranked_tags, relevant_tags, k)
        per_query.append(row)

    aggregate = aggregate_metrics(per_query, k_values)
    payload = {
        "aggregate": aggregate,
        "k_values": k_values,
        "query_count": len(per_query),
        "queries_file": str(args.queries),
        "index_dir": str(args.index_dir),
        "provider": params["provider"],
        "model": params["model"],
        "vector_weight": args.vector_weight,
        "bm25_weight": args.bm25_weight,
        "per_query": per_query,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_json(args.output, payload)
    LOGGER.info("Metrics written -> %s", args.output)
    LOGGER.info("Aggregate: %s", aggregate)

    if args.update_baseline:
        args.baseline.parent.mkdir(parents=True, exist_ok=True)
        write_json(args.baseline, aggregate)
        LOGGER.info("Baseline updated -> %s", args.baseline)
        return 0

    if args.baseline.exists():
        baseline = read_json(args.baseline, default={}) or {}
        failures = compare_with_baseline(
            current=aggregate,
            baseline=baseline,
            monitored_keys=monitored_keys,
            tolerance=args.regression_tolerance,
        )
        if failures:
            for fail in failures:
                LOGGER.error("Regression: %s", fail)
            return 3
        LOGGER.info("Regression check passed against baseline -> %s", args.baseline)
    else:
        LOGGER.warning("Baseline file not found: %s (skip regression check)", args.baseline)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

