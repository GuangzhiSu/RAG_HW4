"""FastAPI app: the live-test endpoint plus a small web UI.

Routes
    GET /answer?question=...  -> {"answer_candidate": "...", "sources": [...]}
    GET /healthz              -> {"status": "ok"}   (for host health checks / wake-ups)
    GET /                     -> web UI (webui/static/index.html)

Run locally (from the repository root):
    uvicorn webui.app:app --reload --port 8000
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from webui.backend import answer_question, normalize

STATIC_DIR = Path(__file__).resolve().parent / "static"
MAX_QUESTION_CHARS = 1000

log = logging.getLogger("webui")
app = FastAPI(title="Anna Julia Cooper QA", docs_url="/docs", redoc_url=None)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class Answer(BaseModel):
    answer_candidate: str
    sources: list[str]


@app.get("/answer", response_model=Answer)
def answer(question: str = Query(..., description="The question to answer")) -> Answer:
    question = question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="question must not be empty")
    if len(question) > MAX_QUESTION_CHARS:
        raise HTTPException(status_code=400, detail=f"question is longer than {MAX_QUESTION_CHARS} characters")
    start = time.perf_counter()
    result = normalize(answer_question(question))
    log.info("answered in %.2fs: %r -> %r", time.perf_counter() - start, question, result["answer_candidate"])
    return Answer(**result)


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
