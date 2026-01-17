# Keyword Search with Tag Autocomplete Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace 327MB semantic search with 19KB keyword/fuzzy search and add tag autocomplete UI with badge filtering.

**Architecture:** Replace @xenova/transformers with Fuse.js for lightweight keyword/fuzzy search. Add @tarekraafat/autocomplete.js for 2K tag autocomplete. Implement badge UI for exact tag filtering with AND logic. Remove model files and embeddings from cache.

**Tech Stack:** Fuse.js (9KB), @tarekraafat/autocomplete.js (10KB), Vite, Service Worker

---

## Task 1: Install Dependencies

**Files:**
- Modify: `package.json`

**Step 1: Install Fuse.js and autocomplete.js**

Run:
```bash
npm install fuse.js @tarekraafat/autocomplete.js
```

Expected output: Dependencies added to package.json

**Step 2: Remove @xenova/transformers**

Run:
```bash
npm uninstall @xenova/transformers
```

Expected: @xenova/transformers removed from package.json

**Step 3: Verify package.json**

Run:
```bash
cat package.json
```

Expected: Should show fuse.js and @tarekraafat/autocomplete.js in dependencies, no @xenova/transformers

**Step 4: Test build still works**

Run:
```bash
npm run build
```

Expected: Build succeeds (may have unused import warnings, will fix next)

**Step 5: Commit**

```bash
git add package.json package-lock.json
git commit -m "deps: replace transformers with fuse.js and autocomplete.js"
```

---

## Task 2: Rewrite SearchEngine with Fuse.js

**Files:**
- Modify: `src/search.js`

**Step 1: Replace imports and remove WASM config**

Replace lines 1-4:
```javascript
import Fuse from 'fuse.js';
```

Remove the entire env.backends configuration (was needed for transformers, not for Fuse.js).

**Step 2: Update constructor**

Replace lines 11-17 with:
```javascript
  constructor() {
    this.fuse = null;
    this.metadata = null;
    this.isLoading = false;
    this.isReady = false;
  }
```

**Step 3: Rewrite initialize method**

Replace lines 19-61 with:
```javascript
  /**
   * Initialize the search engine (load metadata only)
   * @param {Function} onProgress - Callback for progress updates
   */
  async initialize(onProgress = null) {
    if (this.isReady) return;
    if (this.isLoading) {
      throw new Error("Already initializing");
    }

    this.isLoading = true;

    try {
      // Load metadata only (no embeddings needed)
      if (onProgress) onProgress("Loading metadata...");
      const metadataResponse = await fetch(
        "/essay_search_engine/data/metadata.json",
      );
      this.metadata = await metadataResponse.json();

      // Initialize Fuse.js with weighted fields
      if (onProgress) onProgress("Initializing search...");
      this.fuse = new Fuse(this.metadata.chunks, {
        keys: [
          { name: 'book_title', weight: 0.4 },      // Highest priority
          { name: 'chapter_title', weight: 0.3 },   // Second priority
          { name: 'tags', weight: 0.2 },            // Third priority
          { name: 'content', weight: 0.1 }          // Lowest (avoids noise)
        ],
        threshold: 0.4,              // Match strictness (0.0 = exact, 1.0 = anything)
        ignoreLocation: true,        // Match anywhere in field
        minMatchCharLength: 2,       // Ignore single chars
        includeScore: true           // Include match score in results
      });

      if (onProgress) onProgress("Ready!");
      this.isReady = true;
    } catch (error) {
      this.isLoading = false;
      throw new Error(`Failed to initialize search engine: ${error.message}`);
    } finally {
      this.isLoading = false;
    }
  }
```

**Step 4: Remove cosineSimilarity method**

Delete lines 63-86 entirely (method not needed for keyword search).

**Step 5: Rewrite search method for Fuse.js**

