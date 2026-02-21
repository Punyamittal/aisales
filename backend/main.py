"""FastAPI application entrypoint."""
# Load .env from project root and backend/ FIRST so HUNTER_API_KEY is available
from pathlib import Path
try:
    import dotenv
    _backend_dir = Path(__file__).resolve().parent
    dotenv.load_dotenv(_backend_dir / ".env")
    dotenv.load_dotenv(_backend_dir.parent / ".env")
except Exception:
    pass

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from config import get_settings

logger = logging.getLogger(__name__)

app = FastAPI(
    title="AI Sales",
    description="Autonomous AI Business and Career Agent API",
    version="0.1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "http://localhost:3002",
        "http://127.0.0.1:3002",
        "http://localhost:3003",
        "http://127.0.0.1:3003",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


@app.on_event("startup")
async def startup_log():
    """Initial startup logs."""
    logger.info("AI Sales API is starting up. Enrichment method: Web Scraper")


@app.get("/")
async def root():
    return {
        "message": "AI Sales API",
        "docs": "/docs",
        "health": "/api/health",
    }
