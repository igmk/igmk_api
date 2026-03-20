FROM python:3.8-slim


COPY requirements.txt .
RUN python -m pip install -r requirements.txt


COPY ./app /app
WORKDIR /app

EXPOSE 8000

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "-k", "uvicorn.workers.UvicornWorker", "run:app"]