Replace lines 88-207 with:
```javascript
  /**
   * Search for chunks matching the query with optional tag filtering
   * @param {string} query - Search query (keywords)
   * @param {Array<string>} tags - Array of exact tags to filter by (AND logic)
   * @param {number} limit - Maximum number of results (default: no limit)
   * @returns {Promise<Array>} - Array of search results with scores
   */
  async search(query, tags = [], limit = null) {
    if (!this.isReady) {
      throw new Error(
        "Search engine not initialized. Call initialize() first.",
      );
    }

    // Start with all chunks
    let results = this.metadata.chunks;

    // Step 1: Filter by tags (exact AND logic)
    if (tags.length > 0) {
      results = results.filter(chunk => {
        const chunkTags = chunk.tags?.split(',').map(t => t.trim()) || [];
        return tags.every(tag => chunkTags.includes(tag)); // ALL tags must match
      });
    }

    // Step 2: Fuzzy search within filtered results (if query exists)
    if (query && query.trim().length > 0) {
      const fuse = new Fuse(results, {
        keys: [
          { name: 'book_title', weight: 0.4 },
          { name: 'chapter_title', weight: 0.3 },
          { name: 'tags', weight: 0.2 },
          { name: 'content', weight: 0.1 }
        ],
        threshold: 0.4,
        ignoreLocation: true,
        minMatchCharLength: 2,
        includeScore: true
      });

      const fuseResults = fuse.search(query.trim());

      // Convert Fuse.js results format to our format
      results = fuseResults.map(result => ({
        chunk: result.item,
        score: 1 - result.score // Invert score (Fuse.js: 0=perfect, we want 1=perfect)
      }));
    } else {
      // No query, just return filtered results (from tag filtering)
      results = results.map(chunk => ({
        chunk: chunk,
        score: 1.0 // Perfect score for exact tag matches
      }));
    }

    return limit ? results.slice(0, limit) : results;
  }
```

**Step 6: Keep helper methods unchanged**

getTotalChunks() and getBooks() methods (lines 209-222) remain the same.

**Step 7: Add tag extraction method**

Add new method after getBooks():
```javascript
  /**
   * Extract all unique tags from metadata
   * @returns {Array<string>} - Sorted array of unique tags
   */
  getAllTags() {
    if (!this.metadata) return [];

    const tagSet = new Set();
    this.metadata.chunks.forEach(chunk => {
      if (chunk.tags) {
        chunk.tags.split(',').forEach(tag => {
          const trimmed = tag.trim();
          if (trimmed) tagSet.add(trimmed);
        });
      }
    });

    return Array.from(tagSet).sort();
  }
```

**Step 8: Test build**

Run:
```bash
npm run build
```

Expected: Build succeeds with no errors

**Step 9: Commit**

```bash
git add src/search.js
git commit -m "refactor: replace semantic search with Fuse.js keyword search"
```

---

## Task 3: Add Autocomplete CSS Dependency

**Files:**
- Modify: `src/main.js`

**Step 1: Add autocomplete CSS import**

Add after line 1 (after `import './styles.css';`):
```javascript
import '@tarekraafat/autocomplete.js/dist/css/autoComplete.css';
```

**Step 2: Test build**

Run:
```bash
npm run build
```

Expected: Build succeeds, autocomplete CSS bundled

**Step 3: Commit**

```bash
git add src/main.js
git commit -m "style: import autocomplete CSS"
```

---

## Task 4: Update main.js with Tag State Management

**Files:**
- Modify: `src/main.js`

**Step 1: Add autocomplete import**

Add after line 2:
```javascript
import autoComplete from '@tarekraafat/autocomplete.js';
```

**Step 2: Add tag state after searchEngine initialization**

Add after line 39 (after `let isInitialized = false;`):
```javascript
let selectedTags = new Set();
let allTags = [];
let autoCompleteInstance = null;
```

**Step 3: Add DOM element reference for badge container**

Add after line 45 (after `const resultsDiv = document.getElementById('results');`):
```javascript
const tagBadgesDiv = document.getElementById('tagBadges');
```

**Step 4: Create renderBadges function**

Add before the `initialize()` function (around line 52):
```javascript
/**
 * Render tag badges
 */
function renderBadges() {
  if (!tagBadgesDiv) return;

  if (selectedTags.size === 0) {
    tagBadgesDiv.innerHTML = '';
    return;
  }

  const badgesHtml = Array.from(selectedTags).map(tag => `
    <span class="badge" data-tag="${escapeHtml(tag)}">
      ${escapeHtml(tag)}
      <button type="button" class="badge-remove" aria-label="Remove ${escapeHtml(tag)}">×</button>
    </span>
  `).join('');

  tagBadgesDiv.innerHTML = badgesHtml;

  // Add remove handlers
  tagBadgesDiv.querySelectorAll('.badge-remove').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const badge = e.target.closest('.badge');
      const tag = badge.dataset.tag;
      selectedTags.delete(tag);
      renderBadges();

      // Re-run search if there was a previous query
      if (currentQuery || selectedTags.size > 0) {
        performSearch();
      }
    });
  });
}

/**
 * Add tag badge
 */
function addTagBadge(tag) {
  selectedTags.add(tag);
  renderBadges();
}
```

