# Tag Navigation Feature - Design Document

**Date:** 2026-01-12
**Status:** Approved for implementation

## Overview

Add tag-based navigation to the essay search engine, allowing users to:
1. Click tags on search results to search for that tag
2. Browse all available tags on a dedicated index page

This is phase 1 of a future hierarchical tag system where semantically similar tags will cluster under parent concepts.

## User Experience

### Clicking Tags (Search Results)
- Tags displayed on search results become clickable links
- Clicking a tag navigates to `/?tag=anxiety`
- Search input auto-populates with the tag
- Search executes immediately

### Tag Index Page
- New page at `/tags.html`
- Simple alphabetical listing with letter headers (A, B, C...)
- Each tag shows: name + count (e.g., "anxiety (47)")
- Single-column list using browser default styling
- Link back to main search page

### Navigation
- Main search page gets "Browse Tags" link in header
- All tag links use relative URLs (`?tag=...`) to work with base path

## Data Flow

### Sync Process Enhancement
The existing `sync/sync.py` script will be extended to:

1. **Extract all unique tags** from chunks
2. **Count occurrences** of each tag
3. **Generate `public/data/tags.json`:**
   ```json
   {
     "anxiety": 47,
     "jealousy": 23,
     "solitude": 18
   }
   ```
4. **Generate `public/tags.html`** static page with alphabetical index

### Client-Side Enhancement
`src/main.js` will be updated to:

1. **Check for URL parameters** on page load
2. **If `?tag=` exists:**
   - Populate search input with tag value
   - Trigger search automatically
3. **Make tags clickable** in search results
   - Convert `<span class="tag">` to `<a href="?tag=..." class="tag">`

## Technical Implementation

### Files Modified
1. **sync/sync.py**
   - Add tag extraction function
   - Add HTML generation for tags.html
   - Generate tags.json for future use

2. **src/main.js**
   - Add URL parameter detection
   - Update tag rendering to use links
   - Auto-search on tag parameter

3. **index.html**
   - Add "Browse Tags" navigation link

### Files Created
1. **public/tags.html** (generated)
   - Alphabetical tag index
   - Pure semantic HTML, no custom CSS

2. **public/data/tags.json** (generated)
   - Tag counts for future features

### HTML Structure (tags.html)

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Browse Tags - Essay Search Engine</title>
</head>
<body>
  <h1>Browse by Tag</h1>
  <a href="/essay_search_engine/">← Back to Search</a>

  <h2>A</h2>
  <ul>
    <li><a href="/essay_search_engine/?tag=anxiety">anxiety (47)</a></li>
    <li><a href="/essay_search_engine/?tag=art">art (12)</a></li>
  </ul>

  <h2>B</h2>
  <ul>
    <li><a href="/essay_search_engine/?tag=beauty">beauty (31)</a></li>
  </ul>

  <!-- More letter sections -->
</body>
</html>
```

### URL Parameter Handling

```javascript
// On page load (main.js)
window.addEventListener('DOMContentLoaded', async () => {
  await initialize();

  // Check for tag parameter
  const urlParams = new URLSearchParams(window.location.search);
  const tag = urlParams.get('tag');

  if (tag && isInitialized) {
    searchInput.value = tag;
    performSearch();
  }
});
```

### Clickable Tags in Results

```javascript
// Updated tag rendering (main.js)
${tags.length > 0 ? `
  <div class="result-tags">
    ${tags.map(tag => `
      <a href="?tag=${encodeURIComponent(tag)}" class="tag">
        ${escapeHtml(tag)}
      </a>
    `).join('')}
  </div>
` : ''}
```

## Design Decisions

### Why Static Generation?
- Consistent with existing architecture (metadata.json, embeddings.json)
- No client-side aggregation needed
- Fast page loads
- Pre-computed during sync

### Why Simple Alphabetical List?
- Scales to hundreds of tags without UI complexity
- Easy to scan
- No CSS maintenance burden
- Foundation for future hierarchical view

### Why URL Parameters vs. Routes?
- Works with single-page static site
- No router library needed
- Clean shareable URLs
- Browser back/forward works naturally

### Why Auto-Search on Tag Click?
- Consistent behavior everywhere (index page or search results)
- Fewer clicks for user
- Tags are specific enough that immediate results are useful
- User can still modify query after if needed

## Error Handling

- **Chunks without tags:** Skip during extraction
- **Empty/malformed tags:** Filter out during parsing
- **Letters with no tags:** Don't render empty sections
- **Invalid URL parameters:** Treat as empty search

## Future Enhancements (Not in Scope)

This design intentionally leaves room for:
1. **Hierarchical tag clustering** - semantically similar tags grouped under parent concepts
2. **Tag embeddings** - using vector similarity to build the hierarchy
3. **Interactive tag graph** - visual exploration of tag relationships
4. **Tag filtering** - combine multiple tags in search

The current flat structure provides the data foundation and UI patterns needed for these features.

## Success Criteria

1. Users can click any tag to search for it
2. Tag index page shows all tags alphabetically with counts
3. Navigation between search and browse works smoothly
4. URL sharing works (e.g., share `/?tag=anxiety` link)
5. No new CSS files or styling complexity
6. Sync process completes successfully

---

**Ready for implementation.**
