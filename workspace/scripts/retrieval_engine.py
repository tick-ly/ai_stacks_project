from __future__ import annotations

import math
import json
import re
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from common import read_json, read_jsonl, tokenize
from embeddings_providers import make_embedder


TAG_EXACT_RE = re.compile(r"^[0-9A-Z]{4}$")
REFERENCE_RE = re.compile(r"\b\d+\.\d+(?:\.\d+)?\b")

# Keep the table small and targeted: high-value AG retrieval terms only.
CHINESE_QUERY_EXPANSIONS: tuple[tuple[str, str], ...] = (
    ("\u6982\u5f62", "scheme"),
    ("\u5c42", "sheaf"),
    ("\u5e73\u5766", "flat"),
    ("\u6001\u5c04", "morphism"),
    ("\u4ee3\u6570\u6808", "algebraic stack"),
    ("\u4e0a\u540c\u8c03", "cohomology"),
    ("\u4f59\u5207", "cotangent"),
    ("\u9664\u5b50", "divisor"),
    ("\u5b9a\u4e49", "definition"),
    ("\u5f15\u7406", "lemma"),
    ("\u5b9a\u7406", "theorem"),
    ("\u8bc1\u660e", "proof"),
)

INTENT_ENV_HINTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("definition", ("definition", "define", "\u5b9a\u4e49", "\u4ec0\u4e48\u662f")),
    ("theorem", ("theorem", "\u5b9a\u7406")),
    ("lemma", ("lemma", "\u5f15\u7406")),
    ("proposition", ("proposition", "\u547d\u9898")),
    ("remark", ("remark", "\u6ce8\u8bb0")),
)

PROOF_HINTS: tuple[str, ...] = ("proof", "prove", "\u8bc1\u660e", "\u5982\u4f55\u8bc1\u660e")

_GRAPH_CACHE: dict[tuple[int, int], dict[str, Any]] = {}


def minmax_normalize(scores: dict[str, float]) -> dict[str, float]:
    if not scores:
        return {}
    values = list(scores.values())
    lo = min(values)
    hi = max(values)
    if hi - lo <= 1e-12:
        return {k: 1.0 for k in scores}
    return {k: (v - lo) / (hi - lo) for k, v in scores.items()}


def tokenize_for_fts(query: str) -> str:
    tokens = tokenize(query)
    if not tokens:
        return ""
    return " ".join(tokens)


def expand_query_for_retrieval(query: str) -> str:
    expansions: list[str] = []
    for needle, expansion in CHINESE_QUERY_EXPANSIONS:
        if needle in query:
            expansions.append(expansion)
    if not expansions:
        return query
    return f"{query} {' '.join(expansions)}"


def detect_query_intent(query: str, chapter_keys: set[str]) -> dict[str, Any]:
    lowered = query.lower()
    stripped = query.strip()
    tag_hint = stripped.upper() if TAG_EXACT_RE.fullmatch(stripped.upper()) else ""

    prefer_env = ""
    for env, hints in INTENT_ENV_HINTS:
        if any(h in lowered for h in hints):
            prefer_env = env
            break

    wants_proof = any(h in lowered for h in PROOF_HINTS)
    reference_hint = ""
    ref_match = REFERENCE_RE.search(query)
    if ref_match:
        reference_hint = ref_match.group(0)

    chapter_hints: set[str] = set()
    normalized = lowered.replace("_", " ").replace("-", " ")
    for chapter_key in chapter_keys:
        ck = chapter_key.lower()
        if ck in lowered or ck.replace("-", " ") in normalized:
            chapter_hints.add(chapter_key)

    return {
        "tag_hint": tag_hint,
        "prefer_env": prefer_env,
        "wants_proof": wants_proof,
        "reference_hint": reference_hint,
        "chapter_hints": chapter_hints,
    }


def load_corpus(corpus_path: Path) -> dict[str, dict[str, Any]]:
    return {row["id"]: row for row in read_jsonl(corpus_path) if row.get("id")}


def row_passes_filters(row: dict[str, Any], chapter_filter: str, env_filter: str) -> bool:
    chapter_ok = not chapter_filter or str(row.get("chapter_key", "")) == chapter_filter
    env_ok = not env_filter or str(row.get("env_type", "")) == env_filter
    return chapter_ok and env_ok


