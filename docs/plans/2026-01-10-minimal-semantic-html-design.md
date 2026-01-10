# Minimal Semantic HTML Design

**Date**: 2026-01-10
**Goal**: Strip all bloated styling and dependencies, keep codebase lean and powerful with raw semantic HTML

## Requirements

- Private project - only essentials needed
- Browser defaults for styling (except minimal mobile usability CSS)
- Auto-initialize search on page load (no manual button)
- Search triggers on button click only (no auto-search while typing)
- Chunk pages viewed in Safari Reader (no styling needed)

## Architecture

### Search Page (index.html)

Minimal structure:
```html
<body>
  <h1>Essay Search Engine</h1>

  <form id="search-form">
    <input type="search" id="search-input" disabled>
    <button type="submit" disabled>Search</button>
  </form>

  <p id="status">Loading search engine...</p>

  <div id="results"></div>
</body>
```

Elements:
- App title (h1)
- Search form (input + submit button)
- Status messages (loading, results count, errors)
- Results container

### Chunk Pages (chunk_XXX.html)

Zero styling, pure semantic HTML for Safari Reader:
```html
<body>
  <a href="../../index.html">← Back</a>

  <h1>Book Title</h1>
  <p>by Author Name</p>
  <h2>Chapter Title</h2>

  <p>Tags: tag1, tag2, tag3</p>

  <article>
    [chunk content]
  </article>
</body>
```

Elements:
- Back link to search
- Book title (h1)
- Author name
- Chapter title (h2)
- Tags list
- Article content

## CSS Strategy

### Search Page
Minimal CSS (~20-30 lines) for mobile usability only:
- 16px minimum font size (prevents mobile zoom)
- 44px minimum touch targets (iOS standard)
- Max-width container (50rem)
- System font stack
- Full-width search input

### Chunk Pages
No CSS - relies on Safari Reader mode styling

## JavaScript Behavior

### Auto-initialization
- On page load: immediately start loading model/data
- Status updates: "Loading search engine..." → "Ready"
- Enable search input/button when ready
- No init button needed (model caches after first download)

### Search Trigger
- Button click
- Enter key in search input
- NO auto-search while typing (removed debounce)

### Result Rendering
- Pagination: 25 results per page
- Each result: Book title, Chapter title, Score %, Tags
- Click result → navigate to chunk_XXX.html

## Implementation Scope

### Files to Modify
1. **index.html** - Strip to essentials
2. **src/styles.css** - Replace with ~30 lines minimal CSS
3. **src/main.js** - Remove debounce, auto-init, button-only search
4. **sync/sync.py** - Remove all inline styles from chunk template
5. **package.json** - Remove Tailwind dependencies

### Files to Delete
- tailwind.config.js
- postcss.config.js

### Functionality Preserved
- Search algorithm (tag boosting, tiered filtering)
- Pagination logic
- Model caching (Transformers.js handles this)
- Metadata/embeddings structure

### Functionality Removed
- All Tailwind CSS (~76 packages)
- Init button UI
- Auto-search on typing (debounce)
- All utility classes
- Footer with links
- Chunk page inline styles

## Success Criteria

- Search page: functional with browser defaults + minimal mobile CSS
- Chunk pages: pure HTML for Safari Reader
- No Tailwind dependencies
- Auto-initializes on page load
- Search only on button press
- Codebase significantly simplified
