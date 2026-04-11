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
        "--graph-seed-k",
        type=int,
        default=int(cfg.get("graph_seed_k", 20)),
        help="GraphRAG seed size from base ranking.",
    )
    parser.add_argument(
        "--graph-hops",
        type=int,
        default=int(cfg.get("graph_hops", 2)),
        help="Citation graph expansion hops.",
    )
    parser.add_argument(
        "--graph-expand-k",
        type=int,
        default=int(cfg.get("graph_expand_k", 80)),
        help="Max expanded docs taken from graph propagation.",
    )
    parser.add_argument(
        "--graph-weight",
        type=float,
        default=float(cfg.get("graph_weight", 0.35)),
        help="Weight of graph propagation score.",
    )
    parser.add_argument(
        "--graph-outgoing-weight",
        type=float,
        default=float(cfg.get("graph_outgoing_weight", 1.0)),
        help="Propagation weight on outgoing citation edges.",
    )
    parser.add_argument(
        "--graph-incoming-weight",
        type=float,
        default=float(cfg.get("graph_incoming_weight", 0.65)),
        help="Propagation weight on incoming citation edges.",
    )
    parser.add_argument(
        "--graph-hop-decay",
        type=float,
        default=float(cfg.get("graph_hop_decay", 0.55)),
        help="Per-hop decay for graph propagation.",
    )
    parser.add_argument(
        "--graph-centrality-weight",
        type=float,
        default=float(cfg.get("graph_centrality_weight", 0.10)),
        help="Weight of citation-centrality prior.",
    )
    parser.add_argument(
        "--statement-route-weight",
        type=float,
        default=float(cfg.get("statement_route_weight", 1.0)),
        help="Route weight for statement-oriented evidence.",
    )
    parser.add_argument(
        "--proof-route-weight",
        type=float,
        default=float(cfg.get("proof_route_weight", 1.0)),
        help="Route weight for proof-oriented evidence.",
    )
    parser.add_argument(
        "--statement-route-bonus",
        type=float,
        default=float(cfg.get("statement_route_bonus", 0.12)),
        help="Bonus for statement-rich docs when query is not proof intent.",
    )
    parser.add_argument(
        "--proof-route-bonus",
        type=float,
        default=float(cfg.get("proof_route_bonus", 0.45)),
        help="Bonus for docs with proof text when query wants proof.",
    )
    parser.add_argument(
        "--proof-route-fallback-bonus",
        type=float,
        default=float(cfg.get("proof_route_fallback_bonus", 0.10)),
        help="Fallback proof bonus for theorem/lemma/proposition docs without explicit proof text.",
    )
    parser.add_argument(
        "--nonproof-proof-penalty",
        type=float,
        default=float(cfg.get("nonproof_proof_penalty", 0.08)),
        help="Penalty for proof-heavy docs when query does not request proof.",
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
        graph_seed_k=args.graph_seed_k,
        graph_hops=args.graph_hops,
        graph_expand_k=args.graph_expand_k,
        graph_weight=args.graph_weight,
        graph_outgoing_weight=args.graph_outgoing_weight,
        graph_incoming_weight=args.graph_incoming_weight,
        graph_hop_decay=args.graph_hop_decay,
        graph_centrality_weight=args.graph_centrality_weight,
        statement_route_weight=args.statement_route_weight,
        proof_route_weight=args.proof_route_weight,
        statement_route_bonus=args.statement_route_bonus,
        proof_route_bonus=args.proof_route_bonus,
        proof_route_fallback_bonus=args.proof_route_fallback_bonus,
        nonproof_proof_penalty=args.nonproof_proof_penalty,
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
