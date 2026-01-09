# CLAUDE.md - Implementation Documentation

This document explains the implementation decisions, architecture, and context for this project. It's designed to help future Claude sessions (or developers) understand and maintain this codebase.

## Recent Updates

### Chunking Fix (2026-01-09)

**Issue**: Books with numbered subsections containing punctuation were creating abnormally large chunks (7K-12K words vs expected ~500 words).

**Root Cause**:
- Pattern 2 regex failed on titles with `&` symbol: "1. Trauma & anxiety"
- No pattern existed for ALL-CAPS subsections: "SELF-HATRED & ANXIETY"
- These subsections weren't converted to headers, causing MarkdownNodeParser to treat multiple sections as one chunk

**Solution Implemented**:
1. **Updated Pattern 2** (line 165): Allow punctuation (`&`, `-`, `:`, `,`) in numbered titles
2. **Added Pattern 5** (lines 192-204): Detect ALL-CAPS subsections (8-60 chars, 70%+ letters, with validator)
3. **Added validator support** (lines 222-223): Check validators before converting patterns to headers
4. **Updated markdown normalization** (lines 269-271): Mirror HTML patterns for fallback layer
5. **Fixed sync script** (sync/sync.py line 144): Handle chunks without `safe_title` field

**Results**:
- **Anxiety**: 6 → 28 chunks (avg 3,866 → 826 words, max 11,988 → 2,812)
- **A Therapeutic Journey**: 11 → 69 chunks (avg 6,363 → 1,198 words)
- **Total chunks**: 672 → 758 (+13%)

**Impact**: More granular search results, better subsection detection, improved search relevance for 1-2 word queries.

## Repository Consolidation (2026-01-08)

**Important**: This repository consolidates two previously separate projects:
- `book-library-tui` (book processing) → now `process_book.py` + `./lib` command
- `essay_search_engine` (web search) → remains as `src/` + web deployment

**Changes Made**:
- All book data moved from `~/Desktop/unified_library/` to `./private/` (gitignored)
- Removed FAISS/BM25 hybrid search (web uses pure semantic search)
- Ollama now required (not optional) for book processing
- Single unified workflow: `./lib book.epub` → `./lib --sync` → web deployment

## Project Context

**Goal**: Complete solution for processing personal essay collections and making them searchable via mobile-accessible web interface.

**Unified Workflow**:
1. **Book Processing** (`process_book.py`): EPUB → Markdown → Semantic Chunks → AI Tags
2. **Web Sync** (`sync/`): Generate embeddings → Create HTML chunks → Build search data
3. **Web App** (`src/`): Client-side semantic search with tag boosting
4. **Deployment**: Auto-deploy to GitHub Pages via GitHub Actions

**Requirements**:
1. Same search quality as original TUI (explicit user requirement)
2. Mobile accessible (primary goal)
3. Static site (GitHub Pages)
4. Automated workflow
5. Client-side semantic search
6. User typically searches with 1-2 word queries

## Key Design Decisions

### 1. Model Selection: BGE-large-en-v1.5 (Quality Over Speed)

**Decision**: Use Xenova/bge-large-en-v1.5 (327MB quantized, 1024-dim)

**Why**:
- User explicitly requested maximum search quality
- Same model as their TUI for consistency
- Proven to work well for their use case
- Tag boosting already implemented in TUI

**Trade-off**:
- 327MB download on first use (vs 23MB for smaller models)
- 5-10s first query (vs 2-3s)
- User accepted: "I don't mind waiting longer for queries"

**Implementation**:
```javascript
// src/search.js
const embedder = await pipeline('feature-extraction', 'Xenova/bge-large-en-v1.5');
```

### 2. Pre-computed Embeddings (Hybrid Approach)

**Decision**: Generate embeddings offline (Python), only embed queries in browser (JavaScript)

**Why**:
- Only need to embed 1 query instead of 758 chunks per search
- Faster search after model loads
- Smaller data transfer (15MB vs reprocessing all chunks)

