import httpx

from app.config.settings import get_settings

settings = get_settings()


async def get_embedding(text: str) -> list[float]:
    """Get 768-dim embedding via Google gemini-embedding-2 (free).

    The model's native output is 3072-dim but we request 768 via the
    ``outputDimensionality`` parameter so results fit the existing
    PGVector schema (``embedding_dim=768``).

    NOTE: Changing the embedding model/dimension requires re-embedding
    all existing knowledge_documents rows via scripts/reindex_knowledge.py.
    """
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-embedding-2:embedContent"
    )
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            url,
            # Header, not ?key= — httpx logs request URLs at INFO
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": settings.google_api_key,
            },
            json={
                "model": "models/gemini-embedding-2",
                "content": {"parts": [{"text": text}]},
                "outputDimensionality": 768,
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["embedding"]["values"]
