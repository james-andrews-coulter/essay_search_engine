# TODO - Bug Backlog

## COMPLETED BUGS ✅

### ✅ BUG-001: Search Results Show Wrong Content (FIXED - 2026-01-09)

**Status**: COMPLETED

**What was fixed**:
- Implemented globally unique doc_ids for all chunks across all books
- Updated process_book.py to assign doc_ids based on id_range from books_metadata.json
- Updated sync.py to use doc_id instead of book-local chunk_id for HTML filenames
- Added validation to detect duplicate chunk IDs before generating outputs
- Created migration script (migrate_add_doc_ids.py) to add doc_ids to existing chunks

**Verification**:
- ✅ 758 unique HTML files now exist in public/chunks/
- ✅ metadata.json has 758 unique chunk_ids (no duplicates)
- ✅ Search for "anxiety" returns correct content when clicking results
- ✅ Search for "solitude" returns correct content when clicking results

**Files Modified**:
- process_book.py (save_chunks function and main flow)
- sync/sync.py (collect_chunks, validate_chunks, generate_metadata_json functions)
- migrate_add_doc_ids.py (new migration script)

---

### ✅ BUG-002: Footer Template Literal (FIXED - 2026-01-09)

**Status**: COMPLETED

**What was fixed**:
- Removed the unrendered JavaScript template literal from footer
- Footer now only shows "Powered by" links (cleaner UI)
- The chunk count is already shown in the status message after initialization

**Files Modified**:
- index.html (removed lines 80-82)

---

## OPEN ISSUES

### 🟡 BUG-003: Missing Favicon

**Severity**: LOW - Cosmetic issue only
**Priority**: P3 - Nice to have
**Status**: Not Started

**Summary**:
Browser console shows 404 error for missing favicon.ico

**How to Fix**:
1. Create or obtain a favicon.ico file (16x16 or 32x32 icon)
2. Place it in the `public/` directory
3. Add favicon link in index.html `<head>`:
   ```html
   <link rel="icon" type="image/x-icon" href="/essay_search_engine/favicon.ico">
   ```

**Files to Modify**:
- Add `public/favicon.ico`
- Update `index.html` (add favicon link in head)

---

## SYSTEM HEALTH ✅

**Last verified**: 2026-01-09

### Current Statistics
- Total books: 17
- Total chunks: 758 (all with unique doc_ids)
- HTML chunk files: 758
- Metadata entries: 758 (no duplicates)

### Quick Verification Commands

Check for duplicate IDs:
```bash
jq '[.chunks[].chunk_id] | group_by(.) | map({id: .[0], count: length}) | sort_by(.count) | reverse | .[0:10]' public/data/metadata.json
```

Count files:
```bash
ls public/chunks/*.html | wc -l  # Should be 758
jq '.chunks | length' public/data/metadata.json  # Should be 758
```

Verify uniqueness:
```bash
jq '[.chunks[].chunk_id] | unique | length' public/data/metadata.json  # Should be 758
```
