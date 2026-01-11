# Tag Navigation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add clickable tags and a dedicated tag index page for browsing all available tags alphabetically.

**Architecture:** Extend sync process to extract tags and generate static HTML index. Add client-side URL parameter handling for tag-based searches. Pure semantic HTML, no new CSS.

**Tech Stack:** Python (sync scripts), Vanilla JavaScript, HTML, Vite (build)

---

## Task 1: Add Tag Extraction to Sync Script

**Files:**
- Modify: `sync/sync.py` (add functions after line 271)

**Step 1: Add tag extraction function**

Add this function after the `generate_chunk_pages()` function (around line 271):

```python
def extract_tags(chunks):
    """Extract all unique tags with counts from chunks"""
    tag_counts = {}

    for chunk in chunks:
        if not chunk.get('tags'):
            continue

        # Parse comma-separated tags
        tags = [tag.strip().lower() for tag in chunk['tags'].split(',') if tag.strip()]

        for tag in tags:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1

    return tag_counts
```

**Step 2: Add tags.json generation function**

Add this function after `extract_tags()`:

```python
def generate_tags_json(tag_counts):
    """Generate public/data/tags.json"""
    output_file = TARGET_DIR / 'public' / 'data' / 'tags.json'
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, 'w') as f:
        json.dump(tag_counts, f, indent=2, sort_keys=True)

    file_size_kb = output_file.stat().st_size / 1024
    print(f"\n✓ Generated tags.json ({len(tag_counts)} unique tags, {file_size_kb:.1f} KB)")
```

**Step 3: Add tags.html generation function**

Add this function after `generate_tags_json()`:

```python
def generate_tags_html(tag_counts):
    """Generate public/tags.html with alphabetical index"""
    output_file = TARGET_DIR / 'public' / 'tags.html'
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Group tags by first letter
    tags_by_letter = {}
    for tag in sorted(tag_counts.keys()):
        first_letter = tag[0].upper()
        if first_letter not in tags_by_letter:
            tags_by_letter[first_letter] = []
        tags_by_letter[first_letter].append((tag, tag_counts[tag]))

    # Generate HTML
    html = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Browse Tags - Essay Search Engine</title>
</head>
<body>
  <h1>Browse by Tag</h1>
  <a href="/essay_search_engine/">← Back to Search</a>

"""

    # Add letter sections
    for letter in sorted(tags_by_letter.keys()):
        html += f"  <h2>{letter}</h2>\n  <ul>\n"
        for tag, count in tags_by_letter[letter]:
            # URL encode the tag for the link
            from urllib.parse import quote
            encoded_tag = quote(tag)
            html += f'    <li><a href="/essay_search_engine/?tag={encoded_tag}">{tag} ({count})</a></li>\n'
        html += "  </ul>\n\n"

    html += """</body>
</html>
"""

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)

    file_size_kb = output_file.stat().st_size / 1024
    print(f"✓ Generated tags.html ({len(tag_counts)} tags, {file_size_kb:.1f} KB)")
```

**Step 4: Integrate tag generation into main sync flow**

Modify the `main()` function. After the `generate_chunk_pages(new_chunks)` call (around line 318), add:

```python
    # Generate tag index (after generate_chunk_pages)
    print("\n🏷️  Generating tag index...")

    # Need to load ALL chunks for complete tag index
    all_chunks = collect_chunks(books_metadata['books'], all_books=True)
    tag_counts = extract_tags(all_chunks)
    print(f"   Found {len(tag_counts)} unique tags")

    generate_tags_json(tag_counts)
    generate_tags_html(tag_counts)
```

**Step 5: Test sync script**

Run the sync script to verify tag generation works:

```bash
cd /Users/jamesalexander/essay_search_engine/.worktrees/feature/tag-navigation
source ../../venv/bin/activate  # Activate Python venv from main repo
python3 sync/sync.py --force
```

Expected output:
- "🏷️  Generating tag index..."
- "Found X unique tags"
- "✓ Generated tags.json (X unique tags, Y KB)"
- "✓ Generated tags.html (X tags, Y KB)"

Expected files created:
- `public/data/tags.json`
- `public/tags.html`

**Step 6: Verify generated files**

Check that files were created and have reasonable content:

```bash
ls -lh public/data/tags.json
ls -lh public/tags.html
head -20 public/tags.html
```

Expected:
- Both files exist
- tags.html starts with `<!DOCTYPE html>` and has letter sections
- tags.json is valid JSON with tag counts

**Step 7: Commit changes**

```bash
git add sync/sync.py public/data/tags.json public/tags.html
git commit -m "feat: add tag extraction and index generation to sync

- Extract unique tags from all chunks with counts
- Generate tags.json for programmatic access
- Generate tags.html with alphabetical index
- Pure semantic HTML, no CSS styling

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 2: Make Tags Clickable in Search Results

**Files:**
- Modify: `src/main.js:138-146` (tag rendering)

**Step 1: Update tag rendering to use links**

Replace the tag rendering code in `renderResults()` function (lines 138-146):

**OLD CODE:**
```javascript
${tags.length > 0 ? `
  <div class="result-tags">
    ${tags.map(tag => `
      <span class="tag">
        ${escapeHtml(tag)}
      </span>
    `).join('')}
  </div>
` : ''}
```

**NEW CODE:**
```javascript
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