**Step 5: Update initialize function to extract tags and setup autocomplete**

Replace the initialize() function (lines 56-79) with:
```javascript
/**
 * Initialize the search engine
 */
async function initialize() {
  if (isInitialized) return;

  // Register Service Worker for offline support
  await registerServiceWorker();

  statusDiv.textContent = 'Loading...';

  try {
    await searchEngine.initialize((progress) => {
      statusDiv.textContent = progress;
    });

    // Extract all tags for autocomplete
    allTags = searchEngine.getAllTags();

    // Initialize autocomplete
    autoCompleteInstance = new autoComplete({
      selector: "#searchInput",
      data: {
        src: allTags,
        cache: true
      },
      resultsList: {
        maxResults: 15,
        noResults: true,
        element: (list, data) => {
          if (!data.results.length) {
            const message = document.createElement("div");
            message.setAttribute("class", "no_result");
            message.innerHTML = `<span>No tags found for "${data.query}"</span>`;
            list.appendChild(message);
          }
        }
      },
      resultItem: {
        highlight: true,
        element: (item, data) => {
          item.innerHTML = `tag:${data.value}`;
        }
      },
      events: {
        input: {
          selection: (event) => {
            const tag = event.detail.selection.value;
            addTagBadge(tag);
            searchInput.value = '';
            event.detail.event.preventDefault();
            performSearch();
          }
        }
      }
    });

    isInitialized = true;
    searchInput.disabled = false;
    searchButton.disabled = false;
    searchInput.focus();

    statusDiv.textContent = '';
  } catch (error) {
    console.error('Initialization error:', error);
    statusDiv.textContent = `Error: ${error.message}`;
  }
}
```

**Step 6: Update performSearch to pass tags**

Replace the performSearch() function (lines 84-130) with:
```javascript
/**
 * Perform search
 */
async function performSearch() {
  const query = searchInput.value.trim();

  // If no query and no tags, clear results
  if (!query && selectedTags.size === 0) {
    resultsDiv.innerHTML = '';
    allResults = [];
    currentQuery = '';
    statusDiv.textContent = '';
    return;
  }

  if (!isInitialized) {
    statusDiv.textContent = 'Please initialize the search engine first';
    return;
  }

  // Show loading state
  searchButton.disabled = true;
  statusDiv.textContent = 'Searching...';

  try {
    // Get all results with tag filtering
    const tags = Array.from(selectedTags);
    const results = await searchEngine.search(query, tags);

    // Hide loading state
    searchButton.disabled = false;

    if (results.length === 0) {
      const queryDesc = query && tags.length > 0
        ? `"${query}" with tags [${tags.join(', ')}]`
        : query
        ? `"${query}"`
        : `tags [${tags.join(', ')}]`;
      statusDiv.textContent = `No results found for ${queryDesc}`;
      resultsDiv.innerHTML = '<p>No results found. Try different keywords or tags.</p>';
      allResults = [];
      currentQuery = '';
      return;
    }

    // Store results and reset pagination
    allResults = results;
    currentPage = 1;
    currentQuery = query;

    // Render paginated results
    renderResults();
  } catch (error) {
    console.error('Search error:', error);
    statusDiv.textContent = `Search error: ${error.message}`;
    searchButton.disabled = false;
  }
}
```

**Step 7: Update URL parameter handling for tags**

Replace the DOMContentLoaded handler (lines 284-295) with:
```javascript
// Auto-initialize on page load and handle tag parameters
window.addEventListener('DOMContentLoaded', async () => {
  await initialize();

  // Check for tag parameter in URL
  const urlParams = new URLSearchParams(window.location.search);
  const tag = urlParams.get('tag');

  if (tag && isInitialized) {
    addTagBadge(tag);
    performSearch();
  }
});
```

