---
title: Fenwick Support Queue
emoji: 🎫
colorFrom: blue
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
short_description: Fenwick Cloud engineering support queue (POST /tickets)
---

# Fenwick Cloud — Engineering Support Queue

A FastAPI service with one route, `POST /tickets`, that decides what happens to an
engineering support ticket: answer it, route it, mark it a duplicate, decide an
action, or refuse it. The build plan is in [BRIEFING.md](BRIEFING.md) and the
design decisions behind it are in [docs/design/DECISIONS.md](docs/design/DECISIONS.md).

The YAML block at the top of this file configures the Hugging Face Space.

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

## Deploy to Hugging Face Spaces

The service runs as a Docker Space on port 7860.

1. Log in with a token that has write access: `hf auth login`.
2. Commit your changes, then deploy `HEAD`:
   ```bash
   HF_SPACE=<owner>/<space-name> scripts/deploy_hf_space.sh
   ```
   The script creates the Space if needed and uploads the committed tree only,
   so untracked files such as `.env` are never published.
3. In the Space, open **Settings → Variables and secrets** and add the secret
   `GROQ_API_KEY` (and optionally the variable `GROQ_MODEL`). The Space restarts
   to pick it up.
4. Once the build finishes, the service is at `https://<owner>-<space-name>.hf.space`.
   Confirm it answers before submitting:
   ```bash
   python -m eval.runner --url https://<owner>-<space-name>.hf.space
   ```

Known limits of the free Space (DECISIONS Q1): it sleeps after 48 hours without
traffic, so the first request after that waits for a cold start; ticket state is
kept in memory and is lost whenever the Space restarts.
