from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import numpy as np

from common import read_json, read_jsonl, tokenize
from embeddings_providers import make_embedder


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


def load_corpus(corpus_path: Path) -> dict[str, dict[str, Any]]:
    return {row["id"]: row for row in read_jsonl(corpus_path) if row.get("id")}


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
) -> list[tuple[str, float, float, float]]:
    query_vec = embedder.encode([query])[0]
    if matrix.shape[1] != query_vec.shape[0]:
        raise RuntimeError(
            f"Dimension mismatch: index dim={matrix.shape[1]} query dim={query_vec.shape[0]}"
        )

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
        query=query,
        limit=bm25_k,
        chapter_filter=chapter_filter,
        env_filter=env_filter,
    )
    vec_norm = minmax_normalize(vec_scores)
    bm_norm = minmax_normalize(bm25_scores)

    candidate_ids = set(vec_norm.keys()) | set(bm_norm.keys())
    if not candidate_ids:
        return []

    tag_like = query.strip().upper()
    hybrid: list[tuple[str, float, float, float]] = []
    for doc_id in candidate_ids:
        vs = vec_norm.get(doc_id, 0.0)
        bs = bm_norm.get(doc_id, 0.0)
        score = vector_weight * vs + bm25_weight * bs
        if doc_id == tag_like:
            score += 1.0
        hybrid.append((doc_id, score, vs, bs))
    hybrid.sort(key=lambda x: x[1], reverse=True)
    return hybrid

