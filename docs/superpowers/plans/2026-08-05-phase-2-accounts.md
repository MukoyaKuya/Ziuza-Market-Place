# Phase 2 Accounts Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Wire accounts domain — registration, login/logout, profile, addresses, account nav, permissions foundation. Reuse existing User/Address models and services.

**Architecture:** Thin views → forms (shape) → services (domain) → selectors (reads). No marketplace domains.

**Tech Stack:** Django auth, server-rendered forms, design-system components, pytest

---

### Task 1: Settings + permissions + selectors
LOGIN_URL / redirects; `apps/accounts/permissions.py`; address/user selectors.

### Task 2: Forms
Registration, login, profile, address forms.

### Task 3: Views + URLs
Auth, profile, address CRUD under `/account/` and `/accounts/` auth routes matching PRD.

### Task 4: Templates + navbar
Account layout nav; pages using design-system inputs/buttons.

### Task 5: Tests
Registration, login/logout, profile authz, address ownership.