**Trade-off**:
- Requires sync script when content changes
- Two embedding contexts (Python + JS)

**Implementation**:
- Python: `sentence-transformers` with BAAI/bge-large-en-v1.5
- JavaScript: Transformers.js with Xenova/bge-large-en-v1.5 (quantized)
- Both produce 1024-dim normalized embeddings

### 3. Tag Boosting (Critical for User's Search Style)

**Decision**: Boost scores by 20% for exact tag matches, 10% for partial

**Why**:
- User typically searches with 1-2 words ("solitude", "jealousy")
- Tags are AI-generated semantic labels (Ollama qwen2.5:7b)
- Already proven effective in TUI

**Implementation**:
```javascript
// src/search.js
// Exact tag match: +20% score
if (tags.some(tag => tag === queryLower)) {
  result.score += 0.20;
}
// Partial tag match: +10% score
else if (tags.some(tag => tag.includes(queryLower) || queryLower.includes(tag))) {
  result.score += 0.10;
}
```

### 4. Vanilla JavaScript (No Framework)

**Decision**: Use vanilla JS + Vite instead of React/Vue/Svelte

**Why**:
- Smaller bundle size (~50KB vs ~200KB)
- Simpler maintenance for static site
- No framework complexity needed
- Model download is the bottleneck, not JS bundle

**Trade-off**:
- More manual DOM manipulation
- Less component reusability

### 5. Score Threshold: 0.3

**Decision**: Filter out results with similarity score < 0.3

**Why**:
- 0.3 is a reasonable threshold for semantic similarity
- Prevents completely irrelevant results
- Can be adjusted if needed

**Location to adjust**: `src/search.js:142`

## Architecture

### Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    Step 1: Process Book                      │
│                    (./lib book.epub)                         │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  Input: book.epub                                            │
│                                                               │
│          ↓ process_book.py                                   │
│                                                               │
│  1. EPUB → Markdown conversion                               │
│  2. Chapter detection & normalization                        │
│  3. Semantic chunking (LlamaIndex)                           │
│  4. Aggressive content filtering                             │
│  5. AI tag generation (Ollama qwen2.5:7b)                    │
│  6. Save to ./private/books/<title>/                         │
│     - chunks.json                                            │
│     - chunk_NNN.md (with YAML frontmatter)                   │
│     - <title>.md (full book)                                 │
│  7. Update ./private/books_metadata.json                     │
│                                                               │
└─────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────┐
│                    Step 2: Sync to Web                       │
│                    (./lib --sync)                            │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  Input: ./private/books_metadata.json + chunks               │
│                                                               │
│          ↓ sync/sync.py                                      │
│                                                               │
│  1. Load all chunks from ./private/books/*/chunks.json       │
│  2. Generate ./public/data/metadata.json                     │
│  3. Generate ./public/chunks/chunk_NNN.html (static pages)   │
│                                                               │
│          ↓ sync/embed_chunks.py                              │
│                                                               │
│  4. Load sentence-transformers (BAAI/bge-large-en-v1.5)      │
│  5. Generate embeddings (1024-dim, normalized)               │
│  6. Save ./public/data/embeddings.json (~15MB)               │
│                                                               │
└─────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────┐
│                    Step 3: Browser Search                    │
│                    (Web App)                                 │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  1. Load metadata.json (219KB)                               │
│  2. Load embeddings.json (15MB)                              │
│  3. Load Xenova/bge-large-en-v1.5 (327MB, cached)            │
│  4. User types query                                         │
│  5. Embed query (1024-dim)                                   │
│  6. Compute cosine similarity with all embeddings            │
│  7. Apply tag boosting (+20% exact, +10% partial)            │
│  8. Sort by score, filter < 0.3, return top 20               │
│  9. Display results                                          │
│  10. Click → Navigate to chunk_NNN.html                      │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### File Structure

```
essay_search_engine/
├── lib                            # CLI entry point (shell script)
├── process_book.py                # Book processing pipeline
├── setup.sh                       # Installation script
├── requirements.txt               # Python dependencies
│
├── private/                       # Local data (gitignored)
│   ├── books_metadata.json        # Book catalog
│   └── books/<safe_title>/
│       ├── <title>.md             # Full book markdown
│       ├── chunks.json            # Chunk metadata
│       └── chunk_NNN.md           # Individual chunks
│
├── sync/                          # Web sync scripts
│   ├── sync.py                    # Generate metadata + HTML
│   └── embed_chunks.py            # Generate embeddings
│
├── src/                           # Frontend source
│   ├── search.js                  # SearchEngine class
│   ├── main.js                    # UI logic
│   └── styles.css                 # Tailwind base
│
├── public/                        # Web assets (committed)
│   ├── data/
│   │   ├── metadata.json          # Book/chunk metadata
│   │   └── embeddings.json        # Pre-computed embeddings
│   └── chunks/
│       └── chunk_NNN.html         # Static HTML pages
│
├── .github/workflows/
│   └── deploy.yml                 # GitHub Actions CI/CD
│
├── index.html                     # Search page
├── package.json                   # Node deps
├── vite.config.js                 # Vite config
├── tailwind.config.js             # Tailwind config
├── README.md                      # User documentation
└── CLAUDE.md                      # This file
```

## Book Processing Pipeline

### Overview

The `process_book.py` script handles the complete EPUB → searchable chunks pipeline. It performs intelligent content extraction, semantic chunking, and AI-powered tagging.

### Processing Stages

**Stage 1: EPUB Extraction (lines 258-305)**
- Uses `ebooklib` to parse EPUB files
- Extracts HTML from each document section
- Converts HTML → Markdown with `BeautifulSoup`
- Preserves structure: headings, paragraphs, lists, blockquotes

**Stage 2: Chapter Detection (lines 112-205)**
Two-layer normalization to handle inconsistent formatting:
- **HTML Layer**: Detects plain-text chapter markers in `<p>` tags, converts to proper `<h2>` headers
- **Markdown Layer**: Post-processes markdown to catch patterns missed in HTML
- **Patterns Detected**:
  - Pattern 1: Roman numerals (II, III, "II. Specialisation")
  - Pattern 2: Arabic numerals with punctuation (1., 2., "1. Trauma & anxiety")
  - Pattern 3: Chapter keywords ("Chapter One", "CHAPTER 1")
  - Pattern 4: Part keywords ("Part I", "PART TWO")
  - Pattern 5: ALL-CAPS subsections ("SELF-HATRED & ANXIETY", 8-60 chars, 70%+ letters)

**Stage 3: Semantic Chunking (lines 477-645)**
- Uses LlamaIndex's `MarkdownNodeParser` to split by headers/sections
- **Aggressive Filtering** removes non-content:
  - Minimum 30 words per chunk
  - Filters TOC (>40% list items)
  - Removes bibliography/references (citation patterns)
  - Removes copyright/ISBN metadata
  - Removes dedications, acknowledgments
  - Filters illustration lists, image credits
  - Removes publisher promotional content
  - **Result**: Only substantive content chunks

**Stage 4: AI Tag Generation (lines 308-392)**
- Calls Ollama API (local) with `qwen2.5:7b`
- For long chunks (>600 words): samples first 200 + middle 200 + last 200 words
- Generates 3-5 single-word semantic tags (e.g., "jealousy, comparison, envy")
- Temperature 0.3 for consistent tagging
- **Required**: Ollama must be running (no graceful degradation)

**Stage 5: Metadata Management (lines 713-767)**
- Updates `./private/books_metadata.json`
- Tracks contiguous doc_id ranges for each book
- Prevents duplicates by `safe_title` matching
- Supports book replacement

### Output Format

**Chunks JSON** (`./private/books/<title>/chunks.json`):
```json
{
  "chunk_id": 0,
  "content": "## Chapter Title\n\nMarkdown content...",
  "chapter_title": "Chapter Title",
  "tags": "tag1, tag2, tag3",
  "metadata": {
    "char_count": 3041,
    "word_count": 508,
    "chapter_title": "Chapter Title",
    "tags": "tag1, tag2, tag3",
    "title": "Book Title",
    "header_path": "/Book Title/Section/"
  }
}
```

**Individual Markdown Files** (`chunk_NNN.md`):
```markdown
---
chunk_id: 0
chapter_title: Chapter Title
tags: tag1, tag2, tag3
char_count: 3041
word_count: 508
---

## Chapter Title
Markdown content...
```

### Key Features

**Ollama Integration**:
- Check performed at startup (line 1057-1068)
- Verifies `qwen2.5:7b` model availability
- Clear error messages with setup instructions
- Processing fails if Ollama unavailable

**Content Quality**:
- Average chunk size: ~500 words (sweet spot for semantic search)
- Aggressive filtering ensures high signal-to-noise ratio
- Tags boost search relevance for 1-2 word queries

**Metadata Tracking**:
- `books_metadata.json` maintains doc_id ranges
- Enables efficient "previous/next chunk" navigation
- Supports book updates (removes old chunks, assigns new IDs)

## Critical Implementation Details

### 1. Embedding Compatibility

**CRITICAL**: Python and JavaScript embeddings MUST match

**Python** (sync/embed_chunks.py):
```python
model = SentenceTransformer('BAAI/bge-large-en-v1.5')
embeddings = model.encode(
    texts,
    batch_size=32,
    show_progress_bar=True,
    normalize_embeddings=True  # CRITICAL
)
```

**JavaScript** (src/search.js):
```javascript
const embedder = await pipeline('feature-extraction', 'Xenova/bge-large-en-v1.5');
const output = await embedder(query, {
  pooling: 'mean',
  normalize: true  // CRITICAL - must match Python
});
```

### 2. Cosine Similarity

**Why cosine similarity**:
- Normalized embeddings (unit vectors)
- Measures angle between vectors
- Range: -1 (opposite) to 1 (identical)
- Common in semantic search

**Implementation**:
```javascript
cosineSimilarity(vecA, vecB) {
  let dotProduct = 0;
  let normA = 0;
  let normB = 0;

  for (let i = 0; i < vecA.length; i++) {
    dotProduct += vecA[i] * vecB[i];
    normA += vecA[i] * vecA[i];
    normB += vecB[i] * vecB[i];
  }

  return dotProduct / (Math.sqrt(normA) * Math.sqrt(normB));
}
```

**Performance**: ~20-30ms for 758 comparisons (1024-dim each)

### 3. Chunk HTML Generation

**Why generate static HTML**:
- Fast page loads
- No markdown parsing in browser
- SEO-friendly (if needed later)
- Deep linking support

**Template** (sync/sync.py:140-220):
- Inline styles (no external CSS)
- Mobile-responsive
- Previous/Next navigation (same book only)
- Back to search button

### 4. Tag Format

**From TUI**: AI-generated tags via Ollama (qwen2.5:7b)
- Format: `"jealousy, comparison, inferiority, envy, insecurity, rivalry"`
- 3-5 single-word semantic tags per chunk
- Critical for boosting 1-2 word queries

**Processing**:
```javascript
const tags = chunk.tags
  .toLowerCase()
  .split(',')
  .map(t => t.trim())
  .filter(t => t.length > 0);
```

### 5. Vite Base Path

**CRITICAL**: Must match GitHub repo name

**vite.config.js**:
```javascript
export default defineConfig({
  base: '/essay_search_engine/',  // MUST match repo name
  // ...
});
```

**Used in**:
- Asset loading: `/essay_search_engine/data/metadata.json`
- Navigation: `/essay_search_engine/chunks/chunk_000.html`
- GitHub Pages URL: `https://username.github.io/essay_search_engine/`

**If repo name changes**: Update `vite.config.js` base path

## Common Issues & Solutions

### Issue 1: Search Returns No Results

**Causes**:
1. Score threshold too high
2. Model not initialized
3. Query too specific

**Solutions**:
1. Lower threshold in `src/search.js:142` (try 0.2 or 0.1)
2. Check browser console for errors
3. Try more general keywords

### Issue 2: Model Download Fails

**Causes**:
1. Network issues
2. Hugging Face CDN down
3. Browser cache issues

**Solutions**:
1. Check internet connection
2. Clear browser cache
3. Try different browser
4. Wait and retry (CDN might be temporarily down)

### Issue 3: Embeddings Don't Match

**Symptoms**: Results very different from TUI

**Causes**:
1. Different normalization
2. Different model versions
3. Text preprocessing differences

**Solution**:
1. Verify both use `normalize_embeddings=True` / `normalize: true`
2. Check model versions match (both should be v1.5)
3. Compare embedding shapes (both should be 1024)

### Issue 4: Sync Script Fails

**Causes**:
1. book-library-tui not set up
2. Missing Python dependencies
3. Ollama not running (not critical)

**Solutions**:
1. Verify `~/Desktop/unified_library/books_metadata.json` exists
2. Run `pip install -r sync/requirements.txt`
3. Ollama not required for sync (only for initial tag generation in TUI)

### Issue 5: GitHub Pages 404

**Causes**:
1. Wrong base path in vite.config.js
2. Pages not enabled
3. Build failed

**Solutions**:
1. Check base matches repo name
2. Settings → Pages → Source: GitHub Actions
3. Check Actions tab for build errors

## Performance Characteristics

### Initial Load (First Visit)

```
Component                Size        Time (WiFi)
─────────────────────────────────────────────────
HTML/CSS/JS             ~10KB       < 1s
metadata.json           219KB       < 1s
embeddings.json         15MB        1-2s
BGE-large model         327MB       8-10s
─────────────────────────────────────────────────
TOTAL                   ~342MB      10-15s
```

### Cached Load (Subsequent Visits)

```
Component                Size        Time
─────────────────────────────────────────
HTML/CSS/JS (cached)    ~10KB       < 1s
metadata.json (check)   0-219KB     < 1s
embeddings.json (new)   15MB        1-2s
Model (cached)          0KB         0s
─────────────────────────────────────────
TOTAL                   ~15MB       2-3s
```

### Search Performance

```
Operation               Time        Notes
──────────────────────────────────────────────────
First query             5-10s       Model init
Subsequent queries      ~1s         Just inference
Cosine similarity       20-30ms     758 comparisons
Tag boosting           < 5ms        String matching
Sort + filter          < 5ms        Array operations
──────────────────────────────────────────────────
TOTAL (after init)     ~1s
```

### Mobile Performance

```
Network     Initial Load    Search
──────────────────────────────────────
WiFi        10-15s          ~1s
4G          20-30s          ~1-2s
3G          60-90s          ~2-3s
```

## Maintenance Guide

### Adding New Books

1. **Process in TUI**:
   ```bash
   cd /Users/jamesalexander/book-library-tui
   ./lib add path/to/new_book.epub
   ```

2. **Sync to Web**:
   ```bash
   cd /Users/jamesalexander/essay_search_engine
   source venv/bin/activate
   python3 sync/sync.py
   # Wait ~2-3 minutes for embeddings
   ```

3. **Commit & Push**:
   ```bash
   git add public/
   git commit -m "Add [Book Title]"
   git push
   # GitHub Actions auto-deploys in ~2-3 minutes
   ```

### Updating Existing Books

Same as adding - sync script regenerates everything from source.

### Changing Search Behavior

**Adjust result count** (src/main.js:82):
```javascript
const results = await searchEngine.search(query, 20); // Change 20
```

**Adjust score threshold** (src/search.js:142):
```javascript
results = results.filter(r => r.score >= 0.3); // Change 0.3
```

**Adjust tag boosting** (src/search.js:124-133):
```javascript
// Exact match
result.score += 0.20; // Change 0.20

// Partial match
result.score += 0.10; // Change 0.10
```

### Debugging

**Browser Console**:
```javascript
// Check if initialized
console.log(searchEngine.isReady);

// Check metadata loaded
console.log(searchEngine.metadata);

// Check embeddings loaded
console.log(searchEngine.embeddings);

// Test search
searchEngine.search('solitude', 5).then(console.log);
```

**Python Sync**:
```bash
# Test with verbose output
python3 sync/sync.py 2>&1 | tee sync.log

# Check embeddings shape
python3 -c "
import json
with open('public/data/embeddings.json') as f:
    data = json.load(f)
    print(f'Model: {data[\"model\"]}')
    print(f'Dimensions: {data[\"dimensions\"]}')
    print(f'Chunks: {len(data[\"embeddings\"])}')
    print(f'First embedding length: {len(data[\"embeddings\"][0])}')
"
```

## Future Enhancements

### Near-term (Easy)

1. **Tag filtering**: Add UI to filter by specific tags
2. **Book filtering**: Add dropdown to filter by book
3. **Search history**: Use localStorage to save recent searches
4. **Dark mode**: Add theme toggle

### Medium-term (Moderate Effort)

1. **Offline support**: Add Service Worker for offline caching
2. **Hybrid search**: Combine semantic + BM25 keyword search
3. **Search within results**: Filter results after initial search
4. **Related chunks**: Show similar chunks based on embeddings

### Long-term (Complex)

1. **Incremental sync**: Only re-embed changed chunks
2. **Lazy loading**: Load embeddings by book as needed
3. **Compression**: Use binary format for embeddings (reduce ~50%)
4. **Backend**: Move to serverless for better performance

## Technical Constraints

### GitHub Pages Limitations

- **Static only**: No server-side code
- **Size limit**: 1GB per repo (we're ~350MB)
- **Build time**: 10 minutes max (we use ~2-3 min)
- **Bandwidth**: Soft limit, but unlikely to hit with personal use

### Browser Limitations

- **Memory**: 327MB model + 15MB data + browser overhead
- **Storage**: ~342MB in cache (browser-managed)
- **CORS**: Must serve from same origin (handled by Vite)

### Model Limitations

- **Token limit**: 512 tokens max per chunk (most chunks fit)
- **Language**: English only (BGE-large-en-v1.5)
- **Quantization**: 8-bit precision (minimal quality loss)

## Research Sources

This implementation was informed by:

1. **Model Documentation**:
   - [Xenova/bge-large-en-v1.5](https://huggingface.co/Xenova/bge-large-en-v1.5) - ONNX quantized model
   - [BAAI/bge-large-en-v1.5](https://huggingface.co/BAAI/bge-large-en-v1.5) - Original model

2. **Libraries**:
   - [Transformers.js](https://github.com/xenova/transformers.js) - Browser ML
   - [sentence-transformers](https://www.sbert.net/) - Python embeddings

3. **Reference Implementations**:
   - User's book-library-tui (tag boosting strategy)
   - SemanticFinder (client-side search pattern)

## Version History

### v1.1.0 (2026-01-09) - Current
- **Chunking improvements**: Fixed oversized chunk issue
- Added Pattern 5 (ALL-CAPS subsections detection)
- Enhanced Pattern 2 (allow punctuation in numbered titles)
- 758 chunks from 17 books (+13% from v1.0.0)
- Average chunk size improved: better granularity for subsections
- Fixed sync script safe_title handling

### v1.0.0 (2026-01-08)
- Initial implementation after repository consolidation
- BGE-large-en-v1.5 with 1024-dim embeddings
- 672 chunks from 16 books
- Tag boosting (+20% exact, +10% partial)
- Mobile-responsive UI
- GitHub Actions deployment

## Contact & Support

For issues or questions:
1. Check browser console (F12) for errors
2. Review this file for common issues
3. Check GitHub Actions for build errors
4. Verify source data in ./private/

---

*Last updated: 2026-01-09*
*Built by: Claude (Anthropic)*
*Model: claude-sonnet-4-5-20250929*
