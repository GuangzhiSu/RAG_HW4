"""Bridge between the web app and the QA system.

This is the single place where the web app calls the RAG pipeline. For now
it returns a placeholder answer; wire it to the final system in src/ later
(the live test requires the endpoint to run the code in src/).

Contract (same as one entry of `answers` in the run files, HW4 Section V):
    answer_question("...") -> {"answer_candidate": str, "sources": [str, ...]}
where answer_candidate is a short answer, or exactly "unanswerable" with
sources == [].
"""

from __future__ import annotations

UNANSWERABLE = "unanswerable"


def answer_question(question: str) -> dict:
    """Answer one question with the final system.

    TODO: replace the stub with a call into the final pipeline, e.g.
        from src.pipeline import FinalSystem
        result = FinalSystem.load(config).answer(question)
        return {"answer_candidate": result.answer, "sources": result.sources}
    Load models and indexes once at import/startup time, not per request:
    every live-test question must be answered within 60 seconds.
    """
    return {"answer_candidate": UNANSWERABLE, "sources": []}


def normalize(result: dict) -> dict:
    """Coerce a pipeline result into the exact response format."""
    answer = str(result.get("answer_candidate", "")).strip() or UNANSWERABLE
    if answer.lower() == UNANSWERABLE:
        return {"answer_candidate": UNANSWERABLE, "sources": []}
    sources = list(dict.fromkeys(str(s) for s in result.get("sources", []) if s))
    return {"answer_candidate": answer, "sources": sources}
