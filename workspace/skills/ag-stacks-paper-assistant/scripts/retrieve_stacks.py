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
    parser.add_argument("--graph-seed-k", type=int, default=20, help="GraphRAG seed size from base ranking.")
    parser.add_argument("--graph-hops", type=int, default=2, help="Citation graph expansion hops.")
    parser.add_argument(
        "--graph-expand-k",
        type=int,
        default=80,
        help="Max expanded docs from graph propagation.",
    )
    parser.add_argument("--graph-weight", type=float, default=0.35, help="Weight of graph propagation score.")
    parser.add_argument(
        "--graph-outgoing-weight",
        type=float,
        default=1.0,
        help="Propagation weight on outgoing citation edges.",
    )
    parser.add_argument(
        "--graph-incoming-weight",
        type=float,
        default=0.65,
        help="Propagation weight on incoming citation edges.",
    )
    parser.add_argument("--graph-hop-decay", type=float, default=0.55, help="Per-hop decay for propagation.")
    parser.add_argument(
        "--graph-centrality-weight",
        type=float,
        default=0.10,
        help="Weight of citation-centrality prior.",
    )
    parser.add_argument("--statement-route-weight", type=float, default=1.0, help="Statement route weight.")
    parser.add_argument("--proof-route-weight", type=float, default=1.0, help="Proof route weight.")
    parser.add_argument(
        "--statement-route-bonus",
        type=float,
        default=0.12,
        help="Bonus for statement-rich docs when query is not proof intent.",
    )
    parser.add_argument(
        "--proof-route-bonus",
        type=float,
        default=0.45,
        help="Bonus for docs with proof text when query wants proof.",
    )
    parser.add_argument(
        "--proof-route-fallback-bonus",
        type=float,
        default=0.10,
        help="Fallback bonus for theorem/lemma/proposition docs when proof text is absent.",
    )
    parser.add_argument(
        "--nonproof-proof-penalty",
        type=float,
        default=0.08,
        help="Penalty for proof-heavy docs when query does not request proof.",
    )
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


def _degrade_reason_for_code(code: str) -> str:
    if code in {"TLS_ERROR", "TLS_RESTRICTED", "CERTIFICATE_ERROR"}:
        return "tls_restricted"
    if code.startswith("HTTP_"):
        status = code.split("_", 1)[1]
        if status in {"408", "429", "500", "502", "503", "504"}:
            return "timeout"
    if code in {"PARSE_ERROR", "STACKS_PARSE_ERROR"}:
        return "parse_error"
    return "error"


def main() -> int:
    try:
        args = parse_args()
        root = _workspace_root()

        index_dir = args.index_dir if args.index_dir.is_absolute() else root / args.index_dir
        corpus_path = args.corpus if args.corpus.is_absolute() else root / args.corpus
        lexical_db = args.lexical_db if args.lexical_db.is_absolute() else root / args.lexical_db

        (
            hybrid_search,
            load_corpus,
            load_vector_index,
            make_query_embedder,
            resolve_query_embedding_params,
        ) = _load_engine()

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

        results = []
        for i, (tag, hybrid_score, vec_score, bm25_score) in enumerate(
            ranked[: args.top_k], start=1
        ):
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

        if len(results) == 0:
            payload["warnings"] = [
                {
                    "source": "stacks",
                    "code": "NO_MATCHES",
                    "message": "Stacks retrieval returned no matches.",
                    "degrade_reason": "no_matches",
                }
            ]

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
    except Exception as exc:
        payload = {
            "error": {
                "code": "STACKS_RETRIEVAL_ERROR",
                "message": "Failed to retrieve Stacks evidence.",
                "source": "stacks",
                "degrade_reason": _degrade_reason_for_code("STACKS_RETRIEVAL_ERROR"),
                "details": str(exc),
            }
        }
        out = json.dumps(payload, ensure_ascii=False)
        sys.stdout.buffer.write((out + "\n").encode("utf-8", errors="replace"))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
