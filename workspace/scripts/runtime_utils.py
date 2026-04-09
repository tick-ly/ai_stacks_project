from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "YAML config requires PyYAML. Install with: pip install pyyaml"
        ) from exc
    parsed = yaml.safe_load(path.read_text(encoding="utf-8", errors="replace"))
    if parsed is None:
        return {}
    if not isinstance(parsed, dict):
        raise RuntimeError(f"Config must be an object/map: {path}")
    return parsed


def load_config(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    if not path.exists():
        raise RuntimeError(f"Config file not found: {path}")
    suffix = path.suffix.lower()
    if suffix == ".json":
        parsed = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        if not isinstance(parsed, dict):
            raise RuntimeError(f"JSON config must be an object/map: {path}")
        return parsed
    if suffix in {".yaml", ".yml"}:
        return _load_yaml(path)
    raise RuntimeError(f"Unsupported config extension: {suffix}. Use .json/.yaml/.yml")


def get_section_config(config: dict[str, Any], section: str) -> dict[str, Any]:
    if not config:
        return {}
    value = config.get(section)
    if isinstance(value, dict):
        return value
    # Fallback: allow flat config without sections.
    return config


def prefetch_config(section: str) -> tuple[Path | None, dict[str, Any]]:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--config", type=Path, default=None)
    ns, _ = parser.parse_known_args(sys.argv[1:])
    cfg = load_config(ns.config) if ns.config else {}
    section_cfg = get_section_config(cfg, section)
    return ns.config, section_cfg


def setup_logging(level: str = "INFO") -> None:
    log_level_name = (level or "INFO").upper()
    log_level = getattr(logging, log_level_name, logging.INFO)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

