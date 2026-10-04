import asyncio
import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.models  # noqa: E402, F401
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.models import Customer  # noqa: E402
from app.services import analytics, followup_engine, ingest  # noqa: E402
from app.services.state_machine import build_transition_event  # noqa: E402
from app.utils.clock import utcnow  # noqa: E402

STORIES = [
    ("王女士", "朋友介绍", [
        "老师您好，孩子现在初二，数学大概80分，希望提高到100分，周末有时间，预算150一节。",
        "预算可以给到180，想快点开始，什么时候能试听？",
    ], ["contacted", "qualified", "trial"]),
    ("张先生", "抖音", [
        "孩子初三，英语100分左右，想提到110，每次200可以吗？",
    ], ["contacted", "qualified"]),
    ("刘女士", "家长群", [
        "你好，想找数学老师，孩子高一",
    ], ["contacted"]),
    ("陈先生", "转介绍", [
        "高二物理，现在65分，希望冲到85，周末上课，预算250。",
        "先再考虑一下吧",
    ], ["contacted", "lost"]),
    ("赵女士", "小红书", [
        "孩子初一，数学基础差，想补基础，周末可以",
    ], []),
]


async def main() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as db:
        for name, source, messages, path in STORIES:
            customer = Customer(name=name, source=source)
            db.add(customer)
            await db.commit()

            occurred = utcnow() - timedelta(days=len(messages) + 2)
            for message in messages:
                await ingest.ingest_conversation(db, customer, message, direction="in", occurred_at=occurred)
                occurred += timedelta(days=1)

            lead = await ingest.get_or_create_lead(db, customer.id)
            for stage in path:
                if lead.stage != stage:
                    db.add(build_transition_event(lead, stage, reason="seed 演示推进"))
                    await db.commit()

        created = await followup_engine.generate_daily_followups(db)
        summary = await analytics.summary(db)
        print("generated followups:")
        for item in created:
            print(f"  lead#{item.lead_id} score={item.score} reason={item.reason}")
        print("funnel:", summary["stage_counts"])
        print("win_rate:", summary["win_rate"], "avg_budget:", summary["avg_budget"])

    await engine.dispose()
    print("seed done -> tutorflow.db")


if __name__ == "__main__":
    asyncio.run(main())
