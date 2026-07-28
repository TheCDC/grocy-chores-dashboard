# UV Tooling Migration Design

**Goal:** Eliminate `requirements.txt` and switch the Docker build to use `uv` as the sole package manager.

## Changes

1. **Delete `requirements.txt`** — stale; all deps live in `pyproject.toml` + `uv.lock`
2. **Rewrite `Dockerfile`** — use `ghcr.io/astral-sh/uv` to install deps via `uv sync --no-dev`
   - No `--frozen` flag (lockfile is stale; let uv regenerate during build)
   - Keeps `python:3.12-slim` base, `WORKDIR /app`, `COPY app ./app`, `EXPOSE 8080`, `CMD` unchanged
3. **Regenerate `uv.lock`** — `uv sync` in Docker will produce a fresh lockfile; no manual `uv sync` needed on the host
