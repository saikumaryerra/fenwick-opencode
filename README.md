# Fenwick Cloud — Engineering Support Queue

A FastAPI service with one route, `POST /tickets`, that decides what happens to an
engineering support ticket: answer it, route it, mark it a duplicate, decide an
action, or refuse it. The build plan is in [BRIEFING.md](BRIEFING.md) and the
design decisions behind it are in [docs/design/DECISIONS.md](docs/design/DECISIONS.md).

## Run locally

Requires Python 3.11+ (the Docker image and the test runs use 3.13).

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --port 7860
```

Model calls go to Groq. Set `GROQ_API_KEY` in the environment to enable them;
without it, model calls are skipped and tickets are classified by keyword rules.
`GROQ_MODEL` optionally overrides the model. The app does not read `.env`
itself, so export the variables or pass `--env-file .env` to Docker.

Try it:

```bash
curl -s -X POST http://localhost:7860/tickets \
  -H 'content-type: application/json' \
  -d '{"text": "who owns billing-sync now", "filed_by": "FEN-1001", "ticket_id": null}'
```

`filed_by` must be an `emp_id` from `fenwick-data-pack/engineer_roster.csv`.
Interactive API docs are at `/docs`; `/health` returns `{"status": "ok"}`.

## Tests and evaluation

```bash
pip install pytest pytest-asyncio
pytest
python -m eval.runner                           # in-process
python -m eval.runner --url http://localhost:7860  # against a running server
```

## Run with Docker

```bash
docker build -t fenwick-support-queue .
docker run --rm -p 7860:7860 --env-file .env fenwick-support-queue
```

## Deploy (Render, free plan)

Hugging Face Docker Spaces now require a PRO plan, so the service runs on
Render's free plan from [render.yaml](render.yaml).

1. Open https://render.com/deploy?repo=https://github.com/saikumaryerra/fenwick-opencode
   and sign in; Render reads `render.yaml` and creates the web service.
2. Enter `GROQ_API_KEY` when prompted (leave blank to run rules-only).
3. Pushes to `main` redeploy automatically.
4. Check it: `python -m eval.runner --url https://<service>.onrender.com`

Known limits of the free plan: the service sleeps after 15 minutes without
traffic and the next request waits about a minute for it to start; ticket state
is kept in memory and is lost on every restart or sleep.
