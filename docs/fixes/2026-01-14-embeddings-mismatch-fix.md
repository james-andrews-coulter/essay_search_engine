# Fix: Embeddings/Metadata Mismatch Causing Search Crashes

**Date:** 2026-01-14
**Issue:** Search error: `undefined is not an object (evaluating 'f.book_title')`
**Status:** ✅ Fixed and Deployed

## Problem Summary

The deployed site was crashing when performing searches with the error:
```
Search error: undefined is not an object (evaluating 'f.book_title')
```

### Root Cause

**Data Mismatch:**
- `metadata.json` contained **1141 chunks** (array indices 0-1140)
- `embeddings.json` contained **1240 embeddings** (array indices 0-1239)
- **Result:** 99 embeddings without corresponding metadata chunks

**Why the mismatch occurred:**

1. **Duplicate doc_ids in source data:**
   - Books "Essential Ideas" and "Procrastination: How to do it well" had overlapping doc_ids (503-504)
   - This happened because doc_id ranges were not tracked in `books_metadata.json`

2. **Flawed incremental sync logic in `embed_chunks.py`:**
   ```python
   # WRONG: Assumes chunk_id is the array index
   if chunk_id < len(final_embeddings):
       final_embeddings[chunk_id] = new_embeddings_list[i]
   else:
       final_embeddings.append(new_embeddings_list[i])
   ```
   - Treated `chunk_id` (global document ID) as array index
   - Created embeddings array with gaps when chunk_ids were non-contiguous
   - Built embeddings array of size 1240 (highest chunk_id + 1) instead of 1141 (actual chunk count)

3. **Bug in `search.js`:**
   ```javascript
   // WRONG: Assumes embeddings[idx] matches metadata.chunks[idx]
   this.embeddings.embeddings.map((embedding, idx) => ({
     chunk: this.metadata.chunks[idx],  // undefined when idx >= 1141
     ...
   }))
   ```
   - When `idx >= 1141`, `metadata.chunks[idx]` returned `undefined`
   - Accessing `undefined.book_title` threw the error

## Solution

### Part 1: Defensive Code in `search.js`

**File:** `src/search.js`

**Change:** Added filter to remove undefined chunks:
```javascript
let results = this.embeddings.embeddings
  .map((embedding, idx) => ({
    chunk: this.metadata.chunks[idx],
    score: this.cosineSimilarity(queryEmbedding, embedding),
    baseSimilarity: this.cosineSimilarity(queryEmbedding, embedding),
  }))
  .filter((result) => result.chunk !== undefined);  // ADDED
```

**Why:** Prevents crashes even if data becomes misaligned in the future.

### Part 2: Fix Incremental Logic in `embed_chunks.py`

**File:** `sync/embed_chunks.py`

**Key Changes:**

1. **Ensure index-by-index alignment:**
   ```python
   # Build embeddings in exact metadata.chunks order
   embeddings_list = []
   for idx, chunk_meta in enumerate(metadata["chunks"]):
       chunk_id = chunk_meta["chunk_id"]
       if idx in chunk_indices:
           # This chunk was newly embedded
           embeddings_list.append(new_embeddings_list[new_embedding_idx])
           new_embedding_idx += 1
       else:
           # Reuse existing embedding (by chunk_id lookup)
           embeddings_list.append(existing_embeddings_map[chunk_id])
   ```

2. **Validate alignment before saving:**
   ```python
   if len(embeddings_list) != total_chunks:
       raise ValueError(
           f"Embeddings count ({len(embeddings_list)}) doesn't match metadata chunks ({total_chunks})"
       )
   ```

3. **Detect and warn about misaligned data:**
   ```python
   if len(existing_embeddings["embeddings"]) != total_chunks:
       print("⚠️  Existing embeddings don't match metadata chunks")
       print("   Will regenerate all embeddings to fix alignment issue")
   ```

**Why:** Ensures embeddings array always matches metadata.chunks array (same length, same order).

### Part 3: Fix Duplicate doc_ids

