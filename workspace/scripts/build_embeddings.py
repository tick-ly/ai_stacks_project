from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import numpy as np

from common import parse_changed_tags_file, read_jsonl, write_json
from embeddings_providers import make_embedder
from runtime_utils import prefetch_config, setup_logging


LOGGER = logging.getLogger("build_embeddings")


def parse_args() -> argparse.Namespace:
    config_path, cfg = prefetch_config("build_embeddings")
    parser = argparse.ArgumentParser(
        description="Build vector index with pluggable embeddings and incremental updates."
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
        "--corpus",
        type=Path,
        default=Path(str(cfg.get("corpus", "data/processed/corpus.jsonl"))),
        help="Input corpus JSONL file.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(str(cfg.get("output_dir", "data/index"))),
        help="Output directory for embeddings index.",
    )
    parser.add_argument(
        "--provider",
        type=str,
        default=str(cfg.get("provider", "hash")),
        choices=["hash", "openai", "local"],
        help="Embedding provider: hash|openai|local(sentence-transformers).",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=str(cfg.get("model", "hash-embedding-v1")),
        help="Model name. For provider=hash this is metadata only.",
    )
    parser.add_argument(
        "--dim",
        type=int,
        default=int(cfg.get("dim", 1536)),
        help="Embedding dimension for hash/openai (optional for local).",
    )
    parser.add_argument(
        "--text-fields",
        type=str,
        default="statement_text,normalized_text",
        help="Comma-separated fields used to build embedding text.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=int(cfg.get("batch_size", 64)),
        help="Batch size for provider APIs/models.",
    )
    parser.add_argument(
        "--incremental",
        action="store_true",
        default=bool(cfg.get("incremental", False)),
        help="Only recompute vectors for changed/new docs when possible.",
    )
    parser.add_argument(
        "--changed-tags-file",
        type=Path,
        default=Path(str(cfg.get("changed_tags_file", "data/raw/api/changed_tags.json"))),
        help="Changed tags JSON used for incremental updates.",
    )
    parser.add_argument(
        "--openai-api-key",
        type=str,
        default=str(cfg.get("openai_api_key", "")),
        help="OpenAI API key (fallback env OPENAI_API_KEY).",
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
        help="OpenAI request timeout in seconds.",
    )
    parser.add_argument(
        "--local-device",
        type=str,
        default=str(cfg.get("local_device", "cpu")),
        help="Device for local embedding model, e.g. cpu/cuda.",
    )
    return parser.parse_args()


def build_text(row: dict[str, object], fields: list[str]) -> str:
    chunks = []
    for field in fields:
        value = row.get(field, "")
        if value:
            chunks.append(str(value))
    return "\n".join(chunks).strip()


def compat_meta(args: argparse.Namespace, fields: list[str]) -> dict[str, object]:
    expected_dim: int | None
    if args.provider in {"hash", "openai"}:
        expected_dim = args.dim
    else:
        expected_dim = None
    return {
        "provider": args.provider,
        "model": args.model,
        "dim": expected_dim,
        "text_fields": fields,
    }


def can_incremental_reuse(meta_path: Path, expected: dict[str, object]) -> bool:
    if not meta_path.exists():
        return False
    current = json.loads(meta_path.read_text(encoding="utf-8", errors="replace"))
    for key, value in expected.items():
        if value is None and key == "dim":
            # local providers can have model-dependent dim discovered at runtime.
            continue
        if current.get(key) != value:
            return False
    return True


