# Shelf

Turn any EPUB into a searchable, offline-first web library — deployed free on GitHub Pages.

Shelf is a personal search engine for books and essays. Drop in an EPUB, and the CLI extracts chapters, generates semantic tags with a local LLM, and builds a static site you can search from anywhere — even without an internet connection.

**[Live demo →](https://james-andrews-coulter.github.io/essay_search_engine/)**

---

## Why

I read a lot of essays — philosophy, psychology, spirituality — and when a life question hits, I mine my library for relevant chapters to build a kind of *reading playlist*: a curated set of passages I can listen to via iPhone screen reader while at the gym, cleaning the house, or staring out a plane window.

The problem was sourcing. A hundred books, twenty chapters each, and titles rarely tell you what's inside. I wanted a catalog-wide index — one search across everything I've ever read — so I could go from question to curated study in seconds instead of hours.

Something I didn't expect to learn: **insight without inquiry is a sugary statistic.** The answers you find are only as good as the questions you ask yourself. Building the search engine was the easy part. Learning to stop and ask what I actually needed to know — that was the real work.

Shelf runs entirely client-side. No server, no subscription, no API key. The only backend is your laptop during the one-time book import.

## How it works

```
EPUB → Markdown → Semantic chunks → AI tags → Static JSON → Client-side search
```

1. **Import** — `process_book.py` extracts clean markdown from EPUB, detects chapters (5 heading patterns), and splits content into semantic chunks via LlamaIndex.
2. **Tag** — Each chunk gets 3–5 single-word semantic tags from a local Ollama model (`qwen2.5:7b`). No API costs, no data leaves your machine.
3. **Build** — `sync/build.py` compiles all chunks into a single `metadata.json` with full content, plus a `tags.json` index.
4. **Search** — Fuse.js powers weighted keyword/fuzzy search in the browser. Tag filtering uses exact AND logic. Results paginate at 25 per page.
5. **Deploy** — Push to GitHub and Actions deploys to Pages. A service worker pre-caches everything for offline use.

## Quick start

### Prerequisites

- Python 3.10+
- Node.js 20+
- [Ollama](https://ollama.com) with `qwen2.5:7b` (`ollama pull qwen2.5:7b`)

### Setup

```bash
git clone https://github.com/<you>/shelf.git && cd shelf
./setup.sh      # Creates venv, installs Python deps
npm install     # Installs Node deps
```

### Add a book

```bash
ollama serve                # Start the local LLM (if not running)
./lib book.epub             # Process and add a book
./lib --sync                # Build the search index
npm run dev                 # Preview at localhost:5173
```

### Manage your library

```bash
./lib --list                # List all books
./lib --delete "Title"      # Remove a book
./lib --sync                # Rebuild after changes
```

### Deploy

Push to GitHub with Pages enabled. The included workflow builds and deploys automatically.

> **Note:** Update `base` in `vite.config.js` to match your repo name.

## Architecture

```
shelf/
├── lib                      # CLI entry point (bash)
├── process_book.py          # EPUB → chunks → tags pipeline
├── setup.sh                 # One-command environment setup
├── sync/
│   └── build.py             # Generates metadata.json + tags.json
├── src/
│   ├── search.js            # Fuse.js search engine (weighted fields)
│   ├── main.js              # UI logic, pagination, autocomplete
│   ├── service-worker.js    # Cache-first offline support
│   └── styles.css           # Minimal, mobile-first CSS
├── public/data/             # Generated search index (committed)
│   ├── metadata.json
│   └── tags.json
├── index.html               # Search interface
└── chunk.html               # Dynamic chunk viewer (renders markdown)
```

### Design decisions

**Client-side search, no backend.** All book data ships as static JSON. Fuse.js (9KB) handles fuzzy matching with field weights tuned for book content — title matches rank highest, raw content lowest. This eliminates hosting costs and keeps the app fast on repeat visits.

**Local AI for tagging.** Ollama runs on your machine. Tags like `"jealousy, rivalry, comparison"` make 1–2 word searches useful in a way that full-text search alone can't. No API key, no usage limits, no data uploaded anywhere.

**Offline-first.** A service worker pre-caches the app shell and all search data on first load. After that, the entire library works without a connection. Cache versioning ensures updates propagate cleanly.

**Single-page chunk viewer.** One `chunk.html` renders any chunk dynamically from `metadata.json` using `marked.js`. No static HTML generation, no build step per book.

## Search weights

| Field | Weight | Rationale |
|-------|--------|-----------|
| Book title | 0.4 | Highest — narrows to a specific work |
| Chapter title | 0.3 | Structural navigation |
| Tags | 0.2 | Semantic discovery |
| Content | 0.1 | Lowest — avoids noise from long text |

## Tech stack

| Layer | Tools |
|-------|-------|
| Processing | Python, ebooklib, BeautifulSoup, LlamaIndex |
| Tagging | Ollama, qwen2.5:7b |
| Search | Fuse.js (client-side) |
| Frontend | Vanilla JS, Vite, marked.js |
| Offline | Service Worker (cache-first) |
| Deploy | GitHub Actions → GitHub Pages |

## Fork and customize

1. Fork this repo
2. Delete `private/` and `public/data/` contents
3. Update `base` in `vite.config.js` to `/<your-repo-name>/`
4. Update the service worker's `PRECACHE_ASSETS` paths in `src/service-worker.js`
5. Run `./setup.sh && npm install`
6. Add your own EPUBs with `./lib <book.epub>`
7. Enable GitHub Pages (Actions source) in repo settings

## License

MIT
