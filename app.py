"""Vercel ASGI entry point; use the same application as local/Render deployments."""
from backend.api.main import app

__all__ = ['app']