def compute_intent_boost(
    doc_id: str,
    row: dict[str, Any],
    intent: dict[str, Any],
    query_tokens: set[str],
    statement_route_weight: float,
    proof_route_weight: float,
    statement_route_bonus: float,
    proof_route_bonus: float,
    proof_route_fallback_bonus: float,
    nonproof_proof_penalty: float,
) -> float:
    score = 0.0

    if intent["tag_hint"] and doc_id == intent["tag_hint"]:
        score += 10.0

    row_env = str(row.get("env_type", ""))
    row_chapter = str(row.get("chapter_key", ""))
    row_ref = str(row.get("reference", ""))
    has_statement = bool(str(row.get("statement_text", "")).strip())
    has_proof = bool(str(row.get("proof_text", "")).strip())
    statement_scale = max(0.0, statement_route_weight)
    proof_scale = max(0.0, proof_route_weight)

    if intent["prefer_env"] and row_env == intent["prefer_env"]:
        score += 0.75
    if intent["wants_proof"]:
        if has_proof:
            score += max(0.0, proof_route_bonus) * proof_scale
        elif row_env in {"theorem", "lemma", "proposition"}:
            score += max(0.0, proof_route_fallback_bonus) * proof_scale
        if has_statement:
            score += 0.05 * statement_scale
    else:
        if has_statement:
            score += max(0.0, statement_route_bonus) * statement_scale
        if has_proof:
            score -= max(0.0, nonproof_proof_penalty) * proof_scale

    if intent["reference_hint"] and row_ref == intent["reference_hint"]:
        score += 0.60
    if intent["chapter_hints"] and row_chapter in intent["chapter_hints"]:
        score += 0.35

    keyword_space = f"{row.get('title', '')} {row.get('full_label', '')}".lower().replace("-", " ")
    keyword_hits = sum(1 for tok in query_tokens if len(tok) >= 3 and tok in keyword_space)
    score += min(0.05 * keyword_hits, 0.35)
    return score


def build_citation_graph(corpus: dict[str, dict[str, Any]]) -> dict[str, Any]:
    key = (id(corpus), len(corpus))
    cached = _GRAPH_CACHE.get(key)
    if cached is not None:
        return cached

    outgoing: dict[str, list[str]] = {}
    incoming: dict[str, list[str]] = defaultdict(list)
    reference_to_tags: dict[str, list[str]] = defaultdict(list)

    for doc_id, row in corpus.items():
        reference = str(row.get("reference", "")).strip()
        if reference:
            reference_to_tags[reference].append(doc_id)

        refs = row.get("outgoing_refs", [])
        if not isinstance(refs, list):
            refs = []
        uniq_targets: list[str] = []
        seen_targets: set[str] = set()
        for target_raw in refs:
            target = str(target_raw).strip().upper()
            if not target or target == doc_id or target in seen_targets or target not in corpus:
                continue
            seen_targets.add(target)
            uniq_targets.append(target)
            incoming[target].append(doc_id)
        if uniq_targets:
            outgoing[doc_id] = uniq_targets

    centrality_raw: dict[str, float] = {}
    for doc_id in corpus.keys():
        indeg = len(incoming.get(doc_id, []))
        outdeg = len(outgoing.get(doc_id, []))
        centrality_raw[doc_id] = math.log1p(indeg) + 0.35 * math.log1p(outdeg)

    graph = {
        "outgoing": outgoing,
        "incoming": dict(incoming),
        "reference_to_tags": dict(reference_to_tags),
        "centrality_raw": centrality_raw,
    }
    _GRAPH_CACHE.clear()
    _GRAPH_CACHE[key] = graph
    return graph


