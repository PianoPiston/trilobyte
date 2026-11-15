"""Uvicorn-compatible application entry point.

Run: uvicorn server.main:app --host 127.0.0.1 --port 8100
The equivalent factory entry point is server.app:create_app.
"""
from .app import create_app

app = create_app()
