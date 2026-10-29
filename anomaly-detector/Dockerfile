FROM python:3.12-slim AS base

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py ./

# Offline vertinimas: docker compose --profile eval run --rm evaluator <komanda>
FROM base AS eval
COPY requirements-eval.txt .
RUN pip install --no-cache-dir -r requirements-eval.txt
COPY evaluation ./evaluation
ENTRYPOINT ["python", "-m", "evaluation"]

FROM base AS runtime
CMD ["python", "-u", "detector.py"]
