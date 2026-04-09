from __future__ import annotations

import argparse
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path


ARXIV_API = "https://export.arxiv.org/api/query"
ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}
DEFAULT_AG_CATEGORIES = (
    "math.AG",
    "math.AC",
    "math.RT",
    "math.NT",
    "math.KT",
    "math.RA",
    "math.AT",
)


def _build_ssl_context(
    ca_bundle: str,
    prefer_system_truststore: bool,
    allow_certifi_fallback: bool,
) -> tuple[ssl.SSLContext, str]:
    # 1) explicit CA bundle has highest priority
    if ca_bundle:
        bundle_path = Path(ca_bundle)
        if not bundle_path.exists():
            raise RuntimeError(f"CA bundle not found: {bundle_path}")
        ctx = ssl.create_default_context(cafile=str(bundle_path))
        return ctx, f"custom_ca_bundle:{bundle_path}"

    # 2) standard env override
    env_bundle = os.getenv("SSL_CERT_FILE", "").strip()
    if env_bundle:
        env_path = Path(env_bundle)
        if env_path.exists():
            ctx = ssl.create_default_context(cafile=str(env_path))
            return ctx, f"env_ssl_cert_file:{env_path}"

    # 3) OS trust store via truststore package (recommended)
    if prefer_system_truststore:
        try:
            import truststore  # type: ignore

            ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ctx.verify_mode = ssl.CERT_REQUIRED
            ctx.check_hostname = True
            return ctx, "system_truststore"
        except Exception:
            pass

    # 4) certifi fallback
    if allow_certifi_fallback:
        try:
            import certifi  # type: ignore

            ctx = ssl.create_default_context(cafile=certifi.where())
            return ctx, "certifi_bundle"
        except Exception:
            pass

    # 5) default python context
    return ssl.create_default_context(), "python_default"


def _download_with_context(
    req: urllib.request.Request,
    timeout_seconds: int,
    ctx: ssl.SSLContext,
    retries: int,
) -> str:
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout_seconds, context=ctx) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            last_error = exc
            # Backoff on rate limit / transient server errors.
            if exc.code in (429, 500, 502, 503, 504) and attempt < retries:
                time.sleep(min(2.0 * attempt, 10.0))
                continue
            raise
        except Exception as exc:  # pragma: no cover
            last_error = exc
            if attempt < retries:
                time.sleep(0.5 * attempt)
    assert last_error is not None
    raise last_error


def _is_tls_error(exc: Exception) -> bool:
    if isinstance(exc, ssl.SSLError):
        return True
    if isinstance(exc, urllib.error.URLError):
        reason = getattr(exc, "reason", None)
        if isinstance(reason, ssl.SSLError):
            return True
        text = str(reason or exc).lower()
        if "certificate verify failed" in text:
            return True
    text = str(exc).lower()
    return "certificate verify failed" in text


def _parse_categories(categories_raw: str) -> list[str]:
    values = [x.strip() for x in categories_raw.split(",") if x.strip()]
    seen: set[str] = set()
    deduped: list[str] = []
    for category in values:
        if category in seen:
            continue
        seen.add(category)
        deduped.append(category)
    return deduped


def _build_search_query(query: str, categories: list[str]) -> str:
    query_expr = f"(all:{query})"
    if not categories:
        return query_expr
    cat_expr = " OR ".join(f"cat:{cat}" for cat in categories)
    return f"{query_expr} AND ({cat_expr})"


def _format_authors(authors: list[str], max_authors: int = 6) -> str:
    clean = [a for a in authors if a]
    if len(clean) <= max_authors:
        return ", ".join(clean)
    head = ", ".join(clean[:max_authors])
    return f"{head}, et al."


