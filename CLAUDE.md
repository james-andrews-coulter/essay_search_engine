# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Quick Start

### Common Commands

**Development**:
```bash
npm run dev      # Start dev server at http://localhost:5173
npm run build    # Build for production (outputs to dist/)
npm run preview  # Preview production build
```

**Book Management**:
```bash
./lib book.epub           # Process and add a book (requires Ollama)
./lib --list              # List all books in library
./lib --delete "Title"    # Delete a book by title
./lib --sync              # Sync books to web (generate embeddings)
```

**Setup**:
```bash
./setup.sh    # Creates venv, installs Python dependencies
npm install   # Installs Node dependencies
```

**Prerequisites**: Python 3.10+, Node.js 20+, Ollama with `qwen2.5:7b` model

## Architecture

Two-phase system: (1) EPUB → Markdown → Semantic chunks → AI tags via `process_book.py`, (2) Generate embeddings + metadata via `sync/build.py`, (3) Client-side semantic search using BGE-large-en-v1.5 model (327MB) running in browser. All search is client-side, no backend. Deploys to GitHub Pages.

## Project Structure

```
essay_search_engine/
├── lib                      # CLI entry point
├── process_book.py          # EPUB processing pipeline
├── setup.sh                 # Installation script
├── requirements.txt         # Python dependencies
├── private/                 # Local data (gitignored)
│   ├── books_metadata.json
│   └── books/<title>/
│       ├── chunks.json
│       └── chunk_NNN.md
├── sync/
│   └── build.py             # Unified build script (metadata + embeddings + tags)
├── src/
│   ├── search.js            # SearchEngine class (cosine similarity + ranked boosting)
│   ├── main.js              # UI logic and pagination
│   ├── service-worker.js    # Offline caching (cache-first)
│   └── styles.css           # Minimal CSS
├── public/
│   ├── data/
│   │   ├── metadata.json    # Book/chunk metadata with full content
│   │   ├── embeddings.json  # Pre-computed embeddings (15MB)
│   │   └── tags.json        # Tag index
│   └── models/              # Self-hosted BGE model files
├── index.html               # Search page
└── chunk.html               # Dynamic chunk viewer (renders from metadata.json)
```

## Critical Constraints

1. **Vite base path** (`vite.config.js`): MUST match GitHub repo name (`/essay_search_engine/`). If repo name changes, update this.

2. **Embedding normalization**: Python and JavaScript MUST both normalize embeddings:
   - Python: `normalize_embeddings=True` in `sync/build.py`
   - JavaScript: `normalize: true` in `src/search.js`
   Mismatch breaks search quality.

3. **Model files**: Self-hosted at `public/models/Xenova/bge-large-en-v1.5/` for offline support. 321MB .onnx file tracked via Git LFS.

4. **Search ranking** (src/search.js:111-149):
   - Book Title: +50% exact, +40% partial (highest priority)
   - Chapter Title: +40% exact, +30% partial
   - Tags: +30% exact, +15% partial
   - Tiered filtering: 0.15-0.65 similarity thresholds by match type

5. **Chunk rendering**: Single `chunk.html` renders all chunks dynamically from `metadata.json` using marked.js. No static HTML files.

6. **Service Worker**: Cache-first strategy. Version bumps trigger new cache. Pre-caches model files + data for offline.

## Critical Files

- `process_book.py` (1057 lines): EPUB processing, chapter detection (5 patterns), semantic chunking, AI tag generation
- `sync/build.py`: Generates metadata.json, embeddings.json, tags.json + tags.html
- `src/search.js`: SearchEngine class with cosine similarity + multi-attribute ranked boosting
- `vite.config.js`: base path MUST match repo name

## Workflow

```
./lib book.epub    →  EPUB → Markdown → Chunks → AI Tags → private/books/
./lib --sync       →  Generate embeddings + metadata → public/data/
git push           →  GitHub Actions deploys to Pages
```

## Key Behaviors

- **Chunking**: LlamaIndex MarkdownNodeParser splits by headers. Aggressive filtering removes TOC, bibliography, copyright, dedications.
- **Tags**: Ollama qwen2.5:7b generates 3-5 single-word semantic tags per chunk. Critical for 1-2 word queries.
- **Search**: Query → embed → cosine similarity → multi-attribute boosting → tiered filtering → paginate (25/page)
- **Offline**: Service Worker caches model + data + chunks. Works fully offline after first load.
