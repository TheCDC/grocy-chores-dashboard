# UV Tooling Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove `requirements.txt` and switch Docker build to use `uv` for dependency management

**Architecture:** Delete legacy file, rewrite Dockerfile to use `ghcr.io/astral-sh/uv` multi-stage binary copy

**Tech Stack:** Docker, uv

## Global Constraints

- Delete `requirements.txt`
- Dockerfile must use `COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv`
- Dockerfile must use `uv sync --no-dev` (no `--frozen`, since lockfile is stale)
- Keep `python:3.12-slim` base image
- Keep `WORKDIR /app`, `COPY app ./app`, `EXPOSE 8080`, `CMD ["python", "-m", "app.main"]`

---

### Task 1: Rewrite Dockerfile and remove requirements.txt

**Files:**
- Delete: `requirements.txt`
- Modify: `Dockerfile`

- [ ] **Step 1: Delete requirements.txt**

```bash
git rm requirements.txt
```

- [ ] **Step 2: Rewrite Dockerfile**

Replace the entire Dockerfile:

```dockerfile
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev

COPY app ./app

# Keep in sync with Config.dashboard_port default in app/config.py.
EXPOSE 8080

CMD ["python", "-m", "app.main"]
```

- [ ] **Step 3: Run tests to verify nothing broke**

Run: `pytest tests/ -v`
Expected: All 17 tests pass (no Python code changed, only build tooling)

- [ ] **Step 4: Build Docker image to verify**

Run: `docker compose build`
Expected: Image builds successfully

- [ ] **Step 5: Commit**

```bash
git add requirements.txt Dockerfile pyproject.toml uv.lock
git commit -m "build: migrate Docker build from pip to uv"
```