**Step 2: Test tag links in dev mode**

Start the dev server:

```bash
npm run dev
```

Open browser to `http://localhost:5173/essay_search_engine/`

Manual test:
1. Wait for "Ready!" status
2. Search for any term (e.g., "anxiety")
3. Verify tags appear as links (should be underlined/clickable)
4. Click a tag - URL should change to `?tag=tagname`
5. Page reloads but doesn't auto-search yet (expected - will fix in next task)

**Step 3: Commit changes**

```bash
git add src/main.js
git commit -m "feat: make tags clickable in search results

Tags now link to ?tag=<tagname> URLs for navigation

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 3: Add URL Parameter Handling for Auto-Search

**Files:**
- Modify: `src/main.js:266-267` (DOMContentLoaded handler)

**Step 1: Add URL parameter detection and auto-search**

Replace the DOMContentLoaded event listener (lines 266-267):

**OLD CODE:**
```javascript
// Auto-initialize on page load
window.addEventListener('DOMContentLoaded', initialize);
```

**NEW CODE:**
```javascript
// Auto-initialize on page load and handle tag parameters
window.addEventListener('DOMContentLoaded', async () => {
  await initialize();

  // Check for tag parameter in URL
  const urlParams = new URLSearchParams(window.location.search);
  const tag = urlParams.get('tag');

  if (tag && isInitialized) {
    searchInput.value = tag;
    performSearch();
  }
});
```

**Step 2: Test URL parameter handling**

With dev server still running (or restart with `npm run dev`):

Manual test:
1. Navigate to `http://localhost:5173/essay_search_engine/?tag=anxiety`
2. Wait for initialization
3. Verify search input is populated with "anxiety"
4. Verify search executes automatically
5. Verify results appear for "anxiety"

Test tag clicking:
1. Search for a term
2. Click a tag on a result
3. Verify URL changes to `?tag=<tagname>`
4. Verify search input updates
5. Verify new search executes

**Step 3: Test edge cases**

Test with empty tag:
- Navigate to `http://localhost:5173/essay_search_engine/?tag=`
- Should show no results

Test with invalid tag:
- Navigate to `http://localhost:5173/essay_search_engine/?tag=nonexistenttag123`
- Should show "No results found"

Test with URL-encoded tag:
- Navigate to `http://localhost:5173/essay_search_engine/?tag=self-love`
- Should work correctly (hyphens preserved)

**Step 4: Commit changes**

```bash
git add src/main.js
git commit -m "feat: add URL parameter handling for tag-based search

- Detect ?tag= parameter on page load
- Auto-populate search input with tag value
- Trigger search automatically
- Enables shareable tag search URLs

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 4: Add "Browse Tags" Navigation Link

**Files:**
- Modify: `index.html:10-15` (add nav after h1)

**Step 1: Add navigation link to index.html**

Add navigation link after the `<h1>` tag (around line 10):

**BEFORE:**
```html
<body>
  <h1>Essay Search Engine</h1>

  <form id="search-form">
```

**AFTER:**
```html
<body>
  <h1>Essay Search Engine</h1>

  <nav>
    <a href="/essay_search_engine/tags.html">Browse Tags</a>
  </nav>

  <form id="search-form">
