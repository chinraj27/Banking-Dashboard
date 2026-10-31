import logging
import time

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException
from sqlalchemy import text
from contextlib import asynccontextmanager

from app.api import auth, products
from app.core.config import settings
from app.database.mongo import mongo
from app.database.postgres import Base, SessionLocal, engine
from app.database.redis_client import cache
from app.models import models  # noqa: F401  (registers tables)
from app.services.seed import seed_demo_data, seed_metadata

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("banking")


def init_db(retries: int = 10) -> None:
    for attempt in range(1, retries + 1):
        try:
            Base.metadata.create_all(bind=engine)  # no-op for tables created by sql/schema.sql
            return
        except Exception as exc:
            log.warning("Database not ready (%s/%s): %s", attempt, retries, exc)
            time.sleep(2)
    raise RuntimeError("Database is not reachable")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    if settings.seed_demo_data:
        with SessionLocal() as db:
            seed_demo_data(db)
        seed_metadata()
    yield


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="Mock banking data only. No real accounts or payments.",
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


def _error(status_code: int, message: str, errors: list | None = None, headers: dict | None = None):
    body = {"success": False, "error": {"code": status_code, "message": message}}
    if errors:
        body["error"]["details"] = errors
    return JSONResponse(status_code=status_code, content=body, headers=headers)


@app.exception_handler(HTTPException)
async def http_error(_: Request, exc: HTTPException):
    return _error(exc.status_code, str(exc.detail), headers=getattr(exc, "headers", None))


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError):
    # only field + message are returned; the submitted values (e.g. passwords) are never echoed
    details = [{"field": ".".join(str(p) for p in e["loc"][1:]), "message": e["msg"]} for e in exc.errors()]
    return _error(422, "Validation failed", details)


@app.exception_handler(Exception)
async def unhandled_error(_: Request, exc: Exception):
    log.exception("Unhandled error: %s", exc)
    return _error(500, "Something went wrong. Please try again later.")


@app.get("/api/health", tags=["System"])
def health():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    status = "ok" if db_ok else "degraded"
    return {
        "status": status,
        "postgres": db_ok,
        "redis": {"ok": cache.ping(), "backend": cache.backend},
        "mongodb": {"ok": mongo.ping(), "backend": mongo.backend},
    }


app.include_router(auth.router, prefix="/api")
app.include_router(products.router, prefix="/api")
