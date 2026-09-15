FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY igmk_api /app/igmk_api
COPY static   /app/static

# The app only ever reads from its bind-mounts (/config, /data/obs), so it can
# run unprivileged.
RUN useradd --system --uid 10001 --no-create-home api
USER api

EXPOSE 8000

CMD ["gunicorn", \
     "--bind", "0.0.0.0:8000", \
     "-k", "uvicorn.workers.UvicornWorker", \
     "--workers", "4", \
     "--access-logfile", "-", \
     "igmk_api.app:app"]
