# Image for the Hugging Face Docker Space (BRIEFING.md §11).
# Python matches the version the test suite runs on.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Spaces run the container as UID 1000; use the same user locally so
# permission problems show up before deploying, not after.
RUN useradd --create-home --uid 1000 user

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --chown so the app can read its files whatever their mode on the build host.
COPY --chown=user:user . .

USER user

EXPOSE 7860
# A single worker on purpose: ticket state and the ticket-id counter live in
# process memory, so extra workers would each see a different queue.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
