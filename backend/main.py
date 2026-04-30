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
import time
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.career_routes import router as career_router
from app.api.routes import router
from app.services.pipeline_orchestrator_service import pipeline_orchestrator_service
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
app.include_router(career_router)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id", str(uuid4()))
    start = time.perf_counter()
    request.state.request_id = request_id
    response = await call_next(request)
    duration_ms = round((time.perf_counter() - start) * 1000, 2)
    response.headers["x-request-id"] = request_id
    logger.info(
        "request_completed request_id=%s method=%s path=%s status=%s duration_ms=%s",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    request_id = getattr(request.state, "request_id", str(uuid4()))
    payload = {
        "error": {
            "code": f"HTTP_{exc.status_code}",
            "message": str(exc.detail),
            "details": {"path": request.url.path},
            "retryable": exc.status_code in {429, 500, 502, 503},
        },
        "request_id": request_id,
    }
    return JSONResponse(status_code=exc.status_code, content=payload)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", str(uuid4()))
    logger.exception("unhandled_error request_id=%s path=%s error=%s", request_id, request.url.path, exc)
    payload = {
        "error": {
            "code": "INTERNAL_SERVER_ERROR",
            "message": "Unexpected server error",
            "details": {"path": request.url.path},
            "retryable": True,
        },
        "request_id": request_id,
    }
    return JSONResponse(status_code=500, content=payload)


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    """Convert service validation errors to client-safe 4xx responses."""
    request_id = getattr(request.state, "request_id", str(uuid4()))
    msg = str(exc) or "Invalid request"
    status_code = 404 if "not found" in msg.lower() else 400
    payload = {
        "error": {
            "code": "NOT_FOUND" if status_code == 404 else "BAD_REQUEST",
            "message": msg,
            "details": {"path": request.url.path},
            "retryable": False,
        },
        "request_id": request_id,
    }
    return JSONResponse(status_code=status_code, content=payload)


@app.on_event("startup")
async def startup_log():
    """Initial startup logs."""
    await pipeline_orchestrator_service.start()
    logger.info("AI Sales API is starting up. Enrichment method: Web Scraper")


@app.on_event("shutdown")
async def shutdown_log():
    """Graceful shutdown cleanup."""
    await pipeline_orchestrator_service.stop()
    logger.info("AI Sales API shutdown complete.")


@app.get("/")
async def root():
    return {
        "message": "AI Sales API",
        "docs": "/docs",
        "health": "/api/health",
    }
