# Reduction Report — 2026-04-23

**Project:** Essay Search Engine (Shelf)
**Driver:** Nonstop `/refactor-project` → `/open-source-release`
**Baseline commit:** `3b9135b` (after WIP baseline)
**Final commit:** `8e71888`

## Baseline (pre-refactor, including WIP commit)

| File | LOC |
|---|---|
| `src/main.js` | 271 |
| `src/search.js` | 151 |
| `src/service-worker.js` | 79 |
| `src/chunk.js` | — |
| `src/tags.js` | — |
| `src/utils.js` | — |
| `index.html` | 40 |
| `chunk.html` | 84 |
| `tags.html` (root) | — |
| `public/tags.html` | 2221 |
| `vite.config.js` | 31 |
| `process_book.py` | 1056 |
| `sync/build.py` | 198 |
| **Frontend+config subtotal** | **2877** |
| **Pipeline subtotal** | **1254** |
| **Grand total** | **4131** |

**Runtime deps:** `fuse.js` (1).
**Dev deps:** `marked`, `vite` (2).
**No linter, formatter, tests, or TypeScript.**

## Final state

| File | LOC | Δ |
|---|---|---|
| `src/main.js` | 257 | −14 |
| `src/search.js` | 84 | −67 |
| `src/service-worker.js` | 55 | −24 |
| `src/chunk.js` | 45 | +45 (new; supersedes inline in `chunk.html`) |
| `src/tags.js` | 23 | +23 (new; supersedes `public/tags.html`) |
| `src/utils.js` | 19 | +19 (new; shared helpers) |
| `index.html` | 40 | 0 |
| `chunk.html` | 31 | −53 |
| `tags.html` (root) | 20 | +20 (new; replaces `public/tags.html`) |
| `public/tags.html` | — | −2221 (removed) |
| `vite.config.js` | 32 | +1 |
| `process_book.py` | 1040 | −16 |
| `sync/build.py` | 158 | −40 |
| **Frontend+config subtotal** | **606** | **−2271** |
| **Pipeline subtotal** | **1198** | **−56** |
| **Grand total** | **1804** | **−2327 (−56%)** |

## Discovery answers

1. Project purpose confirmed (static client-side essay search, Fuse.js + pre-built JSON).
2. `embeddings.json` — not dead, latent feature. Kept in pipeline; documented in README as staged-for-future.
3. `public/tags.html` — must remain offline-capable. Replaced with SW-cached dynamic render.
4. Python pipeline in scope.

## Pass history

| # | Item | Commit | Net LOC | Notes |
|---|---|---|---|---|
| 0 | WIP baseline commit | `3b9135b` | +2420 / −2776 | Pre-existing UI redesign, not part of refactor |
| 1 | search.js dead Fuse + config dedupe | `491395f` | −64 | First `Fuse` was never read; extracted `FUSE_OPTIONS`; added `{ cause }` to init error |
| 2 | Pagination delegated handler | `600f458` | +2 (quality) | 3 listeners → 1 delegated; listener now registers once, not per render |
| 3 | Service worker nav-path collapse | `3a86789` | −24 | `NAV_PATHS` set + derived `cacheKey`; bumped `CACHE_VERSION` to v9 |
| 4 | Extract `src/utils.js` | `62850e2` | 0 (dedupe) | `escapeHtml`, `excerpt`, `parseTags` shared by `main.js` and `search.js` |
| 5 | Move chunk.html inline → `src/chunk.js` | `40cba0f` | −8 | Now participates in Vite bundling; imports shared utils |
| 6 | tags.html dynamic render | `6b20de5` | −2218 | Deleted pre-generated `public/tags.html`; root `tags.html` + `src/tags.js` + build.py simplification |
| 7 | Python pipeline helpers | `619de80` | −16 | `load_books_metadata` / `save_books_metadata` replace 4 duplicated blocks |
| 8 | README architecture + embeddings note | `8e71888` | +16 / −8 | Refreshed file tree; documented `embeddings.json` as latent |

## Rejected / deferred

- **Fuse caching across repeat searches** — Agent-2 flagged as HIGH perf. Deferred: adds LOC and cache-invalidation complexity, and Fuse rebuild on ~thousands of chunks is already sub-100 ms. Not a reduction, not urgent.
- **Collapse `isLoading`/`isReady` into a state enum** — meaningful distinction (idempotence guard vs usability flag); collapsing would add state-machine code that outweighs the saved boolean.
- **Factor the 7 FILTER blocks in `chunk_markdown_hierarchically`** — domain-specific filter tuning; no tests; high regression risk.
- **Per-search tag pre-parsing** — noted as MED perf; same tradeoff as Fuse caching.
- **Dropping `embeddings.json` generation** — user explicitly flagged this feature as "should work"; kept the pipeline step and documented in README.

## Convergence

Not reached — each pass delivered substantive reduction (Item 6 alone was −2218). The backlog was exhausted before triggering the <2%-for-3-passes stop condition, so the loop ended on completeness rather than diminishing returns.
