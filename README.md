# Essay Search Engine

A complete solution for processing personal essay collections and searching them via a mobile-accessible semantic search engine.

## Features

- **Complete Pipeline**: EPUB → Chunks → Embeddings → Web Search (all in one repo)
- **Semantic Search**: Uses BGE-large-en-v1.5 for intelligent, meaning-based search
- **AI Tag Generation**: Ollama-powered semantic tags for better keyword matching
- **Mobile-Friendly**: Responsive design accessible from any device
- **Offline-First**: Model and data cached in browser after initial load
- **GitHub Pages**: Static deployment, no server required

## Quick Start

### Prerequisites

- Python 3.9+
- Node.js 20+
- Ollama installed and running (for book processing)

### Installation

1. Clone and run setup:
```bash
git clone <repo-url>
cd essay_search_engine
./setup.sh
```

2. Install frontend dependencies:
```bash
npm install
```

3. Ensure Ollama is running with required model:
```bash
ollama serve
ollama pull qwen2.5:7b
```

### Adding Books

Process an EPUB file:
```bash
./lib path/to/book.epub
```

This will:
- Extract and convert EPUB to markdown
- Detect chapters intelligently
- Create semantic chunks (~500 words each)
- Generate AI tags using Ollama
- Save to `./private/books/`

### Syncing to Web

Generate embeddings and web assets (incremental):
```bash
./lib --sync
```

This will **intelligently sync only new or updated books**:
- Detects which books have changed since last sync
- Only generates embeddings for new chunks (~30 seconds for 1 book)
- Merges with existing data
- Creates HTML pages for new chunks

**Force sync all books** (if needed):
```bash
./lib --sync --force
```

This regenerates everything from scratch (~2-3 minutes for 17 books)

### Testing Locally

```bash
npm run dev
```

Visit http://localhost:5173 to test search.

### Deploying

```bash
npm run build      # Build for production
git add public/    # Add generated data
git commit -m "Update books"
git push           # Auto-deploys via GitHub Actions
```

## Commands

```bash
./lib <book.epub>       # Process and add a book
./lib --list            # List all indexed books
./lib --delete <book>   # Delete a book
./lib --sync            # Sync to web (incremental - fast!)
./lib --sync --force    # Force sync all books
./lib --help            # Show all commands

npm run dev             # Run local dev server
npm run build           # Build for production
```

## Project Structure

```
essay_search_engine/
├── lib                    # CLI entry point
├── process_book.py        # Book processing pipeline
├── setup.sh               # Installation script
├── requirements.txt       # Python dependencies
│
├── private/               # Local data (gitignored)
│   ├── books_metadata.json
│   └── books/<title>/
│       ├── chunks.json
│       └── chunk_NNN.md
│
├── sync/                  # Web sync scripts
│   ├── sync.py
│   └── embed_chunks.py
│
├── src/                   # Frontend source
│   ├── main.js
│   ├── search.js
│   └── styles.css
│
├── public/                # Web assets (committed)
│   ├── data/
│   │   ├── metadata.json
│   │   └── embeddings.json
│   └── chunks/
│       └── chunk_NNN.html
│
└── index.html             # Search page
```

## Workflow

### Complete Workflow (Adding a New Book)

```bash
# 1. Process book
./lib ~/Downloads/my_book.epub

# 2. Sync to web
./lib --sync

# 3. Test locally
npm run dev

# 4. Build and deploy
npm run build
git add public/
git commit -m "Add My Book"
git push
```

### Updating Existing Content

If you re-process a book, it will replace the old version:
```bash
./lib ~/Downloads/my_book.epub  # Will prompt to replace
./lib --sync                     # Regenerate embeddings
```

## How It Works

### 1. Book Processing (`process_book.py`)

- **Input**: EPUB file
- **Pipeline**:
  1. EPUB → Markdown conversion (BeautifulSoup)
  2. Chapter detection & normalization
  3. Semantic chunking (LlamaIndex)
  4. Aggressive content filtering (removes TOC, metadata, etc.)
  5. AI tag generation (Ollama qwen2.5:7b)
  6. Save to `./private/books/`

### 2. Web Sync (`sync/`)

- **Input**: `./private/books_metadata.json` + chunks
- **Pipeline**:
  1. Load all chunks
  2. Generate embeddings (BAAI/bge-large-en-v1.5, 1024-dim)
  3. Create `metadata.json` and `embeddings.json`
  4. Generate static HTML for each chunk
  5. Save to `./public/`

### 3. Browser Search (`src/`)

