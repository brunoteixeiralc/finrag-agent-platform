# syntax=docker/dockerfile:1

FROM python:3.14.6-slim-bookworm

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN groupadd --gid 10001 finrag \
    && useradd --uid 10001 --gid finrag --no-log-init --create-home --shell /usr/sbin/nologin finrag

COPY pyproject.toml README.md ./
COPY app ./app

RUN python -m pip install .

USER 10001:10001

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
