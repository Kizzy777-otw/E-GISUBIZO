"""FastAPI application entry point."""

from contextlib import asynccontextmanager
import logging
import os
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .database import Base, SessionLocal, engine
from .routers import auth, hardware, notifications, tickets, trees, users
from .seed import seed_initial_data

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_initial_data(db)
    yield


app = FastAPI(
    title="E-Gisubizo API",
    description="Offline-first diagnostics and service dispatch for rural energy systems.",
    version="1.0.0",
    lifespan=lifespan,
)

allowed_origins = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]
if allowed_origins:
    # Leave same-origin deployments simple; separate origins must be explicitly trusted.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH"],
        allow_headers=["Authorization", "Content-Type"],
    )

app.include_router(auth.router)
app.include_router(hardware.router)
app.include_router(trees.router)
app.include_router(tickets.router)
app.include_router(notifications.router)
app.include_router(users.router)
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
