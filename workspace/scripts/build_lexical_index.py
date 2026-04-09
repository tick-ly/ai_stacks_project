from __future__ import annotations

import argparse
import logging
import sqlite3
from pathlib import Path

from common import parse_changed_tags_file, read_jsonl
from runtime_utils import prefetch_config, setup_logging


SCHEMA_SQL = """
CREATE VIRTUAL TABLE IF NOT EXISTS docs_fts USING fts5(
    id UNINDEXED,
    chapter_key UNINDEXED,
    env_type UNINDEXED,
    reference UNINDEXED,
    title,
    content,
    content_hash UNINDEXED,
    tokenize = 'unicode61 remove_diacritics 2'
);
"""
LOGGER = logging.getLogger("build_lexical_index")


def parse_args() -> argparse.Namespace:
    config_path, cfg = prefetch_config("build_lexical_index")
    parser = argparse.ArgumentParser(
        description="Build SQLite FTS5 lexical index for BM25 retrieval (supports incremental upsert)."
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
        help="Corpus JSONL file.",
    )
    parser.add_argument(
        "--output-db",
        type=Path,
        default=Path(str(cfg.get("output_db", "data/index/lexical.db"))),
        help="Output SQLite database path.",
    )
    parser.add_argument(
        "--incremental",
        action="store_true",
        default=bool(cfg.get("incremental", False)),
        help="Incrementally upsert changed tags when possible.",
    )
    parser.add_argument(
        "--changed-tags-file",
        type=Path,
        default=Path(str(cfg.get("changed_tags_file", "data/raw/api/changed_tags.json"))),
        help="Changed tags JSON used in incremental mode.",
    )
    parser.add_argument(
        "--prune-missing",
        action="store_true",
        default=bool(cfg.get("prune_missing", False)),
        help="Remove docs from lexical index if they no longer exist in corpus.",
    )
    return parser.parse_args()


def doc_content(row: dict[str, object]) -> str:
    chunks = [
        str(row.get("title", "")),
        str(row.get("statement_text", "")),
        str(row.get("proof_text", "")),
        str(row.get("normalized_text", "")),
    ]
    return "\n".join(x for x in chunks if x).strip()


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(SCHEMA_SQL)
    conn.commit()


def delete_by_id(conn: sqlite3.Connection, doc_id: str) -> None:
    conn.execute("DELETE FROM docs_fts WHERE id = ?", (doc_id,))


def upsert_doc(conn: sqlite3.Connection, row: dict[str, object]) -> None:
    doc_id = str(row.get("id", ""))
    delete_by_id(conn, doc_id)
    conn.execute(
        """
        INSERT INTO docs_fts (
            id, chapter_key, env_type, reference, title, content, content_hash
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            doc_id,
            str(row.get("chapter_key", "")),
            str(row.get("env_type", "")),
            str(row.get("reference", "")),
            str(row.get("title", "")),
            doc_content(row),
            str(row.get("content_hash", "")),
        ),
    )


def existing_ids(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT id FROM docs_fts").fetchall()
    return {str(r[0]) for r in rows}


def main() -> int:
    args = parse_args()
    setup_logging(args.log_level)
    args.output_db.parent.mkdir(parents=True, exist_ok=True)
    rows = {row["id"]: row for row in read_jsonl(args.corpus) if row.get("id")}
    corpus_ids = set(rows.keys())

    conn = sqlite3.connect(str(args.output_db))
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    ensure_schema(conn)

    changed_tags = parse_changed_tags_file(args.changed_tags_file)
    wrote = 0
    deleted = 0

    if args.incremental:
        if changed_tags:
            for tag in sorted(changed_tags):
                row = rows.get(tag)
                if row is None:
                    delete_by_id(conn, tag)
                    deleted += 1
                else:
                    upsert_doc(conn, row)
                    wrote += 1
        else:
            LOGGER.info("Incremental mode with no changed tags; no upserts.")
    else:
        conn.execute("DELETE FROM docs_fts")
        for tag in sorted(corpus_ids):
            upsert_doc(conn, rows[tag])
            wrote += 1

    if args.prune_missing:
        current_ids = existing_ids(conn)
        to_delete = sorted(current_ids - corpus_ids)
        for doc_id in to_delete:
            delete_by_id(conn, doc_id)
            deleted += 1

    conn.commit()
    count = conn.execute("SELECT COUNT(*) FROM docs_fts").fetchone()[0]
    conn.close()

    LOGGER.info(
        "db=%s rows=%d upserted=%d deleted=%d mode=%s",
        args.output_db,
        count,
        wrote,
        deleted,
        "incremental" if args.incremental else "full",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
