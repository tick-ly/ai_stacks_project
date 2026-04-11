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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ARXIV_API = "https://export.arxiv.org/api/query"
OPENALEX_API = "https://api.openalex.org/works"
SEMANTIC_SCHOLAR_API = "https://api.semanticscholar.org/graph/v1/paper/search"
CROSSREF_API = "https://api.crossref.org/works"
WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
STACKEXCHANGE_API = "https://api.stackexchange.com/2.3/search/advanced"

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
DEFAULT_SOURCES = (
    "arxiv",
    "openalex",
    "semanticscholar",
    "crossref",
    "mathoverflow",
    "mathse",
    "wikipedia",
)
SOURCE_LABELS = {
    "arxiv": "arXiv",
    "openalex": "OpenAlex",
    "semanticscholar": "Semantic Scholar",
    "crossref": "Crossref",
    "mathoverflow": "MathOverflow",
    "mathse": "Math StackExchange",
    "wikipedia": "Wikipedia",
}
SOURCE_WEIGHTS = {
    "arxiv": 1.00,
    "openalex": 0.92,
    "semanticscholar": 0.88,
    "crossref": 0.80,
    "mathoverflow": 0.82,
    "mathse": 0.72,
    "wikipedia": 0.58,
}
AG_HINT_TERMS = (
    "scheme",
    "morphism",
    "sheaf",
    "stack",
    "moduli",
    "cohomology",
    "divisor",
    "etale",
    "flat",
    "affine",
    "proper",
    "algebraic geometry",
    "代数几何",
    "概形",
    "层",
    "态射",
    "上同调",
    "平坦",
)

TITLE_NORMALIZE_RE = re.compile(r"[^a-z0-9]+")
DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.IGNORECASE)
ARXIV_ID_RE = re.compile(
    r"(?:arxiv\.org/(?:abs|pdf)/|^)(\d{4}\.\d{4,5}(?:v\d+)?)",
    re.IGNORECASE,
)


def _build_ssl_context(
    ca_bundle: str,
    prefer_system_truststore: bool,
    allow_certifi_fallback: bool,
) -> tuple[ssl.SSLContext, str]:
    if ca_bundle:
        bundle_path = Path(ca_bundle)
        if not bundle_path.exists():
            raise RuntimeError(f"CA bundle not found: {bundle_path}")
        return ssl.create_default_context(cafile=str(bundle_path)), f"custom_ca_bundle:{bundle_path}"

    env_bundle = os.getenv("SSL_CERT_FILE", "").strip()
    if env_bundle:
        env_path = Path(env_bundle)
        if env_path.exists():
            return ssl.create_default_context(cafile=str(env_path)), f"env_ssl_cert_file:{env_path}"

    if prefer_system_truststore:
        try:
            import truststore  # type: ignore

            ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ctx.verify_mode = ssl.CERT_REQUIRED
            ctx.check_hostname = True
            return ctx, "system_truststore"
        except Exception:
            pass

    if allow_certifi_fallback:
        try:
            import certifi  # type: ignore

            return ssl.create_default_context(cafile=certifi.where()), "certifi_bundle"
        except Exception:
            pass

    return ssl.create_default_context(), "python_default"


def _download_text(
    req: urllib.request.Request,
    timeout_seconds: int,
    retries: int,
    ctx: ssl.SSLContext,
) -> str:
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout_seconds, context=ctx) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            last_error = exc
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
    return "certificate verify failed" in str(exc).lower()


def _parse_categories(categories_raw: str) -> list[str]:
    values = [x.strip() for x in categories_raw.split(",") if x.strip()]
    seen: set[str] = set()
    out: list[str] = []
    for category in values:
        if category in seen:
            continue
        seen.add(category)
        out.append(category)
    return out


def _parse_sources(sources_raw: str) -> list[str]:
    values = [x.strip().lower() for x in sources_raw.split(",") if x.strip()]
    if not values:
        return list(DEFAULT_SOURCES)
    seen: set[str] = set()
    out: list[str] = []
    for source in values:
        if source in seen:
            continue
        if source not in SOURCE_LABELS:
            raise RuntimeError(
                f"Unsupported source '{source}'. Supported: {', '.join(sorted(SOURCE_LABELS))}"
            )
        seen.add(source)
        out.append(source)
    return out


