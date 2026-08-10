# Component conventions

Canonical UI partials live under `components/<name>/<name>.html`.

Page templates and layouts live under `templates/`. Do **not** duplicate components under `templates/components/`.

## Include path

`TEMPLATES['DIRS']` includes the project root, so includes use the `components/` prefix:

```django
{% include 'components/button/button.html' with label="Shop Now" variant="red" %}
```

## Rules

1. One folder per component; primary template matches the folder name.
2. Prefer variants via `with` kwargs (`variant`, `size`, `disabled`, `loading`) over forked copies.
3. Components present markup only — no marketplace business rules.
4. Forms validate shape; services enforce domain rules (later phases).
5. HTMX attributes may appear on interactive controls; Alpine may manage open/closed UI state only.
6. New shared primitives belong in `components/`, then appear on `/design-system/`.
7. Support `disabled`, error, and focus-visible states on interactive controls.
8. Meaningful controls need accessible names (`label`, `aria-label`, or visible text).

## Design tokens

Defined in `tailwind.config.js` and composed in `static/src/input.css`:

| Token family | Examples |
|--------------|----------|
| Brand / Kenya | `kenya-green`, `kenya-red`, `kenya-black`, `brand-primary`, `brand-surface-*` |
| Typography | `font-sans` (Inter), `font-display` (Outfit) |
| Radii / shadow | `rounded-ziuza`, `rounded-pill`, `shadow-ziuza-*` |
| Form utilities | `.field-label`, `.field-input`, `.field-error`, `.field-hint` |
| Buttons | `.btn-red`, `.btn-secondary`, `.btn-ghost`, `.btn-icon`, `.btn-sm`, `.btn-lg` |
| Feedback | `.alert-error`, `.alert-success`, `.alert-warning`, `.skeleton` |

Rebuild CSS after token changes:

```powershell
npm run build:css
```

## Inventory (Phase 1)

| Component | Path |
|-----------|------|
| Button | `components/button/button.html` |
| Icon button | `components/icon_button/icon_button.html` |
| Input | `components/input/input.html` |
| Textarea | `components/textarea/textarea.html` |
| Select | `components/select/select.html` |
| Checkbox | `components/checkbox/checkbox.html` |
| Radio | `components/radio/radio.html` |
| Search | `components/search/search.html` |
| Badge | `components/badge/badge.html` |
| Price | `components/price/price.html` |
| Rating | `components/rating/rating.html` |
| Avatar | `components/avatar/avatar.html` |
| Breadcrumbs | `components/breadcrumbs/breadcrumbs.html` |
| Pagination | `components/pagination/pagination.html` |
| Tabs | `components/tabs/tabs.html` |
| Listing card | `components/listing_card/listing_card.html` |
| Shop card | `components/shop_card/shop_card.html` |
| Category card | `components/category_card/category_card.html` |
| Collection card | `components/collection_card/collection_card.html` |
| Trust badge | `components/trust_badge/trust_badge.html` |
| Modal | `components/modal/modal.html` |
| Drawer | `components/drawer/drawer.html` |
| Toast | `components/toast/toast.html` |
| Empty state | `components/empty_state/empty_state.html` |
| Skeleton | `components/skeleton/skeleton.html` |
| Error state | `components/error_state/error_state.html` |
| Bar chart | `components/bar_chart/bar_chart.html` |

Living showcase: `/design-system/`

## Alpine vs HTMX

- **Alpine:** dropdowns, mobile nav, modal/drawer open state, tabs, toasts.
- **HTMX:** future partial updates (search, favorites, cart). Pass `hx_*` kwargs on search/pagination when endpoints exist — do not invent JS business logic.