```

**Step 2: Test navigation link**

With dev server running:

Manual test:
1. Go to main page `http://localhost:5173/essay_search_engine/`
2. Verify "Browse Tags" link appears below heading
3. Click "Browse Tags" link
4. Should navigate to tags.html (will 404 in dev - expected, Vite doesn't serve public/ files)
5. Build and preview to test properly

**Step 3: Build and test tags.html**

Build the project and preview:

```bash
npm run build
npm run preview
```

Open browser to the preview URL (usually `http://localhost:4173/essay_search_engine/`)

Manual test:
1. Verify "Browse Tags" link appears
2. Click "Browse Tags"
3. Should navigate to tags.html with alphabetical list
4. Verify letter headers (A, B, C, etc.)
5. Verify tags show counts: "anxiety (47)"
6. Click any tag
7. Should navigate back to main page with `?tag=<tagname>`
8. Verify search executes automatically
9. Click "← Back to Search" link on tags.html
10. Should return to main page

**Step 4: Test back button on tags.html**

From tags.html:
1. Click browser back button
2. Should return to previous page (main search)

From main page:
1. Click "Browse Tags"
2. Click a tag
3. Click browser back button
4. Should return to tags.html (browser history works correctly)

**Step 5: Commit changes**

```bash
git add index.html
git commit -m "feat: add Browse Tags navigation link

Adds link to tag index page in main navigation

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 5: Final Integration Testing

**Files:**
- No changes, just testing

**Step 1: Build production bundle**

```bash
npm run build
```

Expected:
- Build succeeds with no errors
- May show large chunk warning (expected)

**Step 2: Preview production build**

```bash
npm run preview
```

Open browser to preview URL.

**Step 3: Full integration test**

Scenario 1: Browse → Search
1. Go to main page
2. Click "Browse Tags"
3. Scroll to find a tag (e.g., "jealousy")
4. Click the tag
5. Verify redirects to main page with ?tag=jealousy
6. Verify search executes
7. Verify results appear

Scenario 2: Search → Filter by Tag
1. Go to main page
2. Search for general term (e.g., "life")
3. Review results
4. Click a tag on one result (e.g., "meaning")
5. Verify URL changes to ?tag=meaning
6. Verify new search executes
7. Verify results filtered to that tag

Scenario 3: Direct URL
1. Copy a tag URL (e.g., `http://localhost:4173/essay_search_engine/?tag=solitude`)
2. Open in new tab/window
3. Verify search executes immediately
4. Verify results appear

Scenario 4: Navigation flow
1. Main page → Browse Tags
2. Tags page → Click tag → Main page (with search)
3. Main page → Click different tag on result
4. Use browser back button (should go back through history correctly)

**Step 4: Verify all success criteria**

From design document:
- [x] Users can click any tag to search for it
- [x] Tag index page shows all tags alphabetically with counts
- [x] Navigation between search and browse works smoothly
- [x] URL sharing works (e.g., share `/?tag=anxiety` link)
- [x] No new CSS files or styling complexity
- [x] Sync process completes successfully

**Step 5: Check generated files**

Verify these files exist and are reasonable:
```bash
ls -lh public/data/tags.json
ls -lh public/tags.html
wc -l public/tags.html
```

Expected:
- tags.json exists with tag counts
- tags.html exists with alphabetical sections
- File sizes reasonable (< 100 KB each)

**Step 6: Final commit (if any fixes needed)**

If you made any fixes during testing:

```bash
git add .
git commit -m "fix: address integration test issues

[describe any fixes made]

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 6: Update Documentation

**Files:**
- Modify: `CLAUDE.md` (add to Recent Updates section at top)

**Step 1: Add entry to CLAUDE.md Recent Updates**

Add this section at the top of the "Recent Updates" section (after line 6):

```markdown
### Tag Navigation (2026-01-12)

**Goal**: Enable browsing and navigating content by AI-generated tags.

**Changes**:
- **Tag Index Page**: Alphabetical listing at `/tags.html` showing all unique tags with counts
- **Clickable Tags**: Tags in search results are now clickable links to `?tag=<tagname>` URLs
- **URL Parameters**: Main page detects `?tag=` parameter and auto-executes search
- **Navigation**: Added "Browse Tags" link to main page header
- **Data Generation**: Sync script now extracts tags and generates `tags.json` + `tags.html`

**Implementation**:
- Pure semantic HTML, zero new CSS files
- Static tag index generated during sync
- Shareable tag search URLs
- Foundation for future hierarchical tag clustering

**Usage**:
- Browse tags: Click "Browse Tags" on main page
- Search by tag: Click any tag in search results or on tag index
- Share tag searches: Copy URL (e.g., `/?tag=anxiety`)

**Design**: See `docs/plans/2026-01-12-tag-navigation-design.md`
**Implementation**: See `docs/plans/2026-01-12-tag-navigation.md`

```

**Step 2: Commit documentation update**

```bash
git add CLAUDE.md
git commit -m "docs: document tag navigation feature

Add implementation summary to CLAUDE.md

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Post-Implementation

**Verify work in worktree:**
```bash
pwd  # Should be in .worktrees/feature/tag-navigation
git log --oneline -10  # Review commits
git diff main  # Review all changes vs main branch
```

**Ready to merge?**

Use `superpowers:finishing-a-development-branch` skill to:
1. Review all changes
2. Choose merge strategy (direct merge, PR, or cleanup)
3. Return to main workspace

---

## Expected Outcomes

**Files Modified:**
- `sync/sync.py` - Add tag extraction and generation functions
- `src/main.js` - Add URL parameter handling, make tags clickable
- `index.html` - Add Browse Tags link
- `CLAUDE.md` - Document feature

**Files Generated (by sync):**
- `public/data/tags.json` - Tag counts for programmatic access
- `public/tags.html` - Static alphabetical tag index

**Commits:**
- feat: add tag extraction and index generation to sync
- feat: make tags clickable in search results
- feat: add URL parameter handling for tag-based search
- feat: add Browse Tags navigation link
- docs: document tag navigation feature

**Testing:**
- Manual testing at each step
- Build verification (npm run build)
- Preview testing (npm run preview)
- Integration testing (full user flows)

---

**Implementation Time:** ~30-45 minutes (assumes familiarity with codebase)
