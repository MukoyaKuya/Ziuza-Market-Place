# Phase 3 Shops + Seller Dashboard Shell

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Shop domain + seller dashboard shell. Dashboard is the primary UX deliverable; listings/orders/analytics are placeholder sections until later phases.

**Architecture:** `apps.marketplace.shops` vertical slice — models, services, selectors, permissions, thin views. Seller capability derives from shop ownership (not a User flag).

**Scope in:**
- Shop model + verification status
- Create shop (onboarding)
- Shop settings
- Dashboard shell with section nav + overview stats stubs
- Public shop page (minimal)
- Ownership authorization on every seller mutation

**Scope out:** Listings, inventory, orders, reviews, messaging, real analytics, media upload pipeline beyond ImageField fields.
