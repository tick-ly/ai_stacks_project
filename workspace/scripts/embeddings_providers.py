from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Protocol

import numpy as np

from common import chunked, hash_embedding


class Embedder(Protocol):
    provider: str
    model: str
    dim: int | None

    def encode(self, texts: list[str]) -> np.ndarray:
        ...


@dataclass
class HashEmbedder:
    dim: int
    model: str = "hash-embedding-v1"
    provider: str = "hash"

    def encode(self, texts: list[str]) -> np.ndarray:
        vectors = [hash_embedding(text, dim=self.dim) for text in texts]
        return np.asarray(vectors, dtype=np.float32)


@dataclass
class OpenAIEmbedder:
    model: str
    api_key: str
    dim: int | None = None
    base_url: str = "https://api.openai.com/v1"
    timeout_seconds: int = 60
    batch_size: int = 64
    max_retries: int = 4
    provider: str = "openai"

    def _encode_batch(self, texts: list[str]) -> list[list[float]]:
        payload: dict[str, object] = {"model": self.model, "input": texts}
        if self.dim is not None:
            payload["dimensions"] = self.dim
        body = json.dumps(payload).encode("utf-8")
        url = self.base_url.rstrip("/") + "/embeddings"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")

        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                    raw = resp.read().decode("utf-8", errors="replace")
                parsed = json.loads(raw)
                data = parsed.get("data")
                if not isinstance(data, list):
                    raise RuntimeError(f"Invalid embeddings response: {raw[:300]}")
                embeddings = [item["embedding"] for item in data]
                if len(embeddings) != len(texts):
                    raise RuntimeError(
                        f"Embedding count mismatch: got {len(embeddings)} expected {len(texts)}"
                    )
                return embeddings
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
                last_error = exc
                if attempt < self.max_retries:
                    time.sleep(min(2.0 * attempt, 8.0))
        assert last_error is not None
        raise RuntimeError(f"OpenAI embeddings request failed: {last_error}") from last_error

    def encode(self, texts: list[str]) -> np.ndarray:
        all_vectors: list[list[float]] = []
        for batch in chunked(texts, self.batch_size):
            all_vectors.extend(self._encode_batch(list(batch)))
        matrix = np.asarray(all_vectors, dtype=np.float32)
        if self.dim is None:
            self.dim = int(matrix.shape[1])
        return matrix


@dataclass
class SentenceTransformerEmbedder:
    model: str
    device: str = "cpu"
    normalize_embeddings: bool = True
    batch_size: int = 64
    dim: int | None = None
    provider: str = "local"

    def __post_init__(self) -> None:
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(
                "sentence-transformers is required for provider=local. "
                "Install with: pip install sentence-transformers"
            ) from exc
        self._model = SentenceTransformer(self.model, device=self.device)

    def encode(self, texts: list[str]) -> np.ndarray:
        vectors = self._model.encode(
            texts,
            batch_size=self.batch_size,
            convert_to_numpy=True,
            normalize_embeddings=self.normalize_embeddings,
            show_progress_bar=False,
        )
        matrix = np.asarray(vectors, dtype=np.float32)
        if self.dim is None:
            self.dim = int(matrix.shape[1])
        return matrix


def make_embedder(
    provider: str,
    model: str,
    dim: int | None,
    batch_size: int,
    openai_base_url: str,
    openai_api_key: str | None,
    openai_timeout_seconds: int,
    local_device: str,
) -> Embedder:
    if provider == "hash":
        if dim is None:
            raise ValueError("provider=hash requires --dim")
        return HashEmbedder(dim=dim, model=model or "hash-embedding-v1")

    if provider == "openai":
        api_key = openai_api_key or os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is missing. Set env var or pass --openai-api-key."
            )
        return OpenAIEmbedder(
            model=model,
            api_key=api_key,
            dim=dim,
            base_url=openai_base_url,
            timeout_seconds=openai_timeout_seconds,
            batch_size=batch_size,
        )

    if provider == "local":
        return SentenceTransformerEmbedder(
            model=model,
            device=local_device,
            batch_size=batch_size,
        )

    raise ValueError(f"Unsupported provider: {provider}")

