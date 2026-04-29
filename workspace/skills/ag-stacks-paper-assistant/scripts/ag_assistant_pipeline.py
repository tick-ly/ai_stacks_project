from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


def _skill_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _run_json(script: str, args: list[str]) -> dict[str, Any]:
    skill_root = _skill_root()
    cmd = [sys.executable, str(skill_root / "scripts" / script), *args]
    script_error_codes = {
        "classify_relevance.py": "RELEVANCE_CLASSIFY_ERROR",
        "retrieve_stacks.py": "STACKS_RETRIEVAL_ERROR",
        "retrieve_papers.py": "PAPERS_RETRIEVAL_ERROR",
        "format_citations.py": "CITATION_FORMAT_ERROR",
    }

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
        try:
            payload = json.loads(detail)
            if isinstance(payload, dict) and isinstance(payload.get("error"), dict):
                err = payload["error"]
                if isinstance(err, dict):
                    err.setdefault("source", script)
                    return {"error": err}
        except Exception:
            pass
        return {
            "error": {
                "code": script_error_codes.get(script, "PIPELINE_SUBPROCESS_ERROR"),
                "message": detail or f"{script} failed with exit code {exc.returncode}",
                "source": script,
                "details": f"exit_code={exc.returncode}",
            }
        }
    except json.JSONDecodeError as exc:
        return {
            "error": {
                "code": "PIPELINE_JSON_DECODE_ERROR",
                "message": f"{script} produced invalid JSON.",
                "source": script,
                "details": str(exc),
            }
        }
    except Exception as exc:
        return {
            "error": {
                "code": "PIPELINE_SUBPROCESS_UNKNOWN_ERROR",
                "message": str(exc),
                "source": script,
            }
        }

    payload = out.strip()
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return {
            "error": {
                "code": "PIPELINE_JSON_DECODE_ERROR",
                "message": f"{script} produced invalid JSON.",
                "source": script,
                "details": payload[:512],
            }
        }
    if isinstance(parsed, dict):
        if isinstance(parsed.get("error"), dict):
            parsed_error = parsed["error"]
            if isinstance(parsed_error, dict):
                parsed_error.setdefault("source", script)
                return {"error": parsed_error}
        return parsed
    return {
        "error": {
            "code": "PIPELINE_NON_OBJECT_PAYLOAD",
            "message": f"{script} returned non-object payload.",
            "source": script,
        }
    }


def _normalize_warning(
    error: dict[str, Any],
    default_source: str,
) -> dict[str, Any]:
    if not isinstance(error, dict):
        return {"source": default_source, "code": "PIPELINE_UNKNOWN_ERROR", "message": str(error)}
    normalized = dict(error)
    normalized_source = str(normalized.get("source", "")).lower()
    if not normalized_source or normalized_source.endswith(".py"):
        normalized["source"] = default_source
    normalized.setdefault("code", "PIPELINE_UNKNOWN_ERROR")
    if "message" not in normalized:
        normalized["message"] = "Execution failed."
    normalized.setdefault("degrade_reason", _normalize_degrade_reason(normalized))
    return normalized


def _normalize_degrade_reason(error: dict[str, Any]) -> str:
    code = str(error.get("code", "")).upper()
    message = str(error.get("message", "")).lower()

    if code in {"TLS_ERROR", "TLS_RESTRICTED", "CERTIFICATE_ERROR"}:
        return "tls_restricted"
    if "certificate verify failed" in message:
        return "tls_restricted"
    if code.startswith("HTTP_"):
        status = code.split("_", 1)[1]
        if status in {"408", "429", "500", "502", "503", "504"}:
            return "timeout"
    if code in {"PARSE_ERROR", "PAPERS_PARSE_ERROR", "PIPELINE_JSON_DECODE_ERROR"}:
        return "parse_error"
    if "timed out" in message or "timeout" in message or "request timeout" in message:
        return "timeout"
    if code == "NO_MATCHES":
        return "no_matches"
    return "error"


