# Natural-Language Due Dates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace raw `str(chore.due_at)` with human-readable relative time strings ("2 days ago", "in 2 weeks", etc.)

**Architecture:** Add `humanize` dependency, one-line change in `app/ui/chore_row.py`

**Tech Stack:** Python, `humanize>=4.9`

## Global Constraints

- Add `humanize>=4.9` to `pyproject.toml` dependencies array

---

### Task 1: Add dependency and update date display

**Files:**
- Modify: `pyproject.toml:7-10`
- Modify: `app/ui/chore_row.py:62-68`

**Interfaces:**
- Consumes: `DashboardChore.due_at` (`datetime | None`), `DashboardChore.is_overdue` (`bool`)
- Produces: `humanize.naturaltime(chore.due_at)` rendered in UI label

- [ ] **Step 1: Add humanize dependency**

Edit `pyproject.toml` dependencies to add `"humanize>=4.9"`:

```toml
dependencies = [
    "grocy-py>=0.1.0",
    "nicegui>=3.15.0",
    "humanize>=4.9",
]
```

- [ ] **Step 2: Install dependency**

Run: `uv sync`

- [ ] **Step 3: Update chore_row.py — replace raw str() with naturaltime**

Add `import humanize` at the top of `app/ui/chore_row.py` (after the existing stdlib imports).

Replace the due-at label block (lines 62-68):

```python
# Before:
            if chore.due_at is not None:
                # TODO: human-friendly relative due-date formatting
                # ("Overdue by 2 days" / "Due tomorrow"), not a raw
                # timestamp — this is a glance-at-from-across-the-room UI.
                ui.label(str(chore.due_at)).style(f"color: {resolved_theme.text_muted};").classes(
                    "text-sm"
                )

# After:
            if chore.due_at is not None:
                ui.label(humanize.naturaltime(chore.due_at)).style(
                    f"color: {resolved_theme.text_muted};"
                ).classes("text-sm")
```

Remove the TODO lines (63-65) as part of the edit.

- [ ] **Step 4: Run tests**

Run: `pytest tests/ -v`

Expected: All existing tests pass (the display change is purely presentational — no test currently asserts on due-date label text content).

- [ ] **Step 5: Run the app to verify**

Run: `python -m app.main`

Expected: Due dates appear as "2 days ago", "in 2 weeks", "now", etc. instead of raw timestamps.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml app/ui/chore_row.py
git commit -m "feat: show natural-language due dates (humanize.naturaltime)"
```