def graphrag_expand_scores(
    base_scores: dict[str, float],
    corpus: dict[str, dict[str, Any]],
    intent: dict[str, Any],
    chapter_filter: str,
    env_filter: str,
    seed_k: int,
    hops: int,
    expand_k: int,
    outgoing_weight: float,
    incoming_weight: float,
    hop_decay: float,
) -> tuple[set[str], dict[str, float], dict[str, float]]:
    if not base_scores or hops <= 0 or expand_k <= 0:
        return set(base_scores.keys()), {}, {}

    graph = build_citation_graph(corpus)
    outgoing = graph["outgoing"]
    incoming = graph["incoming"]
    reference_to_tags = graph["reference_to_tags"]
    centrality_raw = graph["centrality_raw"]

    sorted_base = sorted(base_scores.items(), key=lambda x: x[1], reverse=True)
    seed_ids: list[str] = []
    for doc_id, _score in sorted_base:
        row = corpus.get(doc_id, {})
        if row and row_passes_filters(row, chapter_filter, env_filter):
            seed_ids.append(doc_id)
        if len(seed_ids) >= max(1, seed_k):
            break

    tag_hint = str(intent.get("tag_hint", ""))
    if tag_hint:
        row = corpus.get(tag_hint, {})
        if row and row_passes_filters(row, chapter_filter, env_filter):
            seed_ids.append(tag_hint)

    ref_hint = str(intent.get("reference_hint", ""))
    if ref_hint:
        for doc_id in reference_to_tags.get(ref_hint, []):
            row = corpus.get(doc_id, {})
            if row and row_passes_filters(row, chapter_filter, env_filter):
                seed_ids.append(doc_id)

    if not seed_ids:
        return set(base_scores.keys()), {}, {}

    seed_signal: dict[str, float] = {}
    for rank, doc_id in enumerate(seed_ids, start=1):
        if doc_id in seed_signal:
            continue
        base = max(float(base_scores.get(doc_id, 0.0)), 0.05)
        rank_decay = 1.0 / (1.0 + 0.2 * float(rank - 1))
        seed_signal[doc_id] = base * rank_decay

    graph_scores: dict[str, float] = defaultdict(float)
    frontier: dict[str, float] = dict(seed_signal)
    for hop in range(1, hops + 1):
        if not frontier:
            break
        hop_weight = hop_decay ** float(hop - 1)
        next_frontier: dict[str, float] = defaultdict(float)
        for node, signal in frontier.items():
            if signal <= 0.0:
                continue

            out_neighbors = outgoing.get(node, [])
            if out_neighbors:
                spread = signal * outgoing_weight * hop_weight / math.sqrt(float(len(out_neighbors)))
                for dst in out_neighbors:
                    row = corpus.get(dst, {})
                    if not row or not row_passes_filters(row, chapter_filter, env_filter):
                        continue
                    graph_scores[dst] += spread
                    next_frontier[dst] += spread

            in_neighbors = incoming.get(node, [])
            if in_neighbors:
                spread = signal * incoming_weight * hop_weight / math.sqrt(float(len(in_neighbors)))
                for dst in in_neighbors:
                    row = corpus.get(dst, {})
                    if not row or not row_passes_filters(row, chapter_filter, env_filter):
                        continue
                    graph_scores[dst] += spread
                    next_frontier[dst] += spread

        if not next_frontier:
            frontier = {}
            continue
        frontier_items = sorted(next_frontier.items(), key=lambda x: x[1], reverse=True)
        frontier = dict(frontier_items[: max(expand_k * 2, 32)])

    candidate_ids = set(base_scores.keys())
    if graph_scores:
        top_expanded = sorted(graph_scores.items(), key=lambda x: x[1], reverse=True)[:expand_k]
        candidate_ids |= {doc_id for doc_id, _score in top_expanded}

    centrality_scores = {doc_id: float(centrality_raw.get(doc_id, 0.0)) for doc_id in candidate_ids}
    return candidate_ids, dict(graph_scores), centrality_scores


def load_vector_index(index_dir: Path) -> tuple[np.ndarray, list[str], dict[str, Any], dict[str, Any]]:
    matrix_path = index_dir / "embeddings.npy"
    ids_path = index_dir / "ids.json"
    meta_path = index_dir / "index_meta.json"
    query_cfg_path = index_dir / "query_embedding_config.json"

    if not matrix_path.exists() or not ids_path.exists() or not meta_path.exists():
        raise RuntimeError(f"Vector index not found in {index_dir}")

    matrix = np.load(matrix_path)
    ids: list[str] = json.loads(ids_path.read_text(encoding="utf-8"))
    meta = read_json(meta_path, default={}) or {}
    query_cfg = read_json(query_cfg_path, default={}) or {}
    if matrix.shape[0] != len(ids):
        raise RuntimeError("Index mismatch: embeddings row count != ids length")
    return matrix, ids, meta, query_cfg


def make_query_embedder(
    provider: str,
    model: str,
    dim: int,
    batch_size: int,
    openai_base_url: str,
    openai_api_key: str | None,
    openai_timeout_seconds: int,
    local_device: str,
):
    return make_embedder(
        provider=provider,
        model=model,
        dim=dim,
        batch_size=batch_size,
        openai_base_url=openai_base_url,
        openai_api_key=openai_api_key,
        openai_timeout_seconds=openai_timeout_seconds,
        local_device=local_device,
    )


