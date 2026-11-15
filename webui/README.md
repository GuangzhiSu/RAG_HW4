# Web UI and live-test endpoint

A FastAPI app that serves the HW4 Step 7 endpoint and a small web UI (bonus +2).

| Route | Purpose |
|---|---|
| `GET /answer?question=...` | Live-test endpoint. Returns `{"answer_candidate": "...", "sources": ["<title>", ...]}` |
| `GET /` | Web UI: a question box that calls `/answer` and shows the answer with linked sources |
| `GET /healthz` | Health check, also handy for waking a sleeping free-tier host before the live test |
| `GET /docs` | Auto-generated API docs |

## Layout

```
webui/
├── app.py          FastAPI routes, input validation, response model
├── backend.py      answer_question(): the one hook into the QA system (currently a stub)
└── static/
    ├── index.html  page markup
    ├── style.css   styles (light and dark)
    └── app.js      calls /answer, renders the answer, sources and timing
```

## Run locally

From the repository root:

```bash
pip install -r requirements.txt
```

```bash
uvicorn webui.app:app --reload --port 8000
```

Then open http://localhost:8000, or:

```bash
curl -G "http://localhost:8000/answer" --data-urlencode "question=Where was Anna Julia Cooper born?"
```

## Status: skeleton

`backend.answer_question()` returns a placeholder (`"unanswerable"`, no sources) for every question. To wire in the real system:

1. Implement the final pipeline in `src/`. The live test requires the endpoint to run the code in the submitted `src/`.
2. Replace the stub in `webui/backend.py` with a call into it. Load models and indexes once at startup, not per request.
3. Keep the AI Gateway key in the host's secret settings and read it from an environment variable.

`backend.normalize()` already enforces the response contract: an `unanswerable` answer always has `sources: []`, and source titles are de-duplicated.

## Deployment requirements (HW4 Step 7)

- The URL must be public HTTPS, reachable without a login. Put the base URL in the top-level `README.md`.
- Each question must be answered within 60 seconds. The UI aborts after 65 s.
- The endpoint must be up all day on the live-test date. Hit `/healthz` beforehand to wake it.
- Hosts usually provide the port in `$PORT`. A typical start command is `uvicorn webui.app:app --host 0.0.0.0 --port $PORT`.
