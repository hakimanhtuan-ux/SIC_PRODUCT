import asyncio
import hashlib
import logging
import math
from typing import Optional, Type, TypeVar
import httpx
from pydantic import BaseModel

from app.core.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class GeminiEngineClient:
    """
    Unified Google GenAI (`google-genai`) wrapper supporting:
    1. Structured JSON Pydantic outputs (`response_schema`)
    2. Semantic Embeddings (`gemini-embedding-001` compressed to 768 dimensions)
    3. Graceful fallback signaling when API key is not yet configured.
    """

    def __init__(self) -> None:
        self._client = None

    def _get_client(self):
        if not settings.has_gemini_key:
            return None
        from google import genai

        return genai.Client(api_key=settings.GEMINI_API_KEY)

    def _get_fallback_google_client(self):
        if settings.has_factcheck_key and settings.GOOGLE_FACTCHECK_API_KEY.startswith("AIza"):
            from google import genai

            return genai.Client(api_key=settings.GOOGLE_FACTCHECK_API_KEY)
        return None

    @property
    def is_live(self) -> bool:
        return settings.has_gemini_key or settings.OLLAMA_ENABLED

    async def _generate_via_ollama(
        self,
        system_instruction: str,
        prompt: str,
        schema: Type[T],
        temperature: float = 0.1,
    ) -> Optional[T]:
        url = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/chat"
        payload = {
            "model": settings.OLLAMA_MODEL,
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt},
            ],
            "format": schema.model_json_schema(),
            "options": {"temperature": temperature},
            "stream": False,
        }
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                content = (resp.json().get("message") or {}).get("content", "")
                if content:
                    return schema.model_validate_json(content)
        except Exception as exc:
            logger.warning("Local Ollama generation failed: %s", exc)
        return None

    async def generate_structured(
        self,
        system_instruction: str,
        prompt: str,
        schema: Type[T],
        temperature: float = 0.1,
    ) -> Optional[T]:
        client = self._get_client()
        if client is not None:
            from google.genai import types

            models_to_try = [
                settings.GEMINI_MODEL,
                "gemini-3.8-flash-lite",
                "gemini-2.5-flash",
            ]
            seen_models: set[str] = set()
            for model_name in models_to_try:
                if not model_name or model_name in seen_models:
                    continue
                seen_models.add(model_name)

                def _call(m=model_name):
                    response = client.models.generate_content(
                        model=m,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            system_instruction=system_instruction,
                            response_mime_type="application/json",
                            response_schema=schema,
                            temperature=temperature,
                        ),
                    )
                    if getattr(response, "parsed", None) is not None:
                        return response.parsed
                    if response.text:
                        return schema.model_validate_json(response.text)
                    return None

                try:
                    res = await asyncio.to_thread(_call)
                    if res is not None:
                        return res
                except Exception as exc:
                    logger.warning("Gemini model '%s' warning (%s), trying next fallback model...", model_name, exc)
                    await asyncio.sleep(0.6)

        if settings.OLLAMA_ENABLED:
            return await self._generate_via_ollama(
                system_instruction=system_instruction,
                prompt=prompt,
                schema=schema,
                temperature=temperature,
            )
        return None

    async def embed_text(self, text: str) -> list[float]:
        """Generates a normalized 768-dim embedding vector via Gemini or deterministic fallback."""
        client = self._get_client()
        dim = settings.GEMINI_EMBEDDING_DIM

        if client is not None:
            from google.genai import types

            def _embed():
                resp = client.models.embed_content(
                    model=settings.GEMINI_EMBEDDING_MODEL,
                    contents=text,
                    config=types.EmbedContentConfig(output_dimensionality=dim),
                )
                vals = list(resp.embeddings[0].values)
                norm = math.sqrt(sum(v * v for v in vals)) or 1.0
                return [v / norm for v in vals]

            try:
                return await asyncio.to_thread(_embed)
            except Exception as exc:
                logger.warning("Gemini embedding failed (%s); using deterministic hash vector.", exc)

        # Deterministic normalized n-gram hash vector for local demo/testing mode
        vec = [0.0] * dim
        tokens = [tok.strip().lower() for tok in text.split() if tok.strip()]
        for i, tok in enumerate(tokens):
            grams = [tok]
            if i + 1 < len(tokens):
                grams.append(f"{tok}_{tokens[i + 1]}")
            for g in grams:
                digest = hashlib.sha256(g.encode("utf-8")).digest()
                idx = int.from_bytes(digest[:4], "big") % dim
                sign = 1.0 if (digest[4] % 2 == 0) else -1.0
                vec[idx] += sign
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]


gemini_client = GeminiEngineClient()