**File:** `sync/fix_doc_ids.py` (new script)

**Purpose:** Reassign sequential doc_ids to all chunks, ensuring uniqueness.

**What it does:**
1. Reads all books from `books_metadata.json`
2. Processes each book in order
3. Assigns sequential doc_ids starting from 0
4. Updates `doc_id` in each chunk's `chunks.json`
5. Adds `doc_id_start` and `doc_id_end` to book metadata
6. Saves updated data

**Result:**
- 1141 chunks with unique sequential doc_ids (0-1140)
- No gaps, no duplicates

**Usage:**
```bash
python3 sync/fix_doc_ids.py
```

### Part 4: Force Resync

After fixing the code and source data, ran a complete regeneration:

```bash
./lib --sync --force
```

**Results:**
- ✅ metadata.json: 1141 chunks
- ✅ embeddings.json: 1141 embeddings
- ✅ Perfect 1:1 alignment
- ✅ All chunk_ids sequential (0-1140)

## Verification

### Data Alignment Check
```bash
python3 -c "
import json
with open('public/data/metadata.json') as f:
    metadata = json.load(f)
with open('public/data/embeddings.json') as f:
    embeddings = json.load(f)
print(f'Metadata chunks: {len(metadata[\"chunks\"])}')
print(f'Embeddings: {len(embeddings[\"embeddings\"])}')
print(f'Match: {len(metadata[\"chunks\"]) == len(embeddings[\"embeddings\"])}')
"
```

**Output:**
```
Metadata chunks: 1141
Embeddings: 1141
Match: True
```

### Local Testing
1. Started dev server: `npm run dev`
2. Tested search queries
3. Verified no console errors
4. Confirmed results display correctly

### Deployment
1. Committed changes with descriptive message
2. Pushed to GitHub: `git push origin main`
3. GitHub Actions automatically deployed to GitHub Pages
4. Verified production site works correctly

## Files Changed

### Code Fixes
- `src/search.js` - Added defensive filter for undefined chunks
- `sync/embed_chunks.py` - Fixed incremental sync to maintain array order

### New Scripts
- `sync/fix_doc_ids.py` - Script to reassign sequential doc_ids

### Data Regenerated
- `public/data/metadata.json` - Regenerated with correct chunk order
- `public/data/embeddings.json` - Regenerated with matching alignment (24.72 MB)
- `public/data/tags.json` - Updated tag index (1643 tags)
- `public/tags.html` - Updated tag browsing page
- `public/chunks/*.html` - Regenerated 1141 chunk pages (159 new pages for previously missing IDs)

## Prevention

To prevent this issue from recurring:

1. **Validation in sync script:** `validate_chunks()` checks for duplicate doc_ids before processing
2. **Validation in embed script:** Checks embeddings count matches metadata chunks before saving
3. **doc_id tracking:** `books_metadata.json` now tracks `doc_id_start` and `doc_id_end` for each book
4. **Defensive code:** Search engine filters out undefined chunks gracefully
5. **Sequential assignment:** `fix_doc_ids.py` can be run anytime to fix doc_id issues

## Impact

- ✅ Search engine no longer crashes
- ✅ All 1141 chunks now searchable (previously 99 were unreachable)
- ✅ Data integrity maintained for future incremental syncs
- ✅ Clear error messages if data becomes misaligned again

## Lessons Learned

1. **Never conflate array indices with IDs:** Use explicit mapping, not assumptions
2. **Validate data alignment:** Always check array lengths match before operations
3. **Add defensive code:** Filter/check for undefined values in critical paths
4. **Track ID ranges:** Maintain metadata about ID assignments to prevent collisions
5. **Test with real data:** Gaps in IDs are common in real-world scenarios

## Related Issues

- Fixes GitHub Issue #8 (if created)
- Related to incremental sync feature implementation
- Resolves deployment crashes from 2026-01-14

---

**Commit:** `c1e7d0c` - "fix: resolve embeddings/metadata mismatch causing search crashes"
**Author:** Claude (Anthropic)
**Deployed:** 2026-01-14