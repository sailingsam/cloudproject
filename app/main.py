import logging
import secrets
import string
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy.orm import Session

from app import config, models
from app.db import engine, get_db, init_schema, ping
from app.observability import (
    DB_UP,
    OPERATIONS,
    RequestMiddleware,
    setup_logging,
    setup_tracing,
)
from app.schemas import LinkCreate, LinkOut

STATIC_DIR = Path(__file__).parent / "static"
ALPHABET = string.ascii_letters + string.digits

setup_logging()
log = logging.getLogger("app")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_schema()
    log.info("startup complete", extra={"git_sha": config.GIT_SHA})
    yield
    log.info("shutting down")


app = FastAPI(title="URL Shortener", version=config.APP_VERSION, lifespan=lifespan)
app.add_middleware(RequestMiddleware)
TRACING_ENABLED = setup_tracing(app, engine)


# ---------------------------------------------------------------- operational endpoints
# Declared before the catch-all "/{code}" redirect route so they always win.


@app.get("/healthz", include_in_schema=False)
def healthz():
    """Liveness: the process is up and serving. Deliberately does NOT check
    the database, so a database outage does not make Kubernetes restart
    every healthy app pod."""
    return {"status": "ok"}


@app.get("/readyz", include_in_schema=False)
def readyz():
    """Readiness: can this pod serve real requests right now? Requires the
    database, so pods that cannot reach it are removed from the Service."""
    try:
        ping()
    except Exception as exc:  # noqa: BLE001
        DB_UP.set(0)
        log.warning("readiness check failed", extra={"error": type(exc).__name__})
        return JSONResponse(status_code=503, content={"status": "unavailable", "database": "down"})
    DB_UP.set(1)
    return {"status": "ready", "database": "up"}


@app.get("/version")
def version():
    """Lets anyone confirm exactly which build is serving traffic."""
    return {
        "version": config.APP_VERSION,
        "git_sha": config.GIT_SHA,
        "build_date": config.BUILD_DATE,
        "tracing": TRACING_ENABLED,
    }


@app.get("/metrics", include_in_schema=False)
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


# ---------------------------------------------------------------- application


def new_code(db: Session, length: int = 7) -> str:
    while True:
        code = "".join(secrets.choice(ALPHABET) for _ in range(length))
        if db.get(models.Link, code) is None:
            return code


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/api/links", response_model=LinkOut, status_code=201)
def create_link(payload: LinkCreate, db: Session = Depends(get_db)):
    if payload.code and db.get(models.Link, payload.code) is not None:
        OPERATIONS.labels("create", "conflict").inc()
        raise HTTPException(status_code=409, detail="Code already in use")
    link = models.Link(code=payload.code or new_code(db), url=str(payload.url))
    db.add(link)
    db.commit()
    db.refresh(link)
    OPERATIONS.labels("create", "success").inc()
    return link


@app.get("/api/links", response_model=list[LinkOut])
def list_links(db: Session = Depends(get_db)):
    return db.query(models.Link).order_by(models.Link.created_at.desc()).limit(100).all()


@app.get("/api/links/{code}", response_model=LinkOut)
def link_stats(code: str, db: Session = Depends(get_db)):
    link = db.get(models.Link, code)
    if link is None:
        raise HTTPException(status_code=404, detail="Link not found")
    return link


@app.delete("/api/links/{code}", status_code=204)
def delete_link(code: str, db: Session = Depends(get_db)):
    link = db.get(models.Link, code)
    if link is None:
        OPERATIONS.labels("delete", "not_found").inc()
        raise HTTPException(status_code=404, detail="Link not found")
    db.delete(link)
    db.commit()
    OPERATIONS.labels("delete", "success").inc()


@app.get("/{code}", include_in_schema=False)
def follow(code: str, db: Session = Depends(get_db)):
    """The hot path users actually hit; covered by the latency SLO."""
    link = db.get(models.Link, code)
    if link is None:
        # A 404 for an unknown code is a correct answer, not a server error,
        # so it does not consume the availability error budget (5xx only).
        OPERATIONS.labels("redirect", "not_found").inc()
        raise HTTPException(status_code=404, detail="Link not found")
    link.clicks += 1
    db.commit()
    OPERATIONS.labels("redirect", "success").inc()
    return RedirectResponse(link.url, status_code=302)
