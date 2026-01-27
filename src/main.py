"""FastAPI application entrypoint."""

from fastapi import FastAPI

from src.api.health import router as health_router

app = FastAPI(title="Infinite Text World")

app.include_router(health_router)
