from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from contextlib import asynccontextmanager

# Define DATABASE_URL - replace with your actual database URL
DATABASE_URL = "sqlite+aiosqlite:///./test.db"

# Async database engine
engine = create_async_engine(
    DATABASE_URL,
    echo=True,
    pool_size=20,
    max_overflow=30,
    pool_pre_ping=True
)

from .database import get_db, engine
from . import models

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.create_all)
    yield

app = FastAPI(
    title="Speakr Enterprise API",
    description="Enterprise-grade audio transcription platform",
    version="2.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from .routers import jobs

app.include_router(jobs.router)

@app.get("/")
async def read_root():
    return {"message": "Welcome to the Speakr Enterprise API"}
