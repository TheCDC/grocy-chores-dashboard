FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev

COPY app ./app

# Keep in sync with Config.dashboard_port default in app/config.py.
EXPOSE 8080

# TODO: add a HEALTHCHECK once main.py/NiceGUI exposes something to poll
# (NiceGUI serves on "/" by default, which is fine as a health endpoint).

CMD ["python", "-m", "app.main"]
