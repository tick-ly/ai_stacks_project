from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def _skill_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _run_json(script: str, args: list[str]) -> dict[str, Any]:
    skill_root = _skill_root()
    cmd = [sys.executable, str(skill_root / "scripts" / script), *args]
    try:
        out = subprocess.check_output(
            cmd,
            cwd=str(skill_root),
            text=True,
            encoding="utf-8",
            errors="replace",
            stderr=subprocess.STDOUT,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.output or "").strip()
        if detail:
            raise RuntimeError(f"{script} failed: {detail}") from exc
        raise RuntimeError(f"{script} failed with exit code {exc.returncode}") from exc
    return json.loads(out.strip())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the AG skill pipeline end-to-end.")
    parser.add_argument("--query", type=str, required=True, help="User query.")
    parser.add_argument("--stacks-top-k", type=int, default=8, help="Stacks evidence size.")
    parser.add_argument("--papers-top-k", type=int, default=6, help="Paper evidence size.")
    parser.add_argument(
        "--papers-sources",
        type=str,
        default="",
        help=(
            "Optional comma-separated papers/web sources for retrieve_papers.py "
            "(e.g. arxiv,openalex,semanticscholar,crossref,mathoverflow,mathse,wikipedia)."
        ),
    )
    parser.add_argument(
        "--papers-per-source-k",
        type=int,
        default=0,
        help="Optional per-source raw retrieval size for retrieve_papers.py.",
    )
    parser.add_argument("--ca-bundle", type=str, default="", help="CA bundle path for paper retrieval.")
    parser.add_argument(
        "--prefer-system-truststore",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Prefer OS trust store for paper retrieval.",
    )
    parser.add_argument(
        "--no-certifi-fallback",
        action="store_true",
        default=False,
        help="Disable certifi fallback for paper retrieval.",
    )
    parser.add_argument(
        "--allow-insecure-ssl-fallback",
        action="store_true",
        default=False,
        help="Allow insecure SSL fallback only if explicitly requested.",
    )
    parser.add_argument(
        "--papers-ag-query-hint",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Auto append algebraic geometry hint when papers query is weak.",
    )
    parser.add_argument("--output", type=Path, default=None, help="Optional JSON output path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    relevance = _run_json("classify_relevance.py", ["--query", args.query])
    if relevance["label"] == "low":
        payload = {
            "query": args.query,
            "relevance": relevance,
            "route": "low_relevance_stop",
            "message": (
                "Input is low relevance to algebraic geometry. "
                "Ask user whether to reframe into AG context."
            ),
            "stacks": {"count": 0, "results": []},
            "papers": {"count": 0, "results": []},
            "citations": {"all_references": []},
        }
    else:
        warnings: list[str] = []

        stacks_error = None
        try:
            stacks = _run_json(
                "retrieve_stacks.py",
                ["--query", args.query, "--top-k", str(args.stacks_top_k)],
            )
        except RuntimeError as exc:
            stacks_error = str(exc)
            warnings.append(stacks_error)
            stacks = {
                "query": args.query,
                "count": 0,
                "results": [],
                "error": stacks_error,
            }

        papers_error = None
        try:
            papers = _run_json(
                "retrieve_papers.py",
                [
                    "--query",
                    args.query,
                    "--top-k",
                    str(args.papers_top_k),
                    *(["--ca-bundle", args.ca_bundle] if args.ca_bundle else []),
                    *(
                        ["--prefer-system-truststore"]
                        if args.prefer_system_truststore
                        else ["--no-prefer-system-truststore"]
                    ),
                    *(["--no-certifi-fallback"] if args.no_certifi_fallback else []),
                    *(
                        ["--allow-insecure-ssl-fallback"]
                        if args.allow_insecure_ssl_fallback
                        else []
                    ),
                    *(["--sources", args.papers_sources] if args.papers_sources else []),
                    *(
                        ["--per-source-k", str(args.papers_per_source_k)]
                        if args.papers_per_source_k > 0
                        else []
                    ),
                    *(
                        ["--ag-query-hint"]
                        if args.papers_ag_query_hint
                        else ["--no-ag-query-hint"]
                    ),
                ],
            )
        except RuntimeError as exc:
            papers_error = str(exc)
            warnings.append(papers_error)
            papers = {
                "query": args.query,
                "count": 0,
                "results": [],
                "insecure_ssl_fallback_used": False,
                "ssl_mode": "unavailable",
                "error": papers_error,
            }

        skill_root = _skill_root()
        tmp_dir = skill_root / "tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        stacks_json = tmp_dir / "stacks.json"
        papers_json = tmp_dir / "papers.json"
        stacks_json.write_text(json.dumps(stacks, ensure_ascii=False, indent=2), encoding="utf-8")
        papers_json.write_text(json.dumps(papers, ensure_ascii=False, indent=2), encoding="utf-8")

        try:
            citations = _run_json(
                "format_citations.py",
                ["--stacks-json", str(stacks_json), "--papers-json", str(papers_json)],
            )
        except RuntimeError as exc:
            citation_error = str(exc)
            warnings.append(citation_error)
            citations = {
                "stacks_references": [],
                "paper_references": [],
                "all_references": [],
                "error": citation_error,
            }

        stacks_count = int(stacks.get("count", 0) or 0)
        papers_count = int(papers.get("count", 0) or 0)
        if stacks_count > 0 and papers_count > 0:
            route = "ag_retrieval"
        elif stacks_count > 0:
            route = "stacks_only_degraded"
        elif papers_count > 0:
            route = "papers_only_degraded"
        else:
            route = "retrieval_unavailable"

        payload = {
            "query": args.query,
            "relevance": relevance,
            "route": route,
            "stacks": stacks,
            "papers": papers,
            "citations": citations,
            **({"warnings": warnings} if warnings else {}),
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