def _build_degradation(
    source: str,
    payload: dict[str, Any],
    error: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if error is not None:
        return {
            "source": source,
            "code": error.get("code", "PIPELINE_UNKNOWN_ERROR"),
            "message": str(error.get("message", "Execution failed.")),
            "degrade_reason": _normalize_degrade_reason(error),
        }

    candidate_count = payload.get("count")
    if candidate_count is None:
        references = payload.get("all_references")
        if isinstance(references, list):
            candidate_count = len(references)
        else:
            candidate_count = 0

    if not payload or int(candidate_count) == 0:
        return {
            "source": source,
            "code": "NO_MATCHES",
            "message": f"{source} retrieval returned no results.",
            "degrade_reason": "no_matches",
        }
    return None


def _append_warning_once(
    warnings: list[dict[str, Any]],
    warning: dict[str, Any] | None,
) -> None:
    if warning is None:
        return
    for existing in warnings:
        if (
            existing.get("source") == warning.get("source")
            and existing.get("code") == warning.get("code")
            and existing.get("degrade_reason") == warning.get("degrade_reason")
        ):
            return
    warnings.append(warning)


def _compute_source_confidence(
    route: str,
    stacks: dict[str, Any],
    papers: dict[str, Any],
    citations: dict[str, Any],
    warnings: list[dict[str, Any]],
) -> float:
    if route in {"pipeline_failed", "low_relevance_stop"}:
        return 0.0

    stacks_count = int(stacks.get("count", 0) or 0)
    papers_count = int(papers.get("count", 0) or 0)

    score = 0.0
    if stacks_count > 0:
        score += 0.45
        score += min(0.25, 0.025 * min(stacks_count, 10))

    if papers_count > 0:
        score += 0.25
        score += min(0.20, 0.03 * min(papers_count, 10))
        if papers.get("insecure_ssl_fallback_used", False):
            score -= 0.06
        source_breakdown = papers.get("source_breakdown")
        if isinstance(source_breakdown, dict) and source_breakdown:
            ok_sources = [
                info
                for info in source_breakdown.values()
                if isinstance(info, dict)
                and info.get("status") == "ok"
                and int(info.get("count", 0) or 0) > 0
            ]
            score += 0.05 * (len(ok_sources) / max(1, len(source_breakdown)))

    if route == "stacks_only_degraded":
        score -= 0.10
    if route == "papers_only_degraded":
        score -= 0.10
    if route == "retrieval_unavailable":
        score = min(score, 0.05)

    if "all_references" in citations and len(citations.get("all_references", [])) > 0:
        score += 0.06

    for warning in warnings:
        reason = str(warning.get("degrade_reason", "")).lower()
        if reason == "parse_error":
            score -= 0.18
        elif reason == "tls_restricted":
            score -= 0.10
        elif reason == "timeout":
            score -= 0.08

    return round(max(0.0, min(1.0, score)), 4)


def _evidence_quality(score: float) -> str:
    if score >= 0.75:
        return "high"
    if score >= 0.45:
        return "medium"
    return "low"


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
    if "error" in relevance:
        payload = {
            "query": args.query,
            "route": "pipeline_failed",
            "error": _normalize_warning(relevance["error"], "relevance"),
            "relevance": None,
            "stacks": {"count": 0, "results": []},
            "papers": {"count": 0, "results": []},
            "citations": {"all_references": []},
            "degradations": [
                {
                    "source": "relevance",
                    "code": relevance["error"].get("code", "RELEVANCE_CLASSIFY_ERROR"),
                    "message": str(
                        relevance["error"].get("message")
                        if isinstance(relevance["error"], dict)
                        else "Relevance classification failed."
                    ),
                    "degrade_reason": _normalize_degrade_reason(
                        {
                            "code": relevance["error"].get("code", "RELEVANCE_CLASSIFY_ERROR")
                            if isinstance(relevance["error"], dict)
                            else "RELEVANCE_CLASSIFY_ERROR",
                            "message": str(
                                relevance["error"].get("message")
                                if isinstance(relevance["error"], dict)
                                else "Relevance classification failed."
                            ),
                        }
                    ),
                }
            ],
            "source_confidence": 0.0,
            "evidence_quality": "low",
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
            "source_confidence": 0.0,
            "evidence_quality": "low",
        }
    else:
        warnings: list[dict[str, Any]] = []
        degradations: list[dict[str, Any]] = []

        stacks_error: dict[str, Any] | None = None
        stacks = _run_json(
            "retrieve_stacks.py",
            ["--query", args.query, "--top-k", str(args.stacks_top_k)],
        )
        if "error" in stacks:
            stacks_error = _normalize_warning(stacks["error"], "stacks")
            warnings.append(stacks_error)
            stacks = {
                "query": args.query,
                "count": 0,
                "results": [],
                "error": stacks_error,
            }

        papers_error: dict[str, Any] | None = None
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
                *(
                    ["--sources", args.papers_sources] if args.papers_sources else []
                ),
                *(
                    ["--per-source-k", str(args.papers_per_source_k)]
                    if args.papers_per_source_k > 0
                    else []
                ),
                *(["--ag-query-hint"] if args.papers_ag_query_hint else ["--no-ag-query-hint"]),
            ],
        )
        if "error" in papers:
            papers_error = _normalize_warning(papers["error"], "papers")
            warnings.append(papers_error)
            papers = {
                "query": args.query,
                "count": 0,
                "results": [],
                "error": papers_error,
                "insecure_ssl_fallback_used": False,
                "ssl_mode": "unavailable",
            }

        skill_root = _skill_root()
        tmp_dir = skill_root / "tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        citations = None
        temp_files: list[Path] = []
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".json",
                prefix="stacks_",
                dir=tmp_dir,
                encoding="utf-8",
                delete=False,
            ) as stacks_json:
                json.dump(stacks, stacks_json, ensure_ascii=False, indent=2)
                stacks_json_path = Path(stacks_json.name)
                temp_files.append(stacks_json_path)

            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".json",
                prefix="papers_",
                dir=tmp_dir,
                encoding="utf-8",
                delete=False,
            ) as papers_json:
                json.dump(papers, papers_json, ensure_ascii=False, indent=2)
                papers_json_path = Path(papers_json.name)
                temp_files.append(papers_json_path)

            citations = _run_json(
                "format_citations.py",
                ["--stacks-json", str(stacks_json_path), "--papers-json", str(papers_json_path)],
            )
            if "error" in citations:
                citation_error = _normalize_warning(citations["error"], "citations")
                warnings.append(citation_error)
                citations = {
                    "stacks_references": [],
                    "paper_references": [],
                    "all_references": [],
                    "error": citation_error,
                }
        finally:
            for temp_file in temp_files:
                temp_file.unlink(missing_ok=True)

        if citations is None:
            citations = {
                "stacks_references": [],
                "paper_references": [],
                "all_references": [],
            }

        stacks_count = int(stacks.get("count", 0) or 0)
        papers_count = int(papers.get("count", 0) or 0)
        if stacks_count > 0 and papers_count > 0:
            route = "ag_retrieval"
        elif stacks_count > 0:
            route = "stacks_only_degraded"
        elif papers_count > 0:
            route = "papers_only_degraded"
        elif stacks_error and papers_error:
            route = "retrieval_unavailable"
        else:
            route = "retrieval_unavailable"

        degradation_stacks = _build_degradation("stacks", stacks, stacks_error)
        if degradation_stacks is not None:
            degradations.append(degradation_stacks)
            _append_warning_once(warnings, stacks_error or degradation_stacks)

        degradation_papers = _build_degradation("papers", papers, papers_error)
        if degradation_papers is not None:
            degradations.append(degradation_papers)
            _append_warning_once(warnings, papers_error or degradation_papers)

        if not any(item.get("source") == "citations" for item in warnings):
            citation_item = _build_degradation("citations", citations, citations.get("error"))
            if citation_item is not None:
                degradations.append(citation_item)
                _append_warning_once(warnings, citation_item)

        source_confidence = _compute_source_confidence(route, stacks, papers, citations, warnings)

        payload = {
            "query": args.query,
            "relevance": relevance,
            "route": route,
            "stacks": stacks,
            "papers": papers,
            "citations": citations,
            **({"warnings": warnings} if warnings else {}),
            "degradations": degradations,
            "source_confidence": source_confidence,
            "evidence_quality": _evidence_quality(source_confidence),
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
