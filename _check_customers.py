import asyncio, asyncpg

async def main():
    conn = await asyncpg.connect('postgresql://eva:eva@localhost:5433/eva')
    rows = await conn.fetch('SELECT id, name, email FROM customers LIMIT 10')
    print(f"Found {len(rows)} customers")
    for r in rows:
        print(f'{str(r["id"])}  |  {r["name"]}  |  {r["email"]}')
    await conn.close()

asyncio.run(main())
