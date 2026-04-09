from __future__ import annotations

import hashlib
import json
import re
import tempfile
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence


DEFAULT_USER_AGENT = (
    "stacks-project-vectorizer/0.1 "
    "(research script skeleton; contact: stacks.project@gmail.com)"
)

TAG_REF_RE = re.compile(r"/tag/([0-9A-Z]{4})")
TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")


class _HTMLToText(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"p", "div", "li", "br", "h1", "h2", "h3", "h4", "h5", "h6", "tr"}:
            self._chunks.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"p", "div", "li", "br", "h1", "h2", "h3", "h4", "h5", "h6", "tr"}:
            self._chunks.append("\n")

    def handle_data(self, data: str) -> None:
        if data:
            self._chunks.append(data)

    def text(self) -> str:
        raw = "".join(self._chunks)
        raw = re.sub(r"[ \t\f\v]+", " ", raw)
        raw = re.sub(r"\n\s*\n+", "\n\n", raw)
        return raw.strip()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def atomic_write_text(path: Path, text: str, encoding: str = "utf-8") -> None:
    ensure_dir(path.parent)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding=encoding,
        newline="\n",
        delete=False,
        dir=str(path.parent),
    ) as fh:
        fh.write(text)
        temp_name = fh.name
    Path(temp_name).replace(path)


def read_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    ensure_dir(path.parent)
    count = 0
    chunks: list[str] = []
    for row in rows:
        chunks.append(json.dumps(row, ensure_ascii=False))
        count += 1
    atomic_write_text(path, "\n".join(chunks) + ("\n" if chunks else ""))
    return count


def parse_tags_file(path: Path) -> dict[str, str]:
    mapping: dict[str, str] = {}
    with path.open("r", encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#") or "," not in line:
                continue
            tag, full_label = line.split(",", 1)
            tag = tag.strip()
            full_label = full_label.strip()
            if not tag or not full_label:
                continue
            mapping[tag] = full_label
    return mapping


def download_text(
    url: str,
    timeout: int = 30,
    retries: int = 3,
    sleep_seconds: float = 0.5,
    user_agent: str = DEFAULT_USER_AGENT,
) -> str:
    last_error: Exception | None = None
    req = urllib.request.Request(url, headers={"User-Agent": user_agent})
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read()
            return body.decode("utf-8", errors="replace")
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(sleep_seconds * attempt)
    assert last_error is not None
    raise RuntimeError(f"Failed to download {url}: {last_error}") from last_error


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8", errors="replace"))


def write_json(path: Path, payload: Any, indent: int = 2) -> None:
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=indent) + "\n")


def html_to_text(html_text: str) -> str:
    parser = _HTMLToText()
    parser.feed(html_text)
    parser.close()
    return parser.text()


def normalize_math_text(text: str) -> str:
    normalized = text
    replacements = [
        (r"\\mathcal\{([A-Za-z])\}", r"\1"),
        (r"\\mathbf\{([A-Za-z])\}", r"\1"),
        (r"\\to", " to "),
        (r"\\mapsto", " mapsto "),
        (r"\\Spec", " Spec "),
        (r"\\Hom", " Hom "),
    ]
    for pattern, repl in replacements:
        normalized = re.sub(pattern, repl, normalized)

    normalized = normalized.replace("$", " ")
    normalized = normalized.replace("{", " ")
    normalized = normalized.replace("}", " ")
    normalized = normalized.replace("^", " ")
    normalized = normalized.replace("_", " ")
    normalized = re.sub(r"\\([A-Za-z]+)", r" \1 ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def extract_tag_refs(html_text: str) -> list[str]:
    seen: set[str] = set()
    refs: list[str] = []
    for tag in TAG_REF_RE.findall(html_text):
        if tag not in seen:
            seen.add(tag)
            refs.append(tag)
    return refs


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def chunked(seq: Sequence[Any], size: int) -> Iterator[Sequence[Any]]:
    if size <= 0:
        raise ValueError("size must be > 0")
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


def hash_embedding(text: str, dim: int = 1536) -> list[float]:
    vec = [0.0] * dim
    tokens = tokenize(text)
    if not tokens:
        return vec

    for tok in tokens:
        digest = hashlib.blake2b(tok.encode("utf-8"), digest_size=8).digest()
        value = int.from_bytes(digest, "little", signed=False)
        idx = value % dim
        sign = 1.0 if ((value >> 1) & 1) == 0 else -1.0
        vec[idx] += sign

    norm_sq = sum(v * v for v in vec)
    if norm_sq <= 0.0:
        return vec
    inv_norm = norm_sq ** -0.5
    return [v * inv_norm for v in vec]


def parse_changed_tags_file(path: Path | None) -> set[str]:
    if path is None or not path.exists():
        return set()
    raw = read_json(path, default=None)
    if raw is None:
        return set()
    if isinstance(raw, list):
        return {str(x) for x in raw}
    if isinstance(raw, dict):
        for key in ("changed_tags", "fetched_tags", "tags"):
            value = raw.get(key)
            if isinstance(value, list):
                return {str(x) for x in value}
    return set()
