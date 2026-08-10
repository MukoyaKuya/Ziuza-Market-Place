# Phase 1 Design System Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Complete PRD Phase 1 — reusable semantic UI components, design tokens, mobile-first a11y states, living `/design-system/` page. No marketplace domain logic.

**Architecture:** Canonical partials under `components/<name>/<name>.html`. Tokens in `tailwind.config.js` + `static/src/input.css`. Alpine for UI-only state; no JS business rules.

**Tech Stack:** Django templates, Tailwind 3, Alpine.js, HTMX (stubs only), pytest

---

### Task 1: Design tokens & base CSS

Expand semantic form/focus/state utilities in `input.css`; add `x-cloak` and reduced-motion; success/warning/danger text helpers if needed.

### Task 2: Form primitives

Create: `input`, `textarea`, `select`, `checkbox`, `radio`, `search`

### Task 3: Navigation & feedback primitives

Create: `icon_button`, `avatar`, `breadcrumbs`, `pagination`, `tabs`, `drawer`, `empty_state`, `skeleton`, `error_state`, `collection_card`

Improve: `modal` (ARIA), `button` (sizes/loading)

### Task 4: Showcase + docs + tests

Update `design_system.html`, `docs/component-conventions.md`, tests asserting new sections render.

### Task 5: Verify

`npm run build:css` · `pytest` · `manage.py check`
