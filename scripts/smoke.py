import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from httpx import ASGITransport, AsyncClient  # noqa: E402


async def main() -> int:
    from main import app

    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://smoke") as client:
            health = (await client.get("/healthz")).json()
            root = (await client.get("/")).json()
            leads = await client.get("/leads")
            followups = await client.get("/followups")
            analytics = await client.get("/analytics/summary")
            assert health == {"status": "ok"}
            assert root["app"] == "TutorFlow"
            assert leads.status_code == 200
            assert followups.status_code == 200
            assert analytics.status_code == 200
    print("smoke ok: healthz/root/leads/followups/analytics all reachable, tables created")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
