# Minimal Refactoring Plan - 2026-01-16

**Goal:** Refactor/simplify/lighten codebase to its essential/lean-most state while preserving full offline search functionality.

**Core Philosophy:** Strip away everything that doesn't directly serve offline semantic search with tag navigation.

---

## High-Level Changes

### What Gets Removed
- 1,241 static chunk HTML files (8.3MB) → Dynamic markdown rendering
- 3 one-time migration scripts (8KB) → Delete entirely
- Service worker update notifications/checking (~150 lines) → Basic caching only
- Main.js update UI and online/offline tracking (~100 lines) → Remove
- All documentation folders (112KB) → CLAUDE.md is single source of truth
- Old worktrees (1.3GB) → Delete merged feature branches
- Test screenshots folder (1.4MB) → Delete

### What Gets Simplified
- Chunk viewer: Single page that renders markdown dynamically from metadata
- Service worker: Cache assets, serve offline, nothing else (~100 lines, was 338)
- Sync workflow: Merge two scripts into one, remove HTML generation
- UI: Brutally minimal, compact for mobile (4-5 results visible vs 1 currently)

### What Stays Unchanged
- BGE-large-en-v1.5 model (337MB) - Quality requirement
- Full offline functionality - Core constraint
- Tag browsing/navigation - Essential feature
- Book processing pipeline (process_book.py)
- Embeddings generation
- Search algorithm and relevance boosting

### Expected Impact
- Repository: -1,245 files, -1.3GB
- Codebase: ~470 fewer lines
- Mobile UX: 4-5 results per screen (was 1)
- Deployment: Faster (fewer files)
- Maintenance: Simpler (no HTML templates)

---

## Complete File & Folder Audit

Every item justified or deleted.

### ✅ KEEP - Core Required

**Folders:**
- `.git/` - Version control
- `.github/` - GitHub Actions deployment
- `.claude/` - Custom commands (4KB)
- `node_modules/` - Build dependencies (gitignored)
- `venv/` - Python environment (gitignored)
- `private/` - Source book data (gitignored)
- `public/` - Web assets (but cleanup: delete chunks/)
- `src/` - Frontend source
- `sync/` - Build scripts (will be consolidated)

**Root files:**
- `.gitattributes` - Git LFS for model files
- `.gitignore` - Ignore rules
- `CLAUDE.md` - Single source of truth
- `index.html` - Main search page
- `lib` - CLI entry point
- `setup.sh` - Setup script
- `process_book.py` - Book processing
- `package.json`, `package-lock.json` - npm deps
- `requirements.txt` - Python deps (will be trimmed)
- `vite.config.js` - Build config

### ❌ DELETE - Unnecessary

**Folders:**
- `.worktrees/` - Old feature branches (1.3GB)
- `.playwright-mcp/` - Old test screenshots (1.4MB)
- `docs/` - All markdown files (112KB)
- `public/chunks/` - 1,241 HTML files (8.3MB)

**Root files:**
- `README.md` - Redundant with CLAUDE.md
- `TODO.md` - Redundant with CLAUDE.md
- `postcss.config.js` - Empty Tailwind leftover
- `migrate_add_doc_ids.py` - One-time migration
- `update_chunks.py` - One-time migration
- `sync/fix_doc_ids.py` - One-time migration

### 🔧 OPTIMIZE - Dependencies

**npm (package.json):**
- ✅ `@xenova/transformers` - Required for browser ML
- ✅ `vite` - Required for build
- **Total: 2 packages (already minimal)**

**Python (requirements.txt):**
- ✅ `ebooklib` - EPUB extraction
- ✅ `beautifulsoup4` - HTML parsing
- ✅ `lxml` - Faster parser
- ✅ `llama-index-core` - Semantic chunking
- ✅ `sentence-transformers` - Embeddings
- ✅ `torch` - Required by sentence-transformers (heavy but unavoidable)
- ❌ `markdown` - Used ONLY for chunk HTML generation → DELETE
- ❌ `pyyaml` - Used to read chunk .md frontmatter → DELETE
- ✅ `requests` - Ollama API client

**Savings: 2 Python dependencies removed**

---

## Architecture Changes

### 1. Dynamic Chunk Rendering

