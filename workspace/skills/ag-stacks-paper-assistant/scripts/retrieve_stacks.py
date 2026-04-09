from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _workspace_root() -> Path:
    # skill/scripts -> skill -> skills -> workspace
    return Path(__file__).resolve().parents[3]


def _load_engine():
    root = _workspace_root()
    sys.path.insert(0, str(root / "scripts"))
    from retrieval_engine import (  # type: ignore
        hybrid_search,
        load_corpus,
        load_vector_index,
        make_query_embedder,
        resolve_query_embedding_params,
    )

    return hybrid_search, load_corpus, load_vector_index, make_query_embedder, resolve_query_embedding_params


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Retrieve Stacks Project evidence from local hybrid index.")
    parser.add_argument("--query", type=str, required=True, help="Search query.")
    parser.add_argument("--top-k", type=int, default=8, help="Returned Stacks results.")
    parser.add_argument("--vector-k", type=int, default=120, help="Vector candidate size.")
    parser.add_argument("--bm25-k", type=int, default=120, help="BM25 candidate size.")
    parser.add_argument("--vector-weight", type=float, default=0.55, help="Vector fusion weight.")
    parser.add_argument("--bm25-weight", type=float, default=0.45, help="BM25 fusion weight.")
    parser.add_argument("--chapter", type=str, default="", help="Optional chapter_key filter.")
    parser.add_argument("--env", type=str, default="", help="Optional env_type filter.")
    parser.add_argument(
        "--index-dir",
        type=Path,
        default=Path("data/index"),
        help="Relative to workspace root unless absolute.",
    )
    parser.add_argument(
        "--corpus",
        type=Path,
        default=Path("data/processed/corpus.jsonl"),
        help="Relative to workspace root unless absolute.",
    )
    parser.add_argument(
        "--lexical-db",
        type=Path,
        default=Path("data/index/lexical.db"),
        help="Relative to workspace root unless absolute.",
    )
    parser.add_argument("--provider", type=str, default="", choices=["", "hash", "openai", "local"])
    parser.add_argument("--model", type=str, default="")
    parser.add_argument("--dim", type=int, default=0)
    parser.add_argument("--openai-api-key", type=str, default="")
    parser.add_argument("--openai-base-url", type=str, default="")
    parser.add_argument("--openai-timeout-seconds", type=int, default=0)
    parser.add_argument("--local-device", type=str, default="")
    parser.add_argument("--output", type=Path, default=None, help="Optional JSON output path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = _workspace_root()

    index_dir = args.index_dir if args.index_dir.is_absolute() else root / args.index_dir
    corpus_path = args.corpus if args.corpus.is_absolute() else root / args.corpus
    lexical_db = args.lexical_db if args.lexical_db.is_absolute() else root / args.lexical_db

    hybrid_search, load_corpus, load_vector_index, make_query_embedder, resolve_query_embedding_params = _load_engine()

    matrix, ids, index_meta, query_cfg = load_vector_index(index_dir)
    corpus = load_corpus(corpus_path)

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

    ranked = hybrid_search(
        query=args.query,
        matrix=matrix,
        ids=ids,
        corpus=corpus,
        lexical_db=lexical_db,
        embedder=embedder,
        vector_k=args.vector_k,
        bm25_k=args.bm25_k,
        vector_weight=args.vector_weight,
        bm25_weight=args.bm25_weight,
        chapter_filter=args.chapter,
        env_filter=args.env,
    )

    results = []
    for i, (tag, hybrid_score, vec_score, bm25_score) in enumerate(ranked[: args.top_k], start=1):
        row = corpus.get(tag, {})
        snippet = str(row.get("statement_text", "")).replace("\n", " ").strip()
        if len(snippet) > 260:
            snippet = snippet[:257] + "..."
        results.append(
            {
                "citation_id": f"S{i}",
                "tag": tag,
                "url": f"https://stacks.math.columbia.edu/tag/{tag}",
                "title": row.get("title", ""),
                "reference": row.get("reference", ""),
                "env_type": row.get("env_type", ""),
                "chapter_key": row.get("chapter_key", ""),
                "snippet": snippet,
                "scores": {
                    "hybrid": hybrid_score,
                    "vector": vec_score,
                    "bm25": bm25_score,
                },
            }
        )

    payload = {
        "query": args.query,
        "count": len(results),
        "results": results,
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
