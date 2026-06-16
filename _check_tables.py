import asyncio, asyncpg

async def main():
    conn = await asyncpg.connect('postgresql://eva:eva@localhost:5433/eva')
    rows = await conn.fetch(
        "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"
    )
    print(f"Tables: {[r['table_name'] for r in rows]}")
    await conn.close()

asyncio.run(main())
