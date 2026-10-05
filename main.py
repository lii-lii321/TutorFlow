from contextlib import asynccontextmanager

import app.models  # noqa: F401  (register ORM metadata before create_all)
from app.config import settings
from app.database import Base, engine
from app.routers import analytics, customers, followups, leads
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


@asynccontextmanager
async def lifespan(_: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(title=settings.app_name, version="0.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(customers.router)
app.include_router(leads.router)
app.include_router(followups.router)
app.include_router(analytics.router)


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.get("/")
async def root():
    return {"app": settings.app_name, "version": "0.1.0", "docs": "/docs"}