def _format_authors(authors: list[str], max_authors: int = 6) -> str:
    clean = [a.strip() for a in authors if a and a.strip()]
    if len(clean) <= max_authors:
        return ", ".join(clean)
    return ", ".join(clean[:max_authors]) + ", et al."


def _short_text(text: str, limit: int = 420) -> str:
    compact = re.sub(r"\s+", " ", text or "").strip()
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."


def _clean_html_snippet(text: str) -> str:
    no_tags = re.sub(r"<[^>]+>", " ", text or "")
    no_entities = re.sub(r"&[A-Za-z0-9#]+;", " ", no_tags)
    return _short_text(no_entities)


def _extract_year(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        m = re.search(r"(19|20)\d{2}", value)
        return m.group(0) if m else ""
    if isinstance(value, dict):
        date_parts = value.get("date-parts")
        if isinstance(date_parts, list) and date_parts and isinstance(date_parts[0], list) and date_parts[0]:
            first = date_parts[0][0]
            if isinstance(first, int):
                return str(first)
            if isinstance(first, str):
                return _extract_year(first)
    return ""


def _year_from_unix_timestamp(value: Any) -> str:
    try:
        ts = int(value)
    except Exception:
        return ""
    if ts <= 0:
        return ""
    try:
        return str(datetime.fromtimestamp(ts, tz=timezone.utc).year)
    except Exception:
        return ""


def _normalize_title(title: str) -> str:
    lowered = title.lower().strip()
    lowered = TITLE_NORMALIZE_RE.sub(" ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def _extract_doi(text: str) -> str:
    if not text:
        return ""
    m = DOI_RE.search(text)
    return m.group(0).lower() if m else ""


def _extract_arxiv_id(text: str) -> str:
    if not text:
        return ""
    m = ARXIV_ID_RE.search(text.strip())
    return m.group(1).lower() if m else ""


def _reconstruct_openalex_abstract(inverted_index: dict[str, list[int]] | None) -> str:
    if not isinstance(inverted_index, dict) or not inverted_index:
        return ""
    max_pos = -1
    for positions in inverted_index.values():
        if not isinstance(positions, list):
            continue
        for pos in positions:
            if isinstance(pos, int) and pos > max_pos:
                max_pos = pos
    if max_pos < 0 or max_pos > 5000:
        return ""
    words = [""] * (max_pos + 1)
    for token, positions in inverted_index.items():
        if not isinstance(token, str) or not isinstance(positions, list):
            continue
        for pos in positions:
            if isinstance(pos, int) and 0 <= pos < len(words):
                words[pos] = token
    return _short_text(" ".join(w for w in words if w))


def _query_tokens(query: str) -> set[str]:
    return {x for x in re.findall(r"[A-Za-z0-9]+", query.lower()) if len(x) >= 3}


def _looks_ag_like(query: str) -> bool:
    lowered = query.lower()
    return any(term in lowered for term in AG_HINT_TERMS)


def _build_web_query(query: str, use_ag_hint: bool) -> str:
    if not use_ag_hint:
        return query
    return query if _looks_ag_like(query) else f"{query} algebraic geometry"


def _canonical_doc_key(item: dict[str, Any]) -> str:
    doi = str(item.get("doi", "")).strip().lower()
    if doi:
        return f"doi:{doi}"
    arxiv_id = str(item.get("arxiv_id", "")).strip().lower()
    if arxiv_id:
        return f"arxiv:{arxiv_id}"
    url = str(item.get("url", "")).strip().lower()
    doi_from_url = _extract_doi(url)
    if doi_from_url:
        return f"doi:{doi_from_url}"
    arxiv_from_url = _extract_arxiv_id(url)
    if arxiv_from_url:
        return f"arxiv:{arxiv_from_url}"
    title_norm = _normalize_title(str(item.get("title", "")))
    if title_norm:
        return f"title:{title_norm}"
    return f"url:{url}" if url else ""


def _source_rank_score(source_key: str, rank: int) -> float:
    base = SOURCE_WEIGHTS.get(source_key, 0.5)
    return base / (1.0 + 0.12 * max(0, rank - 1))


def _token_overlap_score(title: str, summary: str, query_tokens: set[str]) -> float:
    if not query_tokens:
        return 0.0
    haystack = f"{title} {summary}".lower()
    hits = sum(1 for tok in query_tokens if tok in haystack)
    return min(hits / max(1.0, float(len(query_tokens))), 1.0)


def _recency_score(year: str) -> float:
    try:
        y = int(year)
    except Exception:
        return 0.0
    now_year = datetime.now(timezone.utc).year
    if y <= 1900 or y > now_year + 1:
        return 0.0
    delta = max(0, now_year - y)
    if delta <= 1:
        return 1.0
    if delta <= 3:
        return 0.8
    if delta <= 6:
        return 0.55
    if delta <= 10:
        return 0.30
    return 0.12


def _score_item(item: dict[str, Any], query_tokens: set[str]) -> float:
    rank_signal = float(item.get("_rank_signal", 0.0))
    overlap = _token_overlap_score(
        title=str(item.get("title", "")),
        summary=str(item.get("summary", "")),
        query_tokens=query_tokens,
    )
    recency = _recency_score(str(item.get("year", "")))
    source_count = len(item.get("provenance", [])) if isinstance(item.get("provenance"), list) else 1
    source_bonus = min(0.08 * float(source_count), 0.24)
    id_bonus = 0.08 if item.get("doi") or item.get("arxiv_id") else 0.0
    return rank_signal + 0.45 * overlap + 0.25 * recency + source_bonus + id_bonus


def _build_arxiv_query(query: str, categories: list[str]) -> str:
    query_expr = f"(all:{query})"
    if not categories:
        return query_expr
    cat_expr = " OR ".join(f"cat:{cat}" for cat in categories)
    return f"{query_expr} AND ({cat_expr})"


def fetch_arxiv(
    query: str,
    categories: list[str],
    max_results: int,
    timeout_seconds: int,
    retries: int,
    ctx: ssl.SSLContext,
) -> list[dict[str, Any]]:
    search_query = _build_arxiv_query(query=query, categories=categories)
    q = urllib.parse.quote_plus(search_query)
    url = (
        f"{ARXIV_API}?search_query={q}"
        f"&start=0&max_results={max_results}&sortBy=relevance&sortOrder=descending"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "ag-stacks-paper-assistant/0.2"})
    xml_text = _download_text(req=req, timeout_seconds=timeout_seconds, retries=retries, ctx=ctx)
    root = ET.fromstring(xml_text)

    items: list[dict[str, Any]] = []
    for entry in root.findall("atom:entry", ATOM_NS):
        title = (entry.findtext("atom:title", default="", namespaces=ATOM_NS) or "").strip()
        summary = (entry.findtext("atom:summary", default="", namespaces=ATOM_NS) or "").strip()
        published = (entry.findtext("atom:published", default="", namespaces=ATOM_NS) or "").strip()
        entry_id = (entry.findtext("atom:id", default="", namespaces=ATOM_NS) or "").strip()
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
            link = entry_id

        items.append(
            {
                "title": title,
                "authors": _format_authors(authors),
                "year": _extract_year(published),
                "summary": _short_text(summary),
                "url": link,
                "source": SOURCE_LABELS["arxiv"],
                "doi": "",
                "arxiv_id": _extract_arxiv_id(link) or _extract_arxiv_id(entry_id),
            }
        )
    return items


def fetch_openalex(
    query: str,
    max_results: int,
    timeout_seconds: int,
    retries: int,
    ctx: ssl.SSLContext,
) -> list[dict[str, Any]]:
    params = {
        "search": query,
        "per-page": str(max_results),
        "sort": "relevance_score:desc",
    }
    url = f"{OPENALEX_API}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "ag-stacks-paper-assistant/0.2"})
    text = _download_text(req=req, timeout_seconds=timeout_seconds, retries=retries, ctx=ctx)
    payload = json.loads(text)

    rows = payload.get("results", [])
    if not isinstance(rows, list):
        return []
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        title = str(row.get("display_name", "")).strip()
        year = _extract_year(row.get("publication_year"))
        abstract = _reconstruct_openalex_abstract(row.get("abstract_inverted_index"))

        author_names: list[str] = []
        authorships = row.get("authorships", [])
        if isinstance(authorships, list):
            for author_item in authorships:
                if not isinstance(author_item, dict):
                    continue
                author_obj = author_item.get("author")
                if isinstance(author_obj, dict):
                    name = str(author_obj.get("display_name", "")).strip()
                    if name:
                        author_names.append(name)

        doi = str(row.get("doi", "")).strip().lower()
        if doi.startswith("https://doi.org/"):
            doi = doi.replace("https://doi.org/", "", 1)

        url_value = ""
        primary_location = row.get("primary_location", {})
        if isinstance(primary_location, dict):
            url_value = str(primary_location.get("landing_page_url", "")).strip()
        if not url_value and doi:
            url_value = f"https://doi.org/{doi}"
        if not url_value:
            url_value = str(row.get("id", "")).strip()

        out.append(
            {
                "title": title,
                "authors": _format_authors(author_names),
                "year": year,
                "summary": _short_text(abstract),
                "url": url_value,
                "source": SOURCE_LABELS["openalex"],
                "doi": doi,
                "arxiv_id": "",
            }
        )
    return out


def fetch_semantic_scholar(
    query: str,
    max_results: int,
    timeout_seconds: int,
    retries: int,
    ctx: ssl.SSLContext,
) -> list[dict[str, Any]]:
    params = {
        "query": query,
        "limit": str(max_results),
        "fields": "title,year,authors,url,abstract,externalIds",
    }
    url = f"{SEMANTIC_SCHOLAR_API}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "ag-stacks-paper-assistant/0.2"})
    text = _download_text(req=req, timeout_seconds=timeout_seconds, retries=retries, ctx=ctx)
    payload = json.loads(text)

    rows = payload.get("data", [])
    if not isinstance(rows, list):
        return []
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        title = str(row.get("title", "")).strip()
        year = _extract_year(row.get("year"))
        abstract = _short_text(str(row.get("abstract", "")).strip())

        authors = row.get("authors", [])
        author_names: list[str] = []
        if isinstance(authors, list):
            for author in authors:
                if not isinstance(author, dict):
                    continue
                name = str(author.get("name", "")).strip()
                if name:
                    author_names.append(name)

        external_ids = row.get("externalIds", {})
        doi = ""
        arxiv_id = ""
        if isinstance(external_ids, dict):
            doi = str(external_ids.get("DOI", "")).strip().lower()
            arxiv_id = str(external_ids.get("ArXiv", "")).strip().lower()

        url_value = str(row.get("url", "")).strip()
        if not url_value and doi:
            url_value = f"https://doi.org/{doi}"

        out.append(
            {
                "title": title,
                "authors": _format_authors(author_names),
                "year": year,
                "summary": abstract,
                "url": url_value,
                "source": SOURCE_LABELS["semanticscholar"],
                "doi": doi,
                "arxiv_id": arxiv_id,
            }
        )
    return out


def fetch_crossref(
    query: str,
    max_results: int,
    timeout_seconds: int,
    retries: int,
    ctx: ssl.SSLContext,
) -> list[dict[str, Any]]:
    params = {
        "rows": str(max_results),
        "sort": "relevance",
        "order": "desc",
        "query.bibliographic": query,
        "select": "DOI,title,author,issued,URL,container-title,abstract",
    }
    url = f"{CROSSREF_API}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "ag-stacks-paper-assistant/0.2"})
    text = _download_text(req=req, timeout_seconds=timeout_seconds, retries=retries, ctx=ctx)
    payload = json.loads(text)

    message = payload.get("message", {})
    rows = message.get("items", []) if isinstance(message, dict) else []
    if not isinstance(rows, list):
        return []
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        title_arr = row.get("title", [])
        title = str(title_arr[0]).strip() if isinstance(title_arr, list) and title_arr else ""

        authors = row.get("author", [])
        author_names: list[str] = []
        if isinstance(authors, list):
            for author in authors:
                if not isinstance(author, dict):
                    continue
                given = str(author.get("given", "")).strip()
                family = str(author.get("family", "")).strip()
                name = " ".join(x for x in [given, family] if x)
                if name:
                    author_names.append(name)

        doi = str(row.get("DOI", "")).strip().lower()
        year = _extract_year(row.get("issued"))
        abstract = _clean_html_snippet(str(row.get("abstract", "")).strip())

        url_value = str(row.get("URL", "")).strip()
        if not url_value and doi:
            url_value = f"https://doi.org/{doi}"

        out.append(
            {
                "title": title,
                "authors": _format_authors(author_names),
                "year": year,
                "summary": abstract,
                "url": url_value,
                "source": SOURCE_LABELS["crossref"],
                "doi": doi,
                "arxiv_id": "",
            }
        )
    return out


def fetch_wikipedia(
    query: str,
    max_results: int,
    timeout_seconds: int,
    retries: int,
    ctx: ssl.SSLContext,
) -> list[dict[str, Any]]:
    params = {
        "action": "query",
        "format": "json",
        "list": "search",
        "srsearch": query,
        "srlimit": str(max_results),
        "utf8": "1",
    }
    url = f"{WIKIPEDIA_API}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "ag-stacks-paper-assistant/0.2"})
    text = _download_text(req=req, timeout_seconds=timeout_seconds, retries=retries, ctx=ctx)
    payload = json.loads(text)

    query_obj = payload.get("query", {})
    rows = query_obj.get("search", []) if isinstance(query_obj, dict) else []
    if not isinstance(rows, list):
        return []
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        title = str(row.get("title", "")).strip()
        snippet = _clean_html_snippet(str(row.get("snippet", "")))
        url_value = (
            "https://en.wikipedia.org/wiki/" + urllib.parse.quote(title.replace(" ", "_"))
            if title
            else ""
        )
        out.append(
            {
                "title": title,
                "authors": "",
                "year": "",
                "summary": snippet,
                "url": url_value,
                "source": SOURCE_LABELS["wikipedia"],
                "doi": "",
                "arxiv_id": "",
            }
        )
    return out


def fetch_stackexchange_site(
    query: str,
    site: str,
    source_label: str,
    max_results: int,
    timeout_seconds: int,
    retries: int,
    ctx: ssl.SSLContext,
) -> list[dict[str, Any]]:
    params = {
        "order": "desc",
        "sort": "relevance",
        "q": query,
        "site": site,
        "pagesize": str(max_results),
        "filter": "default",
    }
    url = f"{STACKEXCHANGE_API}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "ag-stacks-paper-assistant/0.2"})
    text = _download_text(req=req, timeout_seconds=timeout_seconds, retries=retries, ctx=ctx)
    payload = json.loads(text)

    rows = payload.get("items", [])
    if not isinstance(rows, list):
        return []
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        title = str(row.get("title", "")).strip()
        link = str(row.get("link", "")).strip()
        tags = row.get("tags", [])
        tags_text = ", ".join(str(t) for t in tags[:6]) if isinstance(tags, list) else ""
        score = row.get("score")
        answer_count = row.get("answer_count")
        is_answered = bool(row.get("is_answered", False))
        summary = f"tags: {tags_text}; score: {score}; answers: {answer_count}; accepted/answered: {is_answered}"
        out.append(
            {
                "title": title,
                "authors": "",
                "year": _year_from_unix_timestamp(row.get("creation_date")),
                "summary": _short_text(summary),
                "url": link,
                "source": source_label,
                "doi": "",
                "arxiv_id": "",
            }
        )
    return out


def _run_source(
    source: str,
    query: str,
    categories: list[str],
    per_source_k: int,
    timeout_seconds: int,
    retries: int,
    ctx: ssl.SSLContext,
) -> list[dict[str, Any]]:
    if source == "arxiv":
        return fetch_arxiv(
            query=query,
            categories=categories,
            max_results=per_source_k,
            timeout_seconds=timeout_seconds,
            retries=retries,
            ctx=ctx,
        )
    if source == "openalex":
        return fetch_openalex(
            query=query,
            max_results=per_source_k,
            timeout_seconds=timeout_seconds,
            retries=retries,
            ctx=ctx,
        )
    if source == "semanticscholar":
        return fetch_semantic_scholar(
            query=query,
            max_results=per_source_k,
            timeout_seconds=timeout_seconds,
            retries=retries,
            ctx=ctx,
        )
    if source == "crossref":
        return fetch_crossref(
            query=query,
            max_results=per_source_k,
            timeout_seconds=timeout_seconds,
            retries=retries,
            ctx=ctx,
        )
    if source == "mathoverflow":
        return fetch_stackexchange_site(
            query=query,
            site="mathoverflow.net",
            source_label=SOURCE_LABELS["mathoverflow"],
            max_results=per_source_k,
            timeout_seconds=timeout_seconds,
            retries=retries,
            ctx=ctx,
        )
    if source == "mathse":
        return fetch_stackexchange_site(
            query=query,
            site="math",
            source_label=SOURCE_LABELS["mathse"],
            max_results=per_source_k,
            timeout_seconds=timeout_seconds,
            retries=retries,
            ctx=ctx,
        )
    if source == "wikipedia":
        return fetch_wikipedia(
            query=query,
            max_results=per_source_k,
            timeout_seconds=timeout_seconds,
            retries=retries,
            ctx=ctx,
        )
    raise RuntimeError(f"Unsupported source: {source}")


def _merge_candidate(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    for field in ("title", "authors", "year", "summary", "url", "doi", "arxiv_id"):
        if not existing.get(field) and incoming.get(field):
            existing[field] = incoming[field]

    if len(str(incoming.get("summary", ""))) > len(str(existing.get("summary", ""))):
        existing["summary"] = incoming.get("summary", "")

    incoming_provenance = incoming.get("provenance", [])
    if isinstance(incoming_provenance, list):
        merged = list(existing.get("provenance", []))
        for source_name in incoming_provenance:
            if source_name not in merged:
                merged.append(source_name)
        existing["provenance"] = merged

    existing["_rank_signal"] = max(
        float(existing.get("_rank_signal", 0.0)),
        float(incoming.get("_rank_signal", 0.0)),
    )
    return existing


def aggregate_sources(
    query: str,
    categories: list[str],
    sources: list[str],
    top_k: int,
    per_source_k: int,
    timeout_seconds: int,
    retries: int,
    ca_bundle: str,
    prefer_system_truststore: bool,
    allow_certifi_fallback: bool,
    allow_insecure_ssl_fallback: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any], bool, str]:
    verified_ctx, ssl_mode = _build_ssl_context(
        ca_bundle=ca_bundle,
        prefer_system_truststore=prefer_system_truststore,
        allow_certifi_fallback=allow_certifi_fallback,
    )
    insecure_ctx = ssl._create_unverified_context()
    insecure_used = False

    diagnostics: dict[str, Any] = {}
    merged: dict[str, dict[str, Any]] = {}
    query_tokens = _query_tokens(query)

    for source in sources:
        source_label = SOURCE_LABELS[source]
        try:
            items = _run_source(
                source=source,
                query=query,
                categories=categories,
                per_source_k=per_source_k,
                timeout_seconds=timeout_seconds,
                retries=retries,
                ctx=verified_ctx,
            )
            used_ssl = ssl_mode
        except Exception as exc:
            if _is_tls_error(exc) and allow_insecure_ssl_fallback:
                try:
                    items = _run_source(
                        source=source,
                        query=query,
                        categories=categories,
                        per_source_k=per_source_k,
                        timeout_seconds=timeout_seconds,
                        retries=retries,
                        ctx=insecure_ctx,
                    )
                    insecure_used = True
                    used_ssl = "insecure_fallback"
                except Exception as insecure_exc:
                    diagnostics[source] = {
                        "label": source_label,
                        "status": "error",
                        "error": str(insecure_exc),
                        "count": 0,
                    }
                    continue
            else:
                diagnostics[source] = {
                    "label": source_label,
                    "status": "error",
                    "error": str(exc),
                    "count": 0,
                }
                continue

        diagnostics[source] = {
            "label": source_label,
            "status": "ok",
            "count": len(items),
            "ssl_mode": used_ssl,
        }

        for rank, item in enumerate(items, start=1):
            if not isinstance(item, dict):
                continue
            candidate = {
                "title": str(item.get("title", "")).strip(),
                "authors": str(item.get("authors", "")).strip(),
                "year": str(item.get("year", "")).strip(),
                "summary": str(item.get("summary", "")).strip(),
                "url": str(item.get("url", "")).strip(),
                "source": source_label,
                "doi": str(item.get("doi", "")).strip().lower(),
                "arxiv_id": str(item.get("arxiv_id", "")).strip().lower(),
                "provenance": [source_label],
                "_rank_signal": _source_rank_score(source, rank),
            }
            if not candidate["doi"]:
                candidate["doi"] = _extract_doi(candidate["url"])
            if not candidate["arxiv_id"]:
                candidate["arxiv_id"] = _extract_arxiv_id(candidate["url"])

            key = _canonical_doc_key(candidate)
            if not key:
                continue
            if key in merged:
                merged[key] = _merge_candidate(merged[key], candidate)
            else:
                merged[key] = candidate

    ranked: list[dict[str, Any]] = []
    for item in merged.values():
        if not item.get("title") and not item.get("summary"):
            continue
        item["_score"] = _score_item(item, query_tokens)
        ranked.append(item)

    ranked.sort(key=lambda x: float(x.get("_score", 0.0)), reverse=True)

    final_results: list[dict[str, Any]] = []
    for i, item in enumerate(ranked[:top_k], start=1):
        sources_joined = " + ".join(item.get("provenance", []))
        final_results.append(
            {
                "citation_id": f"P{i}",
                "title": item.get("title", ""),
                "authors": item.get("authors", ""),
                "year": item.get("year", ""),
                "summary": item.get("summary", ""),
                "url": item.get("url", ""),
                "source": sources_joined,
                "provenance": item.get("provenance", []),
                "score": round(float(item.get("_score", 0.0)), 6),
            }
        )

    return final_results, diagnostics, insecure_used, ssl_mode


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Retrieve paper/web evidence from multiple public sources "
            "(arXiv/OpenAlex/SemanticScholar/Crossref/Wikipedia) "
            "with deduped fusion ranking."
        )
    )
    parser.add_argument("--query", type=str, required=True, help="Query string.")
    parser.add_argument(
        "--categories",
        type=str,
        default=",".join(DEFAULT_AG_CATEGORIES),
        help="Comma-separated arXiv categories (applies to arXiv source only).",
    )
    parser.add_argument(
        "--sources",
        type=str,
        default=",".join(DEFAULT_SOURCES),
        help=(
            "Comma-separated sources. Default: "
            "arxiv,openalex,semanticscholar,crossref,mathoverflow,mathse,wikipedia"
        ),
    )
    parser.add_argument("--top-k", type=int, default=6, help="Max merged output results.")
    parser.add_argument(
        "--per-source-k",
        type=int,
        default=8,
        help="Raw results per source before dedupe and rerank.",
    )
    parser.add_argument("--timeout-seconds", type=int, default=30, help="HTTP timeout seconds.")
    parser.add_argument("--retries", type=int, default=3, help="Retry attempts per source request.")
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
    parser.add_argument(
        "--ag-query-hint",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Auto-append 'algebraic geometry' when query AG signal is weak.",
    )
    parser.add_argument("--output", type=Path, default=None, help="Optional JSON output path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    categories = _parse_categories(args.categories)
    sources = _parse_sources(args.sources)
    effective_query = _build_web_query(args.query, use_ag_hint=args.ag_query_hint)

    results, diagnostics, insecure_used, ssl_mode = aggregate_sources(
        query=effective_query,
        categories=categories,
        sources=sources,
        top_k=max(1, args.top_k),
        per_source_k=max(1, args.per_source_k),
        timeout_seconds=max(5, args.timeout_seconds),
        retries=max(1, args.retries),
        ca_bundle=args.ca_bundle,
        prefer_system_truststore=args.prefer_system_truststore,
        allow_certifi_fallback=not args.no_certifi_fallback,
        allow_insecure_ssl_fallback=args.allow_insecure_ssl_fallback,
    )

    warnings: list[str] = []
    for source_key, info in diagnostics.items():
        if not isinstance(info, dict):
            continue
        if info.get("status") == "error":
            warnings.append(f"{source_key} failed: {info.get('error', 'unknown error')}")

    payload = {
        "query": args.query,
        "effective_query": effective_query,
        "count": len(results),
        "sources": sources,
        "categories": categories,
        "insecure_ssl_fallback_used": insecure_used,
        "ssl_mode": ssl_mode,
        "source_breakdown": diagnostics,
        "results": results,
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
