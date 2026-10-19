"""Vercel entrypoint for the Guard-AI FastAPI application."""

from backend.app.main import app


__all__ = ["app"]