**Step 8: Test build**

Run:
```bash
npm run build
```

Expected: Build succeeds

**Step 9: Commit**

```bash
git add src/main.js
git commit -m "feat: add tag autocomplete and badge state management"
```

---

## Task 5: Update HTML with Badge Container

**Files:**
- Modify: `index.html`

**Step 1: Add badge container before search input**

Find the search form (around line 20-25) and replace with:
```html
<div class="search-wrapper">
  <div id="tagBadges" class="tag-badges"></div>
  <div class="search-form">
    <input
      type="text"
      id="searchInput"
      placeholder="Search or add tags..."
      disabled
      autocomplete="off"
      aria-label="Search input"
    />
    <button id="searchButton" disabled>Search</button>
  </div>
</div>
```

**Step 2: Verify HTML structure**

Run:
```bash
cat index.html | grep -A 10 "search-wrapper"
```

Expected: Shows the new structure with tag-badges div

**Step 3: Test build**

Run:
```bash
npm run build
```

Expected: Build succeeds

**Step 4: Commit**

```bash
git add index.html
git commit -m "feat: add tag badge container to search UI"
```

---

## Task 6: Add Badge and Autocomplete Styles

**Files:**
- Modify: `src/styles.css`

**Step 1: Add badge styles**

Add at the end of the file (after line 114):
```css
/* Search wrapper */
.search-wrapper {
  margin-bottom: 1rem;
}

/* Tag badges */
.tag-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-bottom: 8px;
  min-height: 0;
}

.tag-badges:empty {
  margin-bottom: 0;
}

.badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: #e6f2ff;
  color: #0066cc;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 13px;
  border: 1px solid #b3d9ff;
}

.badge-remove {
  background: none;
  border: none;
  color: #0066cc;
  cursor: pointer;
  font-size: 16px;
  line-height: 1;
  padding: 0;
  margin: 0;
  min-height: auto;
  font-weight: bold;
}

.badge-remove:hover {
  background: none;
  color: #004080;
}

/* Search form */
.search-form {
  display: flex;
  gap: 4px;
}

.search-form input {
  flex: 1;
  padding: 0 12px;
  font-size: 16px;
}

.search-form button {
  padding: 0 16px;
  font-size: 14px;
}

/* Autocomplete overrides */
#autoComplete_list {
  position: absolute;
  z-index: 1000;
  background: white;
  border: 1px solid #ccc;
  border-radius: 4px;
  margin-top: 2px;
  max-height: 300px;
  overflow-y: auto;
  box-shadow: 0 2px 8px rgba(0,0,0,0.15);
}

#autoComplete_list ul {
  list-style: none;
  margin: 0;
  padding: 0;
}

#autoComplete_list li {
  padding: 8px 12px;
  cursor: pointer;
  font-size: 14px;
}

#autoComplete_list li:hover,
#autoComplete_list li[aria-selected="true"] {
  background: #f0f0f0;
}

#autoComplete_list .no_result {
  padding: 8px 12px;
  color: #999;
  font-size: 14px;
}

#autoComplete_list mark {
  background: #ffeb3b;
  color: inherit;
  font-weight: 600;
}
```

**Step 2: Test build**

Run:
```bash
npm run build
```

Expected: Build succeeds, CSS is bundled

**Step 3: Commit**

```bash
git add src/styles.css
git commit -m "style: add badge and autocomplete styles"
```

---

## Task 7: Update Service Worker Cache

**Files:**
- Modify: `src/service-worker.js`

**Step 1: Bump cache version**

Change line 2:
```javascript
const CACHE_VERSION = 'v8';
```

**Step 2: Remove model and embedding files from precache**

Replace PRECACHE_ASSETS array (lines 6-22) with:
```javascript
// Assets to pre-cache
const PRECACHE_ASSETS = [
  '/essay_search_engine/',
  '/essay_search_engine/index.html',
  '/essay_search_engine/chunk.html',
  '/essay_search_engine/tags.html',
  '/essay_search_engine/data/metadata.json',
  '/essay_search_engine/data/tags.json'
];
```

**Step 3: Verify removal**

Run:
```bash
cat src/service-worker.js | grep -E "(embeddings|models|wasm)"
```