**Current Architecture:**
```
sync.py generates: chunk_000.html ... chunk_1240.html (8.3MB)
User clicks result → Navigate to /chunks/chunk_NNN.html
Browser loads pre-rendered HTML
```

**New Architecture:**
```
sync/build.py generates: metadata.json only (includes full markdown)
User clicks result → Navigate to /chunk.html?id=NNN
JavaScript reads metadata.json[NNN], renders markdown to HTML
Service worker caches metadata.json for offline
```

**Implementation:**
- Single `chunk.html` page (replaces 1,241 files)
- Simple markdown renderer (~100 lines custom code OR use marked.js ~50KB)
- Read chunk from metadata.json by ID
- No prev/next navigation (removed - never displays)
- Works offline (metadata already cached)

**Trade-off:**
- Adds ~50-100KB code/library
- Slightly slower page load (parse markdown in browser)
- But eliminates 1,241 files and simplifies sync

### 2. Simplified Service Worker

**Current (338 lines):**
- Cache assets on install
- Serve from cache offline
- Check for updates every 5 minutes
- Notify user of updates
- Handle manual update trigger
- Track cache versions

**New (~100 lines):**
- Cache assets on install (models, data, JS, CSS, chunk.html)
- Serve from cache offline
- Update cache automatically on SW update (no user notification)
- Cache version tracking only

**What gets removed:**
- Update notification UI (~50 lines in main.js)
- Periodic update checks (~20 lines)
- Manual update button and logic (~30 lines)
- Online/offline status tracking (~20 lines)
- Message passing between SW and page (~30 lines)

### 3. Consolidated Sync Scripts

**Current:**
```
sync/sync.py:
- Reads chunks from private/books/
- Generates metadata.json
- Generates tags.json
- Generates 1,241 HTML files (uses markdown + yaml libraries)
- Calls embed_chunks.py

sync/embed_chunks.py:
- Reads chunks from private/books/
- Generates embeddings.json
```

**New (merged to sync/build.py):**
```python
sync/build.py:
- Reads chunks from private/books/ (once)
- Generates metadata.json (includes full markdown, no YAML parsing)
- Generates tags.json
- Generates embeddings.json
- Single pass, no HTML generation
```

**Benefits:**
- One script instead of two
- Read chunks only once (not twice)
- Remove markdown/yaml dependencies
- Simpler `./lib --sync` command

### 4. Updated Data Structure

**Current metadata.json chunk:**
```json
{
  "chunk_id": 0,
  "doc_id": 123,
  "book_title": "How to Travel",
  "chapter_title": "Introduction",
  "tags": "travel, adventure, exploration",
  "content_preview": "First 200 chars...",
  "word_count": 508,
  "char_count": 3041,
  "author": "Alain de Botton"
}
```

**New metadata.json chunk:**
```json
{
  "chunk_id": 0,
  "book_title": "How to Travel",
  "chapter_title": "Introduction",
  "tags": "travel, adventure, exploration",
  "content": "## Introduction\n\nFull markdown content here..."
}
```

**Changes:**
- Add `content` field (full markdown)
- Remove `doc_id` (prev/next navigation removed)
- Remove `content_preview` (not needed)
- Remove `word_count` (not used)
- Remove `char_count` (not used)
- Remove `author` (not used)

**Size impact:** ~5.2MB → ~8-10MB (acceptable, already loading 25MB embeddings)

---

## Minimal & Compact UI Redesign

### Remove Unnecessary Features

**Features removed:**
- ❌ Prev/Next chunk navigation - Never displays
- ❌ Match score display - Visual clutter
- ❌ Verbose status messages - Keep minimal
- ❌ Result count text - Visual clutter
- ❌ Word count, char count - Not used
- ❌ Author name - Not used

### Aggressively Compact Mobile Layout

**Goal: Fit 4-5 results on mobile portrait (vs current 1)**

**Header (minimal):**
```html
<h1>Search</h1>
<div class="search-row">
  <input type="text" placeholder="Search...">
  <button>Go</button>
</div>
```

**Result card (tight):**
```html
<article class="result">
  <h2>Chapter Title</h2>
  <div class="meta">Book Title • tag1, tag2</div>
</article>
```

