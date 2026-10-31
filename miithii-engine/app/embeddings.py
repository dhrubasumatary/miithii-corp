"""Embedding client — the only place that talks to the embeddings API.

text-embedding-004 outputs 768-dim vectors (matches chunks.embedding).
Batches requests (API limit 100); caller passes realistic batch sizes.
"""

import structlog
from google import genai

logger = structlog.get_logger(__name__)

_BATCH = 90


class GeminiEmbedder:
    EMBED_DIM = 768  # matches chunks.embedding (gemini-embedding-001, MRL-truncated)

    def __init__(self, api_key: str, model: str = "gemini-embedding-001"):
        self._client = genai.Client(api_key=api_key)
        self._model = model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(texts), _BATCH):
            batch = texts[i : i + _BATCH]
            result = await self._client.aio.models.embed_content(
                model=self._model,
                contents=batch,
                config={"output_dimensionality": self.EMBED_DIM},
            )
            out.extend(e.values for e in result.embeddings)
        logger.info("embedded", count=len(out), model=self._model)
        return out


class NullEmbedder:
    """No API key configured — ingestion will mark sources failed rather than lie."""

    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("embeddings not configured (GEMINI_API_KEY missing)")