def fetch_arxiv(
    query: str,
    categories: list[str],
    max_results: int,
    timeout_seconds: int,
    retries: int,
    ca_bundle: str,
    prefer_system_truststore: bool,
    allow_certifi_fallback: bool,
    allow_insecure_ssl_fallback: bool,
) -> tuple[list[dict[str, str]], bool, str]:
    search_query = _build_search_query(query=query, categories=categories)
    q = urllib.parse.quote_plus(search_query)
    url = (
        f"{ARXIV_API}?search_query={q}"
        f"&start=0&max_results={max_results}&sortBy=relevance&sortOrder=descending"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "ag-stacks-paper-assistant/0.1"})
    insecure_fallback_used = False
    ssl_mode = ""
    try:
        ctx, ssl_mode = _build_ssl_context(
            ca_bundle=ca_bundle,
            prefer_system_truststore=prefer_system_truststore,
            allow_certifi_fallback=allow_certifi_fallback,
        )
        xml_text = _download_with_context(
            req=req,
            timeout_seconds=timeout_seconds,
            ctx=ctx,
            retries=retries,
        )
    except Exception as primary_error:
        if not _is_tls_error(primary_error):
            raise RuntimeError(f"Paper retrieval failed: {primary_error}") from primary_error
        if not allow_insecure_ssl_fallback:
            raise RuntimeError(
                "TLS verification failed. "
                "Try installing truststore/certifi, set --ca-bundle, or set SSL_CERT_FILE."
            ) from primary_error
        insecure_fallback_used = True
        ssl_mode = "insecure_fallback"
        ctx = ssl._create_unverified_context()
        xml_text = _download_with_context(
            req=req,
            timeout_seconds=timeout_seconds,
            ctx=ctx,
            retries=retries,
        )

    root = ET.fromstring(xml_text)
    results: list[dict[str, str]] = []

    for entry in root.findall("atom:entry", ATOM_NS):
        title = (entry.findtext("atom:title", default="", namespaces=ATOM_NS) or "").strip()
        summary = (entry.findtext("atom:summary", default="", namespaces=ATOM_NS) or "").strip()
        published = (entry.findtext("atom:published", default="", namespaces=ATOM_NS) or "").strip()
        authors = [
            (x.findtext("atom:name", default="", namespaces=ATOM_NS) or "").strip()
            for x in entry.findall("atom:author", ATOM_NS)
        ]
        link = ""
        for ln in entry.findall("atom:link", ATOM_NS):
            href = ln.attrib.get("href", "")
            rel = ln.attrib.get("rel", "")
            if rel == "alternate" and href:
                link = href
                break
        if not link:
            link = (entry.findtext("atom:id", default="", namespaces=ATOM_NS) or "").strip()

        year_match = re.match(r"^(\d{4})-", published)
        year = year_match.group(1) if year_match else ""

        results.append(
            {
                "title": title,
                "authors": _format_authors(authors),
                "year": year,
                "published": published,
                "summary": summary,
                "url": link,
                "source": "arXiv",
            }
        )
    return results, insecure_fallback_used, ssl_mode


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Retrieve paper metadata from arXiv.")
    parser.add_argument("--query", type=str, required=True, help="Query string.")
    parser.add_argument(
        "--categories",
        type=str,
        default=",".join(DEFAULT_AG_CATEGORIES),
        help="Comma-separated arXiv categories to constrain retrieval.",
    )
    parser.add_argument("--top-k", type=int, default=6, help="Max paper results.")
    parser.add_argument("--timeout-seconds", type=int, default=30, help="HTTP timeout seconds.")
    parser.add_argument("--retries", type=int, default=3, help="Retry attempts for arXiv request.")
    parser.add_argument(
        "--ca-bundle",
        type=str,
        default="",
        help="Path to PEM bundle with trusted CAs.",
    )
    parser.add_argument(
        "--prefer-system-truststore",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Prefer OS trust store via truststore package.",
    )
    parser.add_argument(
        "--no-certifi-fallback",
        action="store_true",
        help="Disable certifi CA bundle fallback.",
    )
    parser.add_argument(
        "--allow-insecure-ssl-fallback",
        action="store_true",
        default=False,
        help=(
            "Allow unverified SSL fallback if certificate validation fails. "
            "Use only in constrained environments."
        ),
    )
    parser.add_argument("--output", type=Path, default=None, help="Optional JSON output path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    categories = _parse_categories(args.categories)
    papers, insecure_fallback_used, ssl_mode = fetch_arxiv(
        args.query,
        categories=categories,
        max_results=args.top_k,
        timeout_seconds=args.timeout_seconds,
        retries=args.retries,
        ca_bundle=args.ca_bundle,
        prefer_system_truststore=args.prefer_system_truststore,
        allow_certifi_fallback=not args.no_certifi_fallback,
        allow_insecure_ssl_fallback=args.allow_insecure_ssl_fallback,
    )
    results = []
    for i, item in enumerate(papers, start=1):
        results.append(
            {
                "citation_id": f"P{i}",
                **item,
            }
        )
    payload = {
        "query": args.query,
        "count": len(results),
        "insecure_ssl_fallback_used": insecure_fallback_used,
        "ssl_mode": ssl_mode,
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
