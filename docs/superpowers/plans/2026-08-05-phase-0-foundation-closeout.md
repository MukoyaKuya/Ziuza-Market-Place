# Phase 0 Foundation Close-Out Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Complete PRD Phase 0 gaps without rewriting existing foundation or Phase 1+ assets.

**Architecture:** Preserve Vertical Slice layout (`apps/core`, `apps/accounts`). Canonical components live under `components/`; page templates under `templates/`. LocMem cache by default; Redis optional via `REDIS_URL`.

**Tech Stack:** Django 5, Tailwind, HTMX, Alpine.js, pytest-django

---

### Task 1: Error handlers + static URL fix

**Files:**
- Create: `apps/core/views/errors.py`
- Create: `templates/errors/400.html`, `templates/errors/403.html`
- Modify: `config/urls.py`

### Task 2: Cache stub (ADR-008)

**Files:**
- Modify: `config/settings/base.py`, `production.py`, `.env.example`

### Task 3: Component canonicalization

**Files:**
- Modify: `config/settings/base.py` TEMPLATES DIRS (`BASE_DIR` instead of `components/`)
- Delete: `templates/components/**` duplicates

### Task 4: README + docs

**Files:**
- Create: `README.md`, `docs/component-conventions.md`

### Task 5: Tests + verify

**Files:**
- Create: `tests/test_error_pages.py`
- Run: `pytest`
