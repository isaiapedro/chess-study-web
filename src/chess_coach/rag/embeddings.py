from __future__ import annotations

from typing import Sequence

import httpx


class OllamaEmbedder:
    def __init__(self, host: str, model: str) -> None:
        self.host = host.rstrip("/")
        self.model = model

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        with httpx.Client(timeout=300.0) as client:
            response = client.post(
                f"{self.host}/api/embed",
                json={"model": self.model, "input": list(texts)},
            )
            if response.status_code == 404:
                return self._embed_legacy(client, texts)
            response.raise_for_status()
            payload = response.json()
            embeddings = payload.get("embeddings")
            if embeddings and len(embeddings) == len(texts):
                return embeddings
            return self._embed_legacy(client, texts)

    def _embed_legacy(self, client: httpx.Client, texts: Sequence[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            response = client.post(
                f"{self.host}/api/embeddings",
                json={"model": self.model, "prompt": text},
            )
            response.raise_for_status()
            payload = response.json()
            embedding = payload.get("embedding")
            if not embedding:
                raise RuntimeError(f"No embedding returned for model {self.model}")
            vectors.append(embedding)
        return vectors


class HashEmbedder:
    """Deterministic offline fallback when Ollama embeddings are unavailable."""

    def __init__(self, dims: int = 384) -> None:
        self.dims = dims

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            vec = [0.0] * self.dims
            tokens = text.lower().split()
            if not tokens:
                vectors.append(vec)
                continue
            for token in tokens:
                h = hash(token)
                idx = h % self.dims
                sign = 1.0 if (h & 1) == 0 else -1.0
                vec[idx] += sign
            norm = sum(v * v for v in vec) ** 0.5 or 1.0
            vectors.append([v / norm for v in vec])
        return vectors


def get_embedder(host: str, model: str, allow_fallback: bool = True):
    embedder = OllamaEmbedder(host, model)
    try:
        embedder.embed(["ping"])
        return embedder
    except Exception:
        if not allow_fallback:
            raise
        return HashEmbedder()
