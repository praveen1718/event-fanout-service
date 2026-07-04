# --- build stage: resolve and install dependencies into a venv ---
FROM python:3.12-slim AS build

WORKDIR /build
COPY pyproject.toml ./
COPY app ./app

RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir .

# --- runtime stage: minimal image, non-root user ---
FROM python:3.12-slim

RUN useradd --create-home --uid 10001 appuser
WORKDIR /srv

COPY --from=build /opt/venv /opt/venv
COPY app ./app

# SQLite data lives here; mount a volume in real use
RUN mkdir -p /srv/data && chown -R appuser:appuser /srv

USER appuser
ENV PATH="/opt/venv/bin:$PATH"
EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
