# Search UX Redesign: Keyword Search with Tag Autocomplete

**Date:** 2026-01-17
**Status:** Approved

## Problem Statement

Current search engine has several UX issues:
1. **Slow initialization** - Takes 1-2 minutes to load 327MB AI model into WASM memory on every page refresh
2. **Too many irrelevant results** - Semantic search finds conceptually related content, causing noise
3. **Actual usage pattern** - User primarily browses exact tags or searches by keyword, not semantic concepts

The 327MB BGE-large-en-v1.5 model provides semantic search ("philosophy" finds "ethics"), but the user wants keyword search ("philosophy" finds chunks containing "philosoph*").

## Solution Overview

Replace semantic search with lightweight keyword/fuzzy search and add tag autocomplete UI:

**Search approach:**
- Keyword/fuzzy matching using Fuse.js (9KB)
- Search across: book title, chapter title, tags, content
- Tag badges for exact tag filtering with AND logic
- Autocomplete dropdown for 2K tags

**Benefits:**
- Instant page load (milliseconds vs minutes)
- More precise, relevant results
- Better UX for tag-based discovery
- 99.997% smaller (9KB vs 342MB)
- Still works fully offline

## Architecture

### 1. Search Algorithm

**Library:** Fuse.js (9KB gzipped)

**Configuration:**
```javascript
const fuse = new Fuse(metadata.chunks, {
  keys: [
    { name: 'book_title', weight: 0.4 },      // Highest priority
    { name: 'chapter_title', weight: 0.3 },   // Second priority
    { name: 'tags', weight: 0.2 },            // Third priority
    { name: 'content', weight: 0.1 }          // Lowest (avoids noise)
  ],
  threshold: 0.4,              // Match strictness (0.0 = exact, 1.0 = anything)
  ignoreLocation: true,        // Match anywhere in field
  minMatchCharLength: 2        // Ignore single chars
});
```

**Why Fuse.js:**
- Fuzzy matching (handles typos)
- Weighted field search (title matches rank higher)
- Threshold control (filter weak matches)
- Zero dependencies, works offline
- Battle-tested, actively maintained

**Alternative considered:** Plain JavaScript with `String.includes()` would be 0KB but lacks fuzzy matching and requires manual ranking logic.

### 2. Tag Autocomplete UI

**Library:** @tarekraafat/autocomplete.js (~10KB gzipped)

With 2K tags, need efficient filtering, virtual scrolling, and keyboard navigation. This library provides all without bloat.

**Tag extraction:**
```javascript
// At initialization (instant)
const allTags = new Set();
metadata.chunks.forEach(chunk => {
  if (chunk.tags) {
    chunk.tags.split(',').forEach(tag => allTags.add(tag.trim()));
  }
});
const tagList = Array.from(allTags).sort(); // ~2K tags
```

**Autocomplete config:**
```javascript
new autoComplete({
  selector: "#searchInput",
  data: {
    src: tagList,
    cache: true
  },
  resultsList: {
    maxResults: 15,
    noResults: true
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
        addBadge(tag);
        searchInput.value = '';
      }
    }
  }
});
```

### 3. Badge UI & Search Logic

**HTML structure:**
```html
<div class="search-container">
  <div class="tag-badges">
    <!-- Dynamic badges -->
    <span class="badge">health <button>×</button></span>
    <span class="badge">ethics <button>×</button></span>
  </div>
  <input type="text" id="searchInput" placeholder="Search or add tags..." />
</div>
```

**Badge state:**
```javascript
const selectedTags = new Set();

function addBadge(tag) {
  if (selectedTags.has(tag)) return; // No duplicates
  selectedTags.add(tag);
  renderBadges();
}

function removeBadge(tag) {
  selectedTags.delete(tag);
  renderBadges();
}
```