Expected: No matches (all references removed)

**Step 4: Test build**

Run:
```bash
npm run build
```

Expected: Build succeeds, service-worker.js copied to dist/

**Step 5: Commit**

```bash
git add src/service-worker.js
git commit -m "refactor: remove model files from service worker cache"
```

---

## Task 8: Manual Browser Testing

**Files:** None (manual testing)

**Step 1: Start dev server**

Run:
```bash
npm run dev
```

Expected: Server starts at http://localhost:5173

**Step 2: Test basic functionality**

Manual steps:
1. Open http://localhost:5173/essay_search_engine/
2. Verify page loads quickly (no long initialization)
3. Type a partial tag name (e.g., "heal")
4. Verify autocomplete dropdown appears with "tag:health" etc.
5. Select a tag from dropdown
6. Verify badge appears above search box
7. Verify search executes showing results for that tag
8. Click the × on the badge to remove it
9. Verify badge disappears and results update

**Step 3: Test keyword search**

Manual steps:
1. Clear any badges
2. Type a keyword in search box (e.g., "meditation")
3. Click Search
4. Verify results appear with relevant chunks
5. Verify results are ranked sensibly (titles > tags > content)

**Step 4: Test combined tag + keyword**

Manual steps:
1. Select a tag badge (e.g., "health")
2. Type a keyword (e.g., "mindfulness")
3. Click Search
4. Verify results are tagged "health" AND contain "mindfulness"
5. Remove badge
6. Verify results update to all "mindfulness" results

**Step 5: Test URL parameter**

Manual steps:
1. Visit http://localhost:5173/essay_search_engine/?tag=philosophy
2. Verify "philosophy" badge appears automatically
3. Verify results show philosophy-tagged chunks

**Step 6: Test offline functionality**

Manual steps:
1. Open DevTools > Application > Service Workers
2. Verify service worker is registered
3. Check "Offline" in Network tab
4. Reload page
5. Verify app still works (cached assets load)
6. Search should still work with cached metadata.json

**Step 7: Document any issues**

If bugs found, note them. Do NOT commit yet (testing is verification only).

---

## Task 9: Remove Model Files from Repository

**Files:**
- Delete: `public/models/**`
- Delete: `public/wasm/**`
- Delete: `public/data/embeddings.json`

**Step 1: Remove model directory**

Run:
```bash
rm -rf public/models
```

Expected: Directory removed

**Step 2: Remove WASM directory**

Run:
```bash
rm -rf public/wasm
```

Expected: Directory removed

**Step 3: Remove embeddings.json**

Run:
```bash
rm public/data/embeddings.json
```

Expected: File removed

**Step 4: Verify removal**

Run:
```bash
ls -la public/models 2>&1 || echo "models/ removed ✓"
ls -la public/wasm 2>&1 || echo "wasm/ removed ✓"
ls public/data/embeddings.json 2>&1 || echo "embeddings.json removed ✓"
```

Expected: All three confirmation messages

**Step 5: Check if .gitattributes references model files**

Run:
```bash
cat .gitattributes 2>/dev/null | grep -i model || echo "No .gitattributes or no model references"
```

If model files were tracked with Git LFS, remove those lines from .gitattributes.

**Step 6: Test build still works**

Run:
```bash
npm run build
```

Expected: Build succeeds (smaller dist/ size)

**Step 7: Commit**

```bash
git add -A
git commit -m "remove: delete model files and embeddings (327MB reduction)"
```

---

## Task 10: Update CLAUDE.md Documentation

**Files:**
- Modify: `CLAUDE.md`

**Step 1: Update Architecture section**

Replace the Architecture paragraph:
```markdown
## Architecture

Two-phase system: (1) EPUB → Markdown → Semantic chunks → AI tags via `process_book.py`, (2) Generate metadata via `sync/build.py`, (3) Client-side keyword/fuzzy search using Fuse.js (9KB) running in browser. All search is client-side, no backend. Deploys to GitHub Pages.
```

**Step 2: Update Project Structure**

Replace the public/data section:
```markdown
├── public/
│   └── data/
│       ├── metadata.json    # Book/chunk metadata with full content
│       └── tags.json        # Tag index
```

Remove references to:
- `embeddings.json`
- `public/models/`

**Step 3: Update Critical Constraints**

