from __future__ import annotations

import argparse
import json
import logging
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from common import read_json, write_json
from runtime_utils import prefetch_config, setup_logging


LOGGER = logging.getLogger("run_retrieval_improvement")

DEFAULT_EMBEDDING_CANDIDATES: list[dict[str, Any]] = [
    {
        "name": "hash_baseline",
        "provider": "hash",
        "model": "hash-embedding-v1",
        "dim": 1536,
        "text_fields": "statement_text,normalized_text",
    },
    {
        "name": "local_minilm",
        "provider": "local",
        "model": "sentence-transformers/all-MiniLM-L6-v2",
        "dim": 384,
        "text_fields": "statement_text,normalized_text",
    },
]

DEFAULT_ROUTE_GRID: list[dict[str, Any]] = [
    {
        "name": "route_default",
        "statement_route_weight": 1.0,
        "proof_route_weight": 1.0,
        "statement_route_bonus": 0.12,
        "proof_route_bonus": 0.45,
        "proof_route_fallback_bonus": 0.10,
        "nonproof_proof_penalty": 0.08,
    },
    {
        "name": "route_statement_focused",
        "statement_route_weight": 1.2,
        "proof_route_weight": 0.8,
        "statement_route_bonus": 0.18,
        "proof_route_bonus": 0.40,
        "proof_route_fallback_bonus": 0.08,
        "nonproof_proof_penalty": 0.12,
    },
    {
        "name": "route_proof_focused",
        "statement_route_weight": 0.9,
        "proof_route_weight": 1.25,
        "statement_route_bonus": 0.08,
        "proof_route_bonus": 0.55,
        "proof_route_fallback_bonus": 0.14,
        "nonproof_proof_penalty": 0.06,
    },
]