**Search execution (Hybrid AND logic):**
```javascript
async function performSearch() {
  const keywordQuery = searchInput.value.trim();
  const tags = Array.from(selectedTags);

  // Step 1: Filter by tags (exact AND logic)
  let results = metadata.chunks;
  if (tags.length > 0) {
    results = results.filter(chunk => {
      const chunkTags = chunk.tags?.split(',').map(t => t.trim()) || [];
      return tags.every(tag => chunkTags.includes(tag)); // ALL tags must match
    });
  }

  // Step 2: Fuzzy search within filtered results (if keyword exists)
  if (keywordQuery) {
    const fuse = new Fuse(results, fuseConfig);
    results = fuse.search(keywordQuery).map(r => r.item);
  }

  return results;
}
```

**Search behavior examples:**
- `badges=[health, ethics], input=""` → Chunks tagged with BOTH health AND ethics
- `badges=[], input="meditation"` → Fuzzy search "meditation" across all fields
- `badges=[health], input="meditation"` → Health-tagged chunks containing "meditation"
- `?tag=philosophy` from Browse Tags → Converts to badge, input stays empty

### 4. File Changes

**Modified files:**

1. **`src/search.js`** - Replace SearchEngine class
   - Remove: @xenova/transformers, embedder, cosine similarity
   - Add: Fuse.js import and configuration
   - Keep: Same public API (initialize, search)

2. **`src/main.js`** - Minimal changes
   - Remove: Model loading progress callbacks
   - Add: Tag extraction, autocomplete, badge management
   - Keep: Pagination, event handlers, rendering

3. **`package.json`** - Update dependencies
   - Remove: @xenova/transformers
   - Add: fuse.js, @tarekraafat/autocomplete.js

4. **`src/styles.css`** - Add badge and autocomplete styles

5. **`service-worker.js`** - Remove model/embedding caches
   - Bump cache version to v3
   - Remove: models/**, wasm/**, embeddings.json
   - Keep: metadata.json, app files

**Removed files:**
- `public/models/**` - 327MB model files
- `public/data/embeddings.json` - 15MB embeddings

**Unchanged files:**
- `public/data/metadata.json` - Still contains all searchable data
- `sync/build.py` - Could skip embedding generation later (optional optimization)
- `chunk.html`, `index.html` structure, etc.

## Service Worker Migration

**Cache cleanup:**
```javascript
const CACHE_NAME = 'essay-search-v3'; // Bump version

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (cacheName !== CACHE_NAME) {
            return caches.delete(cacheName); // Clear 327MB old cache
          }
        })
      );
    })
  );
});
```

**New cache list:**
```javascript
const urlsToCache = [
  '/essay_search_engine/',
  '/essay_search_engine/index.html',
  '/essay_search_engine/chunk.html',
  '/essay_search_engine/data/metadata.json',
  // Removed: models/**, wasm/**, embeddings.json
];
```

Users will automatically:
1. Clear old 327MB cache on app update
2. Download new ~100KB assets
3. Continue working offline perfectly

## Impact Summary

**Performance:**
- Initialization: 1-2 minutes → <100ms
- Search latency: ~50ms → ~10ms
- Bundle size: 342MB → 19KB (Fuse.js 9KB + autocomplete 10KB)
- First load: 342MB download → ~100KB download
- Offline: Still works perfectly

**UX improvements:**
- Instant page load/refresh
- Tag autocomplete for 2K tags
- Visual tag badges with easy removal
- More precise, relevant results
- Fewer "why is this here?" results
- Natural workflow: Browse tags → Badge → Refine with keywords

**Trade-offs:**
- Lose semantic search (finding conceptually related content without keyword overlap)
- User confirmed this causes more noise than value for their use case

## Future Enhancements

**Optional improvements not in scope:**
1. Expose `threshold` slider in UI for user-tunable strictness
2. Save recent tag combinations to localStorage
3. Tag suggestions based on current results ("People also searched...")
4. Stop generating embeddings in `sync/build.py` (saves build time)
5. Multi-select tags from Browse Tags page (add multiple badges at once)

## Implementation Plan

1. Install new dependencies (fuse.js, autocomplete.js)
2. Rewrite SearchEngine class with Fuse.js
3. Add tag extraction and autocomplete
4. Implement badge UI and state management
5. Update search execution with hybrid AND logic
6. Update service worker cache strategy
7. Remove model files from repo
8. Test offline functionality
9. Update CLAUDE.md documentation