- **Pipeline**:
  1. Load metadata (219KB) and embeddings (15MB)
  2. Load BGE-large-en-v1.5 model (327MB, cached)
  3. User types query
  4. Embed query (1024-dim)
  5. Compute cosine similarity with all chunks
  6. Apply tag boosting (+20% exact, +10% partial)
  7. Sort by score, filter < 0.3
  8. Display top 20 results

## Performance

**Initial Load (First Visit)**:
- Model: 327MB (cached for ~7 days)
- Data: 15MB
- Time: 10-15s on WiFi, 20-30s on 4G

**Subsequent Visits**:
- Model: 0KB (cached)
- Data: 15MB (checks for updates)
- Time: 2-3s

**Search**:
- First query: 5-10s (model initialization)
- Subsequent: ~1s

**Book Processing**:
- ~2-5 minutes per book (mostly Ollama tag generation)

**Sync to Web (Incremental)**:
- First sync: ~2-3 minutes for all books
- Subsequent syncs: ~30 seconds per new book
- Skips unchanged books automatically
- Force sync: ~2-3 minutes for all books

## Configuration

### Change Result Count

Edit `src/main.js`:
```javascript
const results = await searchEngine.search(query, 20); // Change 20
```

### Change Score Threshold

Edit `src/search.js`:
```javascript
results = results.filter(r => r.score >= 0.3); // Change 0.3
```

### Customize Tag Boosting

Edit `src/search.js`:
```javascript
// Exact tag match
result.score += 0.20; // Change 0.20

// Partial tag match
result.score += 0.10; // Change 0.10
```

## Troubleshooting

### Ollama Not Running

```
❌ Error: Cannot connect to Ollama (is it running?)
```

**Solution**: Start Ollama:
```bash
ollama serve
```

### Model Not Found

```
⚠️ qwen2.5:7b model not found
```

**Solution**: Pull the model:
```bash
ollama pull qwen2.5:7b
```

### Sync Fails

```
ERROR: ./private/books_metadata.json not found
```

**Solution**: Add books first:
```bash
./lib path/to/book.epub
```

### Search Returns No Results

**Solutions**:
- Try more general keywords
- Lower score threshold in `src/search.js`
- Check browser console for errors

### Model Download Fails (Browser)

**Solutions**:
- Check internet connection
- Clear browser cache
- Try different browser
- Wait and retry (CDN might be down)

## GitHub Pages Setup

### Initial Setup

1. Go to repository **Settings → Pages**
2. Source: **"GitHub Actions"**
3. Save

### Deployment

Every push to `main` triggers auto-deployment:
```bash
git push origin main
# Wait ~2-3 minutes for build
# Visit: https://your-username.github.io/essay_search_engine/
```

## Architecture

- **Frontend**: Vanilla JavaScript + Vite + Tailwind CSS
- **Backend**: Python (local processing only, no server)
- **AI Models**:
  - Embedding: BAAI/bge-large-en-v1.5 (Python & Browser)
  - Tagging: Ollama qwen2.5:7b (local inference)
- **Deployment**: GitHub Pages (static hosting)
- **Storage**: ~15MB embeddings + 327MB model (browser cache)

## Key Design Decisions

### Why BGE-large-en-v1.5?
- Highest quality embeddings (1024-dim)
- Consistent with original TUI
- Proven to work well for essay search
- Worth the 327MB download for quality

### Why Ollama for Tags?
- Local inference (privacy)
- High-quality semantic tags
- Temperature 0.3 for consistency
- Tags boost 1-2 word queries significantly

### Why Pre-computed Embeddings?
- Only embed 1 query vs 672 chunks per search
- Faster search after model loads
- 15MB transfer is acceptable
- Enables GitHub Pages deployment

### Why Remove FAISS/BM25?
- Web doesn't support FAISS
- Pure semantic search works well
- Simpler architecture
- Tag boosting compensates for exact matches

### Why Incremental Sync?
- Only processes new/changed books
- 30 seconds vs 3 minutes for typical updates
- Tracks sync state automatically
- Force mode available when needed

## Documentation

- **CLAUDE.md**: Detailed implementation documentation
- **Plan**: `/Users/jamesalexander/.claude/plans/crystalline-crafting-stearns.md`

## License

Private project for personal use.

## Credits

- **Embedding Model**: [BAAI/bge-large-en-v1.5](https://huggingface.co/BAAI/bge-large-en-v1.5)
- **Tagging Model**: [Ollama qwen2.5:7b](https://ollama.ai)
- **Browser ML**: [Transformers.js](https://github.com/xenova/transformers.js)
- **Chunking**: [LlamaIndex](https://www.llamaindex.ai/)
- **UI**: Tailwind CSS
- **Build**: Vite