def bm25_candidates(
    lexical_db: Path,
    query: str,
    limit: int,
    chapter_filter: str,
    env_filter: str,
) -> dict[str, float]:
    fts_query = tokenize_for_fts(query)
    if not fts_query or not lexical_db.exists():
        return {}

    conn = sqlite3.connect(str(lexical_db))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT id, chapter_key, env_type, bm25(docs_fts) AS rank
        FROM docs_fts
        WHERE docs_fts MATCH ?
        ORDER BY rank ASC
        LIMIT ?
        """,
        (fts_query, max(limit * 4, limit)),
    ).fetchall()
    conn.close()

    out: dict[str, float] = {}
    for row in rows:
        doc_id = str(row["id"])
        chapter_ok = not chapter_filter or str(row["chapter_key"]) == chapter_filter
        env_ok = not env_filter or str(row["env_type"]) == env_filter
        if not chapter_ok or not env_ok:
            continue
        rank = float(row["rank"])
        out[doc_id] = -rank
        if len(out) >= limit:
            break
    return out


def vector_candidates(
    matrix: np.ndarray,
    ids: list[str],
    query_vec: np.ndarray,
    limit: int,
    corpus: dict[str, dict[str, Any]],
    chapter_filter: str,
    env_filter: str,
) -> dict[str, float]:
    scores = matrix @ query_vec
    order = np.argsort(-scores)
    out: dict[str, float] = {}
    for idx in order:
        doc_id = ids[int(idx)]
        row = corpus.get(doc_id)
        if not row:
            continue
        chapter_ok = not chapter_filter or row.get("chapter_key", "") == chapter_filter
        env_ok = not env_filter or row.get("env_type", "") == env_filter
        if not chapter_ok or not env_ok:
            continue
        out[doc_id] = float(scores[int(idx)])
        if len(out) >= limit:
            break
    return out


def resolve_query_embedding_params(
    index_meta: dict[str, Any],
    query_cfg: dict[str, Any],
    provider_override: str,
    model_override: str,
    dim_override: int,
    openai_base_url_override: str,
    openai_timeout_override: int,
    local_device_override: str,
) -> dict[str, Any]:
    provider = provider_override or str(query_cfg.get("provider", index_meta.get("provider", "hash")))
    model = model_override or str(query_cfg.get("model", index_meta.get("model", "hash-embedding-v1")))
    dim = dim_override if dim_override > 0 else int(query_cfg.get("dim", index_meta.get("dim", 1536)))
    openai_base_url = openai_base_url_override or str(query_cfg.get("openai_base_url", "https://api.openai.com/v1"))
    openai_timeout_seconds = (
        openai_timeout_override
        if openai_timeout_override > 0
        else int(query_cfg.get("openai_timeout_seconds", 60))
    )
    local_device = local_device_override or str(query_cfg.get("local_device", "cpu"))
    batch_size = int(query_cfg.get("batch_size", 64))
    return {
        "provider": provider,
        "model": model,
        "dim": dim,
        "batch_size": batch_size,
        "openai_base_url": openai_base_url,
        "openai_timeout_seconds": openai_timeout_seconds,
        "local_device": local_device,
    }


def hybrid_search(
    query: str,
    matrix: np.ndarray,
    ids: list[str],
    corpus: dict[str, dict[str, Any]],
    lexical_db: Path,
    embedder,
    vector_k: int,
    bm25_k: int,
    vector_weight: float,
    bm25_weight: float,
    chapter_filter: str,
    env_filter: str,
    graph_seed_k: int = 20,
    graph_hops: int = 2,
    graph_expand_k: int = 80,
    graph_weight: float = 0.35,
    graph_outgoing_weight: float = 1.0,
    graph_incoming_weight: float = 0.65,
    graph_hop_decay: float = 0.55,
    graph_centrality_weight: float = 0.10,
    statement_route_weight: float = 1.0,
    proof_route_weight: float = 1.0,
    statement_route_bonus: float = 0.12,
    proof_route_bonus: float = 0.45,
    proof_route_fallback_bonus: float = 0.10,
    nonproof_proof_penalty: float = 0.08,
) -> list[tuple[str, float, float, float]]:
    expanded_query = expand_query_for_retrieval(query)
    query_vec = embedder.encode([expanded_query])[0]
    if matrix.shape[1] != query_vec.shape[0]:
        raise RuntimeError(
            f"Dimension mismatch: index dim={matrix.shape[1]} query dim={query_vec.shape[0]}"
        )

    chapter_keys = {
        str(row.get("chapter_key", ""))
        for row in corpus.values()
        if str(row.get("chapter_key", ""))
    }
    intent = detect_query_intent(query=query, chapter_keys=chapter_keys)

    vec_scores = vector_candidates(
        matrix=matrix,
        ids=ids,
        query_vec=query_vec,
        limit=vector_k,
        corpus=corpus,
        chapter_filter=chapter_filter,
        env_filter=env_filter,
    )
    bm25_scores = bm25_candidates(
        lexical_db=lexical_db,
        query=expanded_query,
        limit=bm25_k,
        chapter_filter=chapter_filter,
        env_filter=env_filter,
    )
    vec_norm = minmax_normalize(vec_scores)
    bm_norm = minmax_normalize(bm25_scores)

    candidate_ids = set(vec_norm.keys()) | set(bm_norm.keys())

    # Exact tag direct-hit: always seed candidate set when corpus + filters allow it.
    if intent["tag_hint"]:
        tag = str(intent["tag_hint"])
        row = corpus.get(tag)
        if row:
            chapter_ok = not chapter_filter or row.get("chapter_key", "") == chapter_filter
            env_ok = not env_filter or row.get("env_type", "") == env_filter
            if chapter_ok and env_ok:
                candidate_ids.add(tag)

    if not candidate_ids:
        return []

    query_tokens = set(tokenize(expanded_query))

    base_scores: dict[str, float] = {}
    for doc_id in candidate_ids:
        row = corpus.get(doc_id, {})
        vs = vec_norm.get(doc_id, 0.0)
        bs = bm_norm.get(doc_id, 0.0)
        score = vector_weight * vs + bm25_weight * bs
        score += compute_intent_boost(
            doc_id=doc_id,
            row=row,
            intent=intent,
            query_tokens=query_tokens,
            statement_route_weight=statement_route_weight,
            proof_route_weight=proof_route_weight,
            statement_route_bonus=statement_route_bonus,
            proof_route_bonus=proof_route_bonus,
            proof_route_fallback_bonus=proof_route_fallback_bonus,
            nonproof_proof_penalty=nonproof_proof_penalty,
        )
        base_scores[doc_id] = score

    graph_norm: dict[str, float] = {}
    centrality_norm: dict[str, float] = {}
    if graph_weight > 0.0 and graph_hops > 0 and graph_expand_k > 0:
        expanded_candidates, graph_scores, centrality_scores = graphrag_expand_scores(
            base_scores=base_scores,
            corpus=corpus,
            intent=intent,
            chapter_filter=chapter_filter,
            env_filter=env_filter,
            seed_k=graph_seed_k,
            hops=graph_hops,
            expand_k=graph_expand_k,
            outgoing_weight=graph_outgoing_weight,
            incoming_weight=graph_incoming_weight,
            hop_decay=graph_hop_decay,
        )
        candidate_ids |= expanded_candidates
        graph_norm = minmax_normalize(graph_scores)
        if graph_centrality_weight > 0.0:
            centrality_norm = minmax_normalize(centrality_scores)

    hybrid: list[tuple[str, float, float, float]] = []
    for doc_id in candidate_ids:
        row = corpus.get(doc_id, {})
        vs = vec_norm.get(doc_id, 0.0)
        bs = bm_norm.get(doc_id, 0.0)
        score = vector_weight * vs + bm25_weight * bs
        score += compute_intent_boost(
            doc_id=doc_id,
            row=row,
            intent=intent,
            query_tokens=query_tokens,
            statement_route_weight=statement_route_weight,
            proof_route_weight=proof_route_weight,
            statement_route_bonus=statement_route_bonus,
            proof_route_bonus=proof_route_bonus,
            proof_route_fallback_bonus=proof_route_fallback_bonus,
            nonproof_proof_penalty=nonproof_proof_penalty,
        )
        score += graph_weight * graph_norm.get(doc_id, 0.0)
        score += graph_centrality_weight * centrality_norm.get(doc_id, 0.0)
        hybrid.append((doc_id, score, vs, bs))

    hybrid.sort(key=lambda x: x[1], reverse=True)
    return hybrid