def main() -> int:
    args = parse_args()
    setup_logging(args.log_level)
    rows = list(read_jsonl(args.corpus))
    if not rows:
        raise RuntimeError(f"No corpus rows found in {args.corpus}. Run build_corpus.py first.")

    fields = [x.strip() for x in args.text_fields.split(",") if x.strip()]
    if not fields:
        raise RuntimeError("--text-fields cannot be empty")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    ids_path = args.output_dir / "ids.json"
    emb_path = args.output_dir / "embeddings.npy"
    meta_path = args.output_dir / "index_meta.json"
    hash_path = args.output_dir / "doc_hashes.json"
    query_cfg_path = args.output_dir / "query_embedding_config.json"

    by_id: dict[str, dict[str, object]] = {}
    for row in rows:
        doc_id = str(row.get("id", "")).strip()
        if doc_id:
            by_id[doc_id] = row

    target_ids = sorted(by_id.keys())
    changed_tags = parse_changed_tags_file(args.changed_tags_file)
    expected_meta = compat_meta(args, fields)

    embedder = make_embedder(
        provider=args.provider,
        model=args.model,
        dim=args.dim,
        batch_size=args.batch_size,
        openai_base_url=args.openai_base_url,
        openai_api_key=args.openai_api_key or None,
        openai_timeout_seconds=args.openai_timeout_seconds,
        local_device=args.local_device,
    )

    doc_hashes = {
        doc_id: str(by_id[doc_id].get("content_hash", "")) for doc_id in target_ids
    }

    old_ids: list[str] = []
    old_matrix = np.zeros((0, 0), dtype=np.float32)
    old_hashes: dict[str, str] = {}
    reusable = False
    if args.incremental and ids_path.exists() and emb_path.exists():
        reusable = can_incremental_reuse(meta_path, expected_meta)
        if reusable:
            old_ids = json.loads(ids_path.read_text(encoding="utf-8"))
            old_matrix = np.load(emb_path)
            old_hashes = json.loads(hash_path.read_text(encoding="utf-8")) if hash_path.exists() else {}
            if old_matrix.shape[0] != len(old_ids):
                reusable = False

    id_to_old_idx = {doc_id: i for i, doc_id in enumerate(old_ids)} if reusable else {}
    embed_ids: list[str] = []
    embed_texts: list[str] = []
    if reusable:
        # Keep previous vectors when doc hash unchanged and not explicitly changed.
        for doc_id in target_ids:
            old_i = id_to_old_idx.get(doc_id)
            new_hash = doc_hashes.get(doc_id, "")
            old_hash = old_hashes.get(doc_id, "")
            changed_by_hash = old_hash != new_hash
            changed_by_tag = bool(changed_tags and doc_id in changed_tags)
            if old_i is not None and not changed_by_hash and not changed_by_tag:
                pass
            else:
                embed_ids.append(doc_id)
                embed_texts.append(build_text(by_id[doc_id], fields))
    else:
        for doc_id in target_ids:
            embed_ids.append(doc_id)
            embed_texts.append(build_text(by_id[doc_id], fields))

    embedded_map: dict[str, np.ndarray] = {}
    if embed_ids:
        LOGGER.info("Computing vectors for %d docs", len(embed_ids))
        encoded = embedder.encode(embed_texts)
        for i, doc_id in enumerate(embed_ids):
            embedded_map[doc_id] = encoded[i]

    if reusable:
        dim = old_matrix.shape[1]
        if embed_ids:
            dim = int(next(iter(embedded_map.values())).shape[0])
        matrix = np.zeros((len(target_ids), dim), dtype=np.float32)
        for i, doc_id in enumerate(target_ids):
            if doc_id in embedded_map:
                matrix[i] = embedded_map[doc_id]
            else:
                old_i = id_to_old_idx[doc_id]
                matrix[i] = old_matrix[old_i]
    else:
        if not embed_ids:
            raise RuntimeError("No documents to embed.")
        dim = int(next(iter(embedded_map.values())).shape[0])
        matrix = np.zeros((len(target_ids), dim), dtype=np.float32)
        for i, doc_id in enumerate(target_ids):
            matrix[i] = embedded_map[doc_id]

    np.save(emb_path, matrix)
    write_json(ids_path, target_ids)
    write_json(hash_path, doc_hashes)

    final_meta = {
        "provider": args.provider,
        "model": args.model,
        "dim": int(matrix.shape[1]),
        "count": int(matrix.shape[0]),
        "text_fields": fields,
        "source_corpus": str(args.corpus),
        "incremental": bool(args.incremental),
    }
    write_json(meta_path, final_meta)

    query_cfg = {
        "provider": args.provider,
        "model": args.model,
        "dim": int(matrix.shape[1]),
        "batch_size": args.batch_size,
        "openai_base_url": args.openai_base_url,
        "openai_timeout_seconds": args.openai_timeout_seconds,
        "local_device": args.local_device,
    }
    write_json(query_cfg_path, query_cfg)

    LOGGER.info(
        "Wrote matrix shape=%s -> %s (reused=%s recomputed=%d)",
        matrix.shape,
        args.output_dir,
        reusable,
        len(embed_ids),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