Remove constraint #2 (Embedding normalization - no longer relevant).

Remove constraint #3 (Model files - no longer relevant).

**Step 4: Update Search ranking**

Replace constraint #4 with:
```markdown
4. **Search configuration** (src/search.js):
   - Fuse.js weighted field search
   - Book Title: weight 0.4 (highest priority)
   - Chapter Title: weight 0.3
   - Tags: weight 0.2
   - Content: weight 0.1 (lowest, avoids noise)
   - Threshold: 0.4 (match strictness)
   - Tag badges use exact AND logic
```

**Step 5: Update Critical Files section**

Replace search.js description:
```markdown
- `src/search.js`: SearchEngine class with Fuse.js keyword/fuzzy search + tag filtering
```

**Step 6: Update Workflow section**

Replace the sync step:
```markdown
./lib --sync       →  Generate metadata → public/data/
```

**Step 7: Update Key Behaviors section**

Replace the Search bullet:
```markdown
- **Search**: Keyword/fuzzy search with Fuse.js → tag filtering (exact AND) → fuzzy match within filtered → paginate (25/page)
```

Replace the Offline bullet:
```markdown
- **Offline**: Service Worker caches metadata + app files. Works fully offline after first load.
```

**Step 8: Verify changes**

Run:
```bash
git diff CLAUDE.md
```

Expected: Shows all the documentation updates

**Step 9: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md for keyword search architecture"
```

---

## Task 11: Final Verification and Build

**Files:** None (verification)

**Step 1: Clean build**

Run:
```bash
rm -rf dist && npm run build
```

Expected: Clean build succeeds

**Step 2: Check dist size**

Run:
```bash
du -sh dist/
```

Expected: Should be ~500KB (down from ~342MB before)

**Step 3: Check bundle sizes**

Run:
```bash
ls -lh dist/assets/
```

Expected: Main bundle should be ~50KB (down from ~820KB)

**Step 4: Run preview server**

Run:
```bash
npm run preview
```

Expected: Preview server starts

**Step 5: Full manual test**

Repeat Task 8 manual testing steps on preview build:
1. Search works instantly
2. Autocomplete works
3. Badges work
4. Tag + keyword combined search works
5. URL parameters work

**Step 6: Stop preview server**

Press Ctrl+C

**Step 7: Verify git status is clean**

Run:
```bash
git status
```

Expected: "nothing to commit, working tree clean"

**Step 8: Review commit history**

Run:
```bash
git log --oneline main..HEAD
```

Expected: Shows all 11 commits from this plan

---

## Task 12: Optional - Update sync/build.py

**Files:**
- Modify: `sync/build.py` (optional optimization)

**Note:** This task is optional. The build script currently generates embeddings.json which is no longer used. You can remove the embedding generation logic to speed up the build process, but it's not required for the feature to work.

**Step 1: Identify embedding generation code**

Run:
```bash
grep -n "embedding" sync/build.py | head -20
```

Expected: Shows lines where embeddings are generated

**Step 2: Comment out or remove embedding generation**

This is optional and can be done later. The metadata.json generation must remain.

**Step 3: Test sync still works**

Run:
```bash
./lib --sync
```

Expected: Generates metadata.json and tags.json (skip if you don't have books)

**Step 4: Commit (if changes made)**

```bash
git add sync/build.py
git commit -m "chore: remove unused embedding generation from build"
```

---

## Summary

**Total changes:**
- 12 tasks (11 required, 1 optional)
- Bundle size: 342MB → ~500KB (99.85% reduction)
- Initialization time: 1-2 minutes → <100ms
- Dependencies: +2 packages, -1 package
- Deleted files: ~327MB of model files
- Modified files: 6 core files
- New features: Tag autocomplete, badge UI, hybrid AND search

**Verification checklist:**
- [ ] npm run build succeeds
- [ ] npm run dev works
- [ ] Search is instant on page load
- [ ] Autocomplete shows tag suggestions
- [ ] Badges can be added and removed
- [ ] Tag filtering works (exact match)
- [ ] Keyword search works (fuzzy match)
- [ ] Combined tag + keyword works (AND logic)
- [ ] URL parameters work (?tag=X)
- [ ] Offline functionality works
- [ ] All commits have descriptive messages