**CSS strategy:**
- H1: 18px (reduce from current)
- Search input: 16px, minimal padding (8px)
- Button: Compact, same row as input
- Result h2 (chapter): 14px, line-height 1.2
- Meta text (book/tags): 12px, line-height 1.3
- Result padding: 8px (reduce from current)
- Result margin: 4px (reduce from current)
- Tags: Inline, subtle gray, no chips/badges

**Remove entirely:**
- Score badges
- "Search across X books..." copy
- "Found X results" text
- Decorative borders/shadows on results
- Extra whitespace

**Expected: 4-5 results visible on iPhone portrait mode**

---

## Implementation Order

### Phase 1: Deletions (Safe, reversible via git)
1. Delete `.worktrees/` folder (1.3GB)
2. Delete `.playwright-mcp/` folder (1.4MB)
3. Delete `docs/` folder (112KB)
4. Delete `public/chunks/` folder (8.3MB, 1,241 files)
5. Delete migration scripts (migrate_add_doc_ids.py, update_chunks.py, sync/fix_doc_ids.py)
6. Delete `README.md`, `TODO.md`, `postcss.config.js`

### Phase 2: Dependencies
1. Remove `markdown` and `pyyaml` from requirements.txt
2. Keep package.json as-is (already minimal)

### Phase 3: Backend Refactoring
1. Merge `sync/sync.py` + `sync/embed_chunks.py` → `sync/build.py`
2. Update metadata generation (remove word_count, char_count, author, doc_id, content_preview)
3. Add full `content` field to metadata
4. Remove HTML chunk generation code
5. Remove markdown/yaml imports

### Phase 4: Frontend - Chunk Viewer
1. Create `chunk.html` (single page for all chunks)
2. Add simple markdown renderer (custom ~100 lines or use marked.js ~50KB)
3. Read chunk from metadata by URL param `?id=NNN`
4. Remove prev/next navigation
5. Style for Safari Reader mode compatibility

### Phase 5: Frontend - Compact UI
1. Simplify `index.html` header (remove verbose copy)
2. Search button on same row as input
3. Remove score display from results
4. Aggressive mobile CSS: smaller fonts, tighter spacing, minimal padding
5. Target: 4-5 results visible on mobile portrait

### Phase 6: Service Worker Simplification
1. Remove update notification code (~50 lines)
2. Remove periodic update checks
3. Remove manual update UI
4. Keep only: cache on install, serve offline, auto-update on SW change
5. Update `main.js` to remove update UI logic (~100 lines)

### Phase 7: Documentation
1. Update `CLAUDE.md` with all changes
2. Document new architecture
3. Update commands/workflow
4. Delete this REFACTOR_PLAN.md (temporary file)

---

## Expected Final State

### Repository Size
- Before: ~380MB + 1.3GB worktrees = 1.68GB
- After: ~375MB (mostly model files, unavoidable)
- **Savings: 1.3GB (77% reduction in repo size)**

### File Count
- Before: ~1,270 committed files
- After: ~25 committed files
- **Savings: 1,245 files (98% reduction)**

### Code Complexity
- JavaScript: 1,139 lines → ~850 lines (-25%)
- Python: 2,032 lines → ~1,850 lines (-9%)
- Total: 3,171 lines → ~2,700 lines (-15%)

### Dependencies
- npm: 2 packages (unchanged, already minimal)
- Python: 10 packages → 8 packages (-20%)

### User-Facing Improvements
- Mobile: 1 result per screen → 4-5 results per screen (400% improvement)
- Cleaner, more focused UI
- Simpler mental model (no HTML generation, just data)
- Faster sync (merged scripts, no HTML generation)

### Offline Functionality
- ✅ Fully preserved (primary constraint met)
- metadata.json cached by service worker
- Dynamic rendering works offline

---

## Success Criteria

1. ✅ Full offline search functionality preserved
2. ✅ Repository size reduced by >70%
3. ✅ Mobile displays 4-5 results per screen
4. ✅ Codebase simplified (fewer files, fewer dependencies)
5. ✅ CLAUDE.md is single source of truth
6. ✅ No feature regression (tag navigation still works)
7. ✅ Deployment still works via GitHub Actions

---

**End of Refactoring Plan**
