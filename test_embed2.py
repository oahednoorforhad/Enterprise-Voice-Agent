"""Check OpenRouter embedding model pricing."""
import httpx, asyncio, os

KEY = os.environ["OPENROUTER_API_KEY"]

async def main():
    async with httpx.AsyncClient() as c:
        r = await c.get(
            "https://openrouter.ai/api/v1/models",
            headers={"Authorization": f"Bearer {KEY}"},
            timeout=15,
        )
        models = r.json().get("data", [])
        for m in models:
            pid = m.get("id", "")
            if any(x in pid.lower() for x in ["embed", "ada", "nomic", "mini", "bge", "gte"]):
                pricing = m.get("pricing", {})
                pp = pricing.get("prompt", "?")
                print(f"  {pid}  prompt=${pp}/token")

asyncio.run(main())