def parse_args() -> argparse.Namespace:
    config_path, cfg = prefetch_config("run_retrieval_improvement")
    parser = argparse.ArgumentParser(
        description=(
            "One-click retrieval improvement runner: embedding model comparison + "
            "proof/statement route-balance grid search."
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
        "--workspace-root",
        type=Path,
        default=Path(str(cfg.get("workspace_root", "."))),
        help="Workspace root containing scripts/, config/, and data/.",
    )
    parser.add_argument(
        "--queries",
        type=Path,
        default=Path(str(cfg.get("queries", "config/eval_queries.sample.jsonl"))),
        help="Eval query JSONL.",
    )
    parser.add_argument(
        "--corpus",
        type=Path,
        default=Path(str(cfg.get("corpus", "data/processed/corpus.jsonl"))),
        help="Corpus JSONL.",
    )
    parser.add_argument(
        "--lexical-db",
        type=Path,
        default=Path(str(cfg.get("lexical_db", "data/index/lexical.db"))),
        help="Lexical SQLite DB path.",
    )
    parser.add_argument(
        "--index-root",
        type=Path,
        default=Path(str(cfg.get("index_root", "data/index_compare"))),
        help="Directory for per-candidate vector indexes.",
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=Path(str(cfg.get("report_dir", "data/eval/improvement_runs"))),
        help="Directory for eval outputs and summary reports.",
    )
    parser.add_argument(
        "--embedding-candidates-file",
        type=Path,
        default=Path(str(cfg.get("embedding_candidates_file", "config/embedding_candidates.sample.json"))),
        help="JSON file containing embedding candidates list.",
    )
    parser.add_argument(
        "--route-grid-file",
        type=Path,
        default=Path(str(cfg.get("route_grid_file", "config/route_balance_grid.sample.json"))),
        help="JSON file containing statement/proof route parameter grid.",
    )
    parser.add_argument(
        "--skip-embedding-build",
        action="store_true",
        default=bool(cfg.get("skip_embedding_build", False)),
        help="Skip build_embeddings and reuse existing indexes in index_root.",
    )
    parser.add_argument(
        "--incremental",
        action="store_true",
        default=bool(cfg.get("incremental", False)),
        help="Pass --incremental into build_embeddings.",
    )
    parser.add_argument(
        "--changed-tags-file",
        type=Path,
        default=Path(str(cfg.get("changed_tags_file", "data/raw/api/changed_tags.json"))),
        help="Changed tags file for incremental embedding builds.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=int(cfg.get("batch_size", 64)),
        help="Embedding batch size.",
    )
    parser.add_argument(
        "--k-values",
        type=str,
        default=str(cfg.get("k_values", "1,3,5,10")),
        help="K values for eval_retrieval.",
    )
    parser.add_argument(
        "--vector-k",
        type=int,
        default=int(cfg.get("vector_k", 120)),
        help="Vector candidate count.",
    )
    parser.add_argument(
        "--bm25-k",
        type=int,
        default=int(cfg.get("bm25_k", 120)),
        help="BM25 candidate count.",
    )
    parser.add_argument(
        "--vector-weight",
        type=float,
        default=float(cfg.get("vector_weight", 0.55)),
        help="Vector fusion weight.",
    )
    parser.add_argument(
        "--bm25-weight",
        type=float,
        default=float(cfg.get("bm25_weight", 0.45)),
        help="BM25 fusion weight.",
    )
    parser.add_argument(
        "--graph-seed-k",
        type=int,
        default=int(cfg.get("graph_seed_k", 20)),
        help="GraphRAG seed size.",
    )
    parser.add_argument(
        "--graph-hops",
        type=int,
        default=int(cfg.get("graph_hops", 2)),
        help="Graph expansion hops.",
    )
    parser.add_argument(
        "--graph-expand-k",
        type=int,
        default=int(cfg.get("graph_expand_k", 80)),
        help="Graph expansion top-k.",
    )
    parser.add_argument(
        "--graph-weight",
        type=float,
        default=float(cfg.get("graph_weight", 0.35)),
        help="Graph score weight.",
    )
    parser.add_argument(
        "--graph-outgoing-weight",
        type=float,
        default=float(cfg.get("graph_outgoing_weight", 1.0)),
        help="Outgoing edge propagation weight.",
    )
    parser.add_argument(
        "--graph-incoming-weight",
        type=float,
        default=float(cfg.get("graph_incoming_weight", 0.65)),
        help="Incoming edge propagation weight.",
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
        help="Centrality prior weight.",
    )
    parser.add_argument(
        "--openai-api-key",
        type=str,
        default=str(cfg.get("openai_api_key", "")),
        help="OpenAI API key for openai provider candidates.",
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
        help="Local embedding device.",
    )
    return parser.parse_args()


def run(cmd: list[str], cwd: Path) -> None:
    LOGGER.info("$ %s", " ".join(cmd))
    subprocess.run(cmd, cwd=str(cwd), check=True)


def load_json_list(path: Path, fallback: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not path.exists():
        return [dict(x) for x in fallback]
    payload = json.loads(path.read_text(encoding="utf-8-sig", errors="replace"))
    if not isinstance(payload, list):
        raise RuntimeError(f"Expected JSON list in {path}")
    out: list[dict[str, Any]] = []
    for item in payload:
        if isinstance(item, dict):
            out.append(dict(item))
    if not out:
        raise RuntimeError(f"No valid objects in {path}")
    return out


def slugify(text: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", text.strip())
    cleaned = cleaned.strip("._-")
    return cleaned.lower() or "unnamed"


def fmetric(obj: dict[str, Any], key: str) -> float:
    try:
        return float(obj.get(key, 0.0))
    except Exception:
        return 0.0


def compute_objective(metrics: dict[str, Any]) -> dict[str, float]:
    agg = metrics.get("aggregate", {}) if isinstance(metrics, dict) else {}
    by_category = metrics.get("aggregate_by_category", {}) if isinstance(metrics, dict) else {}
    if not isinstance(agg, dict):
        agg = {}
    if not isinstance(by_category, dict):
        by_category = {}

    overall_mrr10 = fmetric(agg, "mrr@10")
    overall_recall10 = fmetric(agg, "recall@10")
    proof_bucket = by_category.get("proof", {}) if isinstance(by_category.get("proof", {}), dict) else {}
    proof_mrr10 = fmetric(proof_bucket, "mrr@10")

    nonproof_vals: list[float] = []
    for key in ("definition", "theorem", "chapter_filter"):
        bucket = by_category.get(key, {})
        if isinstance(bucket, dict) and "mrr@10" in bucket:
            nonproof_vals.append(fmetric(bucket, "mrr@10"))
    nonproof_mrr10 = sum(nonproof_vals) / len(nonproof_vals) if nonproof_vals else overall_mrr10

    balance_gap = abs(proof_mrr10 - nonproof_mrr10)
    objective = (
        0.45 * overall_mrr10
        + 0.25 * overall_recall10
        + 0.20 * proof_mrr10
        + 0.10 * nonproof_mrr10
        - 0.05 * balance_gap
    )
    return {
        "objective": objective,
        "overall_mrr10": overall_mrr10,
        "overall_recall10": overall_recall10,
        "proof_mrr10": proof_mrr10,
        "nonproof_mrr10": nonproof_mrr10,
        "balance_gap": balance_gap,
    }


def normalize_path(root: Path, maybe_rel: Path) -> Path:
    return maybe_rel if maybe_rel.is_absolute() else root / maybe_rel


def main() -> int:
    args = parse_args()
    setup_logging(args.log_level)
    root = args.workspace_root.resolve()

    queries = normalize_path(root, args.queries)
    corpus = normalize_path(root, args.corpus)
    lexical_db = normalize_path(root, args.lexical_db)
    index_root = normalize_path(root, args.index_root)
    report_dir = normalize_path(root, args.report_dir)
    embedding_candidates_file = normalize_path(root, args.embedding_candidates_file)
    route_grid_file = normalize_path(root, args.route_grid_file)
    changed_tags_file = normalize_path(root, args.changed_tags_file)

    index_root.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)

    embedding_candidates = load_json_list(embedding_candidates_file, DEFAULT_EMBEDDING_CANDIDATES)
    route_grid = load_json_list(route_grid_file, DEFAULT_ROUTE_GRID)

    LOGGER.info(
        "Candidates=%d route_variants=%d queries=%s",
        len(embedding_candidates),
        len(route_grid),
        queries,
    )

    rows: list[dict[str, Any]] = []
    failed_candidates: list[dict[str, str]] = []
    skip_baseline_path = report_dir / "_skip_baseline.json"

    for cand_idx, candidate in enumerate(embedding_candidates, start=1):
        name = str(candidate.get("name", f"candidate_{cand_idx}")).strip()
        provider = str(candidate.get("provider", "hash")).strip()
        model = str(candidate.get("model", "hash-embedding-v1")).strip()
        dim = int(candidate.get("dim", 1536))
        text_fields = str(candidate.get("text_fields", "statement_text,normalized_text")).strip()
        if provider not in {"hash", "openai", "local"}:
            LOGGER.warning("Skip candidate %s due to unsupported provider=%s", name, provider)
            continue

        index_dir = index_root / slugify(name)

        try:
            if not args.skip_embedding_build:
                build_cmd = [
                    sys.executable,
                    "scripts/build_embeddings.py",
                    "--log-level",
                    args.log_level,
                    "--corpus",
                    str(corpus),
                    "--output-dir",
                    str(index_dir),
                    "--provider",
                    provider,
                    "--model",
                    model,
                    "--dim",
                    str(dim),
                    "--text-fields",
                    text_fields,
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
                    build_cmd += ["--openai-api-key", args.openai_api_key]
                if args.incremental:
                    build_cmd += ["--incremental", "--changed-tags-file", str(changed_tags_file)]
                run(build_cmd, root)
            elif not (index_dir / "embeddings.npy").exists():
                raise RuntimeError(f"Index not found for --skip-embedding-build candidate: {index_dir}")
        except Exception as exc:
            msg = str(exc)
            LOGGER.error("Skip candidate=%s due to build error: %s", name, msg)
            failed_candidates.append({"candidate_name": name, "stage": "build_embeddings", "error": msg})
            continue

        for route in route_grid:
            route_name = str(route.get("name", "route")).strip()
            out_path = report_dir / f"{slugify(name)}__{slugify(route_name)}.json"

            statement_route_weight = float(route.get("statement_route_weight", 1.0))
            proof_route_weight = float(route.get("proof_route_weight", 1.0))
            statement_route_bonus = float(route.get("statement_route_bonus", 0.12))
            proof_route_bonus = float(route.get("proof_route_bonus", 0.45))
            proof_route_fallback_bonus = float(route.get("proof_route_fallback_bonus", 0.10))
            nonproof_proof_penalty = float(route.get("nonproof_proof_penalty", 0.08))

            eval_cmd = [
                sys.executable,
                "scripts/eval_retrieval.py",
                "--log-level",
                args.log_level,
                "--queries",
                str(queries),
                "--index-dir",
                str(index_dir),
                "--corpus",
                str(corpus),
                "--lexical-db",
                str(lexical_db),
                "--k-values",
                args.k_values,
                "--vector-k",
                str(args.vector_k),
                "--bm25-k",
                str(args.bm25_k),
                "--vector-weight",
                str(args.vector_weight),
                "--bm25-weight",
                str(args.bm25_weight),
                "--graph-seed-k",
                str(args.graph_seed_k),
                "--graph-hops",
                str(args.graph_hops),
                "--graph-expand-k",
                str(args.graph_expand_k),
                "--graph-weight",
                str(args.graph_weight),
                "--graph-outgoing-weight",
                str(args.graph_outgoing_weight),
                "--graph-incoming-weight",
                str(args.graph_incoming_weight),
                "--graph-hop-decay",
                str(args.graph_hop_decay),
                "--graph-centrality-weight",
                str(args.graph_centrality_weight),
                "--statement-route-weight",
                str(statement_route_weight),
                "--proof-route-weight",
                str(proof_route_weight),
                "--statement-route-bonus",
                str(statement_route_bonus),
                "--proof-route-bonus",
                str(proof_route_bonus),
                "--proof-route-fallback-bonus",
                str(proof_route_fallback_bonus),
                "--nonproof-proof-penalty",
                str(nonproof_proof_penalty),
                "--baseline",
                str(skip_baseline_path),
                "--output",
                str(out_path),
            ]
            if args.openai_api_key:
                eval_cmd += ["--openai-api-key", args.openai_api_key]
            try:
                run(eval_cmd, root)
            except Exception as exc:
                msg = str(exc)
                LOGGER.error(
                    "Skip route candidate=%s route=%s due to eval error: %s",
                    name,
                    route_name,
                    msg,
                )
                failed_candidates.append(
                    {
                        "candidate_name": name,
                        "stage": f"eval:{route_name}",
                        "error": msg,
                    }
                )
                continue

            metrics = read_json(out_path, default={}) or {}
            objective_pack = compute_objective(metrics)
            rows.append(
                {
                    "candidate_name": name,
                    "candidate_provider": provider,
                    "candidate_model": model,
                    "candidate_dim": dim,
                    "candidate_text_fields": text_fields,
                    "route_name": route_name,
                    "route_params": {
                        "statement_route_weight": statement_route_weight,
                        "proof_route_weight": proof_route_weight,
                        "statement_route_bonus": statement_route_bonus,
                        "proof_route_bonus": proof_route_bonus,
                        "proof_route_fallback_bonus": proof_route_fallback_bonus,
                        "nonproof_proof_penalty": nonproof_proof_penalty,
                    },
                    "index_dir": str(index_dir),
                    "metrics_path": str(out_path),
                    **objective_pack,
                }
            )

    if not rows:
        raise RuntimeError("No experiment result produced.")

    ranked = sorted(rows, key=lambda x: float(x["objective"]), reverse=True)
    best = ranked[0]

    summary = {
        "best": best,
        "ranked": ranked,
        "failures": failed_candidates,
        "config": {
            "queries": str(queries),
            "corpus": str(corpus),
            "lexical_db": str(lexical_db),
            "index_root": str(index_root),
            "report_dir": str(report_dir),
            "graph": {
                "graph_seed_k": args.graph_seed_k,
                "graph_hops": args.graph_hops,
                "graph_expand_k": args.graph_expand_k,
                "graph_weight": args.graph_weight,
                "graph_outgoing_weight": args.graph_outgoing_weight,
                "graph_incoming_weight": args.graph_incoming_weight,
                "graph_hop_decay": args.graph_hop_decay,
                "graph_centrality_weight": args.graph_centrality_weight,
            },
        },
    }
    summary_json = report_dir / "summary.json"
    write_json(summary_json, summary)

    table_lines = [
        "# Retrieval Improvement Summary",
        "",
        "| Rank | Candidate | Route | Objective | MRR@10 | Recall@10 | Proof MRR@10 | Nonproof MRR@10 |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for i, row in enumerate(ranked[:20], start=1):
        table_lines.append(
            "| "
            + f"{i} | {row['candidate_name']} | {row['route_name']} | "
            + f"{float(row['objective']):.6f} | {float(row['overall_mrr10']):.6f} | "
            + f"{float(row['overall_recall10']):.6f} | {float(row['proof_mrr10']):.6f} | "
            + f"{float(row['nonproof_mrr10']):.6f} |"
        )
    table_lines += [
        "",
        "## Best Combo",
        "",
        f"- candidate: `{best['candidate_name']}` ({best['candidate_provider']} / {best['candidate_model']})",
        f"- route: `{best['route_name']}`",
        f"- objective: `{float(best['objective']):.6f}`",
        f"- index_dir: `{best['index_dir']}`",
        f"- metrics_path: `{best['metrics_path']}`",
        "",
        "Route parameters:",
        "",
        "```json",
        json.dumps(best["route_params"], ensure_ascii=False, indent=2),
        "```",
        "",
    ]
    summary_md = report_dir / "summary.md"
    summary_md.write_text("\n".join(table_lines), encoding="utf-8", newline="\n")

    LOGGER.info("One-click improvement done. best_candidate=%s best_route=%s objective=%.6f",
                best["candidate_name"], best["route_name"], float(best["objective"]))
    LOGGER.info("Summary JSON -> %s", summary_json)
    LOGGER.info("Summary MD -> %s", summary_md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
