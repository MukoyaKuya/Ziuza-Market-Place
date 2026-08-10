# Phase 4 Catalog Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Browseable marketplace catalog — Category, Listing, ListingImage, ListingVariant, Inventory, ListingAttribute; seller listing management; listing detail; category pages.

**Architecture:** `apps.marketplace.categories` + `apps.marketplace.listings` vertical slices. Money as Decimal + currency. Inventory authoritative on server. Seller mutations require shop ownership.

**Scope out:** Search engine, cart, homepage CMS, shipping profiles beyond a simple optional note, image derivatives/CDN.
