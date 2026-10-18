import secrets
import string
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session

from app import models
from app.db import Base, engine, get_db
from app.schemas import LinkCreate, LinkOut

STATIC_DIR = Path(__file__).parent / "static"
ALPHABET = string.ascii_letters + string.digits


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="URL Shortener", lifespan=lifespan)


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
        raise HTTPException(status_code=409, detail="Code already in use")
    link = models.Link(code=payload.code or new_code(db), url=str(payload.url))
    db.add(link)
    db.commit()
    db.refresh(link)
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
        raise HTTPException(status_code=404, detail="Link not found")
    db.delete(link)
    db.commit()


@app.get("/{code}", include_in_schema=False)
def follow(code: str, db: Session = Depends(get_db)):
    link = db.get(models.Link, code)
    if link is None:
        raise HTTPException(status_code=404, detail="Link not found")
    link.clicks += 1
    db.commit()
    return RedirectResponse(link.url, status_code=302)
