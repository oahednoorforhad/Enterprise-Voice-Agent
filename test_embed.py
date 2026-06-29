"""Test available embedding models and their dimensions."""
import httpx, asyncio, os

KEY = os.environ["GOOGLE_API_KEY"]
BASE = "https://generativelanguage.googleapis.com/v1beta/models"

async def test_google():
    models = ["gemini-embedding-001", "gemini-embedding-2", "gemini-embedding-2-preview"]
    for m in models:
        for dim in [None, 768]:
            url = f"{BASE}/{m}:embedContent"
            body = {"model": f"models/{m}", "content": {"parts": [{"text": "hello"}]}}
            if dim:
                body["outputDimensionality"] = dim
            async with httpx.AsyncClient() as c:
                r = await c.post(url, params={"key": KEY}, json=body, timeout=15)
                d = r.json()
                if "embedding" in d:
                    actual = len(d["embedding"]["values"])
                    label = f"dim={actual}" if not dim else f"requested={dim}, actual={actual}"
                    print(f"  {m}: OK {label}")
                else:
                    err = d.get("error", {}).get("message", r.text)[:120]
                    print(f"  {m} (dim={dim}): FAIL {err}")

async def test_openrouter():
    key = os.environ["OPENROUTER_API_KEY"]
    models = [
        "nomic-ai/nomic-embed-text-v1.5",
        "text-embedding-3-small",
        "text-embedding-3-large",
    ]
    for m in models:
        async with httpx.AsyncClient() as c:
            r = await c.post(
                "https://openrouter.ai/api/v1/embeddings",
                headers={"Authorization": f"Bearer {key}"},
                json={"model": m, "input": "hello"},
                timeout=15,
            )
            d = r.json()
            if "data" in d and len(d["data"]) > 0:
                actual = len(d["data"][0]["embedding"])
                print(f"  {m}: OK dim={actual}")
            else:
                err = d.get("error", {}).get("message", r.text)[:120]
                print(f"  {m}: FAIL {err}")

async def main():
    print("=== Google ===")
    await test_google()
    print("\n=== OpenRouter ===")
    await test_openrouter()

asyncio.run(main())
