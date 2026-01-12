# TOC-Based EPUB Parsing Design

**Date:** 2026-01-12
**Status:** Design Phase
**Goal:** Replace pattern-based chapter detection with TOC-based parsing and LLM filtering

---

## Problem Statement

The current EPUB parsing system uses regex pattern matching to detect chapter boundaries from HTML/Markdown formatting. This approach has two critical failures:

### Issue 1: Missing Chapters

**Example: "How to Age" by Anne Karpf**

Missing chapters:
- "Introduction" - appears as plain text, not detected as header
- "1. What is Age?" - has `?` punctuation, Pattern 2 only allows `[A-Za-z\s&\-:,]`
- "Conclusion" - appears as plain text, not detected as header

**Root Cause:** Chapters are detected by guessing from formatting patterns. Any chapter that doesn't match the 5 hardcoded regex patterns gets missed.

### Issue 2: Junk Chunks

**Example: Chunk 7 from "How to Age"**

```
## ISBN 978-1-250-05899-7 (e-book)

Originally published in Great Britain by Macmillan...
eISBN: 9781250058997
Explore All of the "Maintenance Manuals for the Mind"...
How to Think More About Sex
Alain de Botton
```

**Root Cause:** Filters check for copyright+ISBN combinations, but this chunk only has ISBN and promotional text. The pattern list is brittle and can't handle all variations.

---

## Current Approach (Pattern-Based)

### How It Works

1. **HTML Layer:** Scan all `<p>` tags, check against 5 regex patterns
2. **Markdown Layer:** Scan markdown text, check against same patterns
3. **Chunk Filter:** After semantic chunking, filter by keyword lists

### Patterns Used

```python
Pattern 1: Roman numerals (II, III, "II. Specialisation")
Pattern 2: Arabic numerals ("1. Trauma & anxiety") - limited punctuation
Pattern 3: "Chapter" keywords ("Chapter One", "CHAPTER 1")
Pattern 4: "Part" keywords ("Part I", "PART TWO")
Pattern 5: ALL-CAPS subsections ("SELF-HATRED & ANXIETY")
```

### Limitations

- Fragile: Every new formatting style requires a new pattern
- Incomplete: Can't handle arbitrary punctuation (`?`, `!`, etc.)
- No structure: Treats all chapters equally (no hierarchy)
- Keyword maintenance: Junk filter requires constant updates
- Guesswork: We're inferring structure instead of reading it

---

## New Approach (TOC-Based)

### Core Principle

**Use the author's Table of Contents as the source of truth.**

EPUBs contain a `toc.ncx` or `nav.xhtml` file that defines the book structure. The `ebooklib` library already parses this. Instead of guessing chapter boundaries from formatting, we read them directly from the TOC.

### Three-Stage Pipeline

**Stage 1: TOC Extraction**
- Use `ebooklib`'s `.toc` property to get book structure
- Flatten nested TOC tree (Part → Chapter → Section) into linear list
- Extract chapter titles and their corresponding EPUB document references

**Stage 2: LLM-Based TOC Filtering**
- Send entire TOC to Ollama for classification
- LLM identifies which entries are content vs junk (copyright, acknowledgments, etc.)
- Filter junk sections BEFORE any processing
- One LLM call per book (~2 seconds)

**Stage 3: Chapter-Aware Conversion**
- For each filtered TOC entry, fetch HTML content
- Convert HTML → Markdown using existing `html_to_markdown()`
- Inject chapter headers from TOC structure
- Concatenate into final markdown with proper boundaries

### Fallback Path

If `book.toc` is empty or malformed:
- Fall back to existing `epub_to_clean_markdown()` function
- Log warning for manual review
- Keeps system working for edge cases

---

## Architecture

### TOC Extraction

```python
def flatten_toc(toc, depth=0):
    """Recursively flatten nested TOC structure."""
    chapters = []
    for item in toc:
        if isinstance(item, epub.Link):
            chapters.append({
                'title': item.title,    # "1. What is Age?"
                'href': item.href,      # "ch1.xhtml"
                'depth': depth          # Nesting level
            })
        elif isinstance(item, epub.Section):
            chapters.append({
                'title': item.title,
                'href': None,           # Section may have no content
                'depth': depth
            })
        elif isinstance(item, list):
            chapters.extend(flatten_toc(item, depth + 1))
    return chapters
```

### Document Fetching

```python
def get_chapter_content(book, chapter):
    """Get HTML content for a TOC chapter."""
    if chapter['href'] is None:
        return None  # Section header with no content

    # Handle anchors: "ch1.xhtml#section2" -> "ch1.xhtml"
    href_base = chapter['href'].split('#')[0]

    # Get the EPUB item by filename
    item = book.get_item_with_href(href_base)
    if item:
        content = item.get_content()
        return BeautifulSoup(content, 'html.parser')
    return None
```

### LLM-Based TOC Filtering

```python
def filter_toc_with_llm(chapters, book_title):
    """Use LLM to classify TOC entries as content vs junk."""

    if not chapters:
        return chapters

    toc_list = '\n'.join(f"{i+1}. {ch['title']}" for i, ch in enumerate(chapters))

    prompt = f"""Book: "{book_title}"

Table of Contents:
{toc_list}

Which items are SUBSTANTIVE CONTENT (chapters, essays, arguments, advice, stories) vs METADATA/JUNK (copyright, acknowledgments, about the author, photo credits, ISBN, publisher info, also by, dedication)?

Return ONLY the numbers of SUBSTANTIVE items as comma-separated list.
Example: 1,3,4,7,8,9"""

    try:
        response = requests.post(
            'http://localhost:11434/api/generate',
            json={
                'model': 'qwen2.5:7b',
                'prompt': prompt,
                'stream': False,
                'options': {'temperature': 0.1}
            },
            timeout=30
        ).json()['response']

        # Parse: "1,3,4,7,8,9" -> [0,2,3,6,7,8]
        keep_indices = [int(x.strip()) - 1 for x in response.split(',') if x.strip()]
        filtered = [chapters[i] for i in keep_indices if 0 <= i < len(chapters)]

        print(f"  TOC filter: kept {len(filtered)}/{len(chapters)} chapters")
        return filtered

    except Exception as e:
        print(f"  WARNING: TOC filter failed ({e}), keeping all chapters")
        return chapters

```

### Main Conversion Function

```python
def epub_to_markdown_with_toc(epub_path):
    """Convert EPUB to markdown using TOC structure with LLM filtering."""

    print(f"Reading EPUB: {epub_path}")
    book = epub.read_epub(str(epub_path))

    # Extract metadata
    title_meta = book.get_metadata('DC', 'title')
    book_title = title_meta[0][0] if title_meta else Path(epub_path).stem

    author_meta = book.get_metadata('DC', 'creator')
    book_author = author_meta[0][0] if author_meta else "Unknown Author"

    print(f"Book: {book_title}")
    print(f"Author: {book_author}")

    # Extract and flatten TOC
    chapters = flatten_toc(book.toc)

    if not chapters:
        print("  WARNING: No TOC found, falling back to old method")
        return epub_to_clean_markdown(epub_path)

    print(f"  Found {len(chapters)} TOC entries")

    # Filter junk chapters with LLM
    chapters = filter_toc_with_llm(chapters, book_title)

    # Build markdown
    markdown_parts = []
    markdown_parts.append(f"# {book_title}\n\n")
    markdown_parts.append(f"**Author:** {book_author}\n\n")
    markdown_parts.append("---\n\n")

    processed_count = 0
    for chapter in chapters:
        soup = get_chapter_content(book, chapter)
        if soup is None:
            continue

        # Remove scripts/styles
        for script in soup(["script", "style"]):
            script.decompose()

        # Add chapter header from TOC
        markdown_parts.append(f"## {chapter['title']}\n\n")

        # Convert to markdown
        chapter_markdown = html_to_markdown(soup)
        if chapter_markdown.strip():
            markdown_parts.append(chapter_markdown)
            processed_count += 1

    print(f"  Processed {processed_count} chapters")

    final_markdown = ''.join(markdown_parts)
    final_markdown = re.sub(r'\n{3,}', '\n\n', final_markdown)

    return final_markdown, book_title, book_author
```

---

## Changes to Existing Code

### Functions Removed

```python
normalize_chapter_markers()      # ~100 lines - HTML pattern detection
normalize_markdown_headers()     # ~50 lines - Markdown pattern detection
CHAPTER_DETECTION_CONFIG         # No longer needed
```

### Functions Added

```python
flatten_toc()                    # ~20 lines - TOC tree flattening
get_chapter_content()            # ~15 lines - Fetch HTML by href
filter_toc_with_llm()            # ~30 lines - LLM classification
epub_to_markdown_with_toc()      # ~60 lines - New main function
```

### Functions Unchanged

```python
html_to_markdown()               # Still used for HTML → Markdown
chunk_markdown_hierarchically()  # Still uses LlamaIndex
generate_tags_with_ollama()      # Still generates semantic tags
is_table_of_contents()           # Kept as safety net
is_bibliography()                # Kept as safety net
```

### Integration Point

Replace in `main()`:

```python
# OLD:
markdown_content, book_title, author = epub_to_clean_markdown(epub_path)

# NEW:
markdown_content, book_title, author = epub_to_markdown_with_toc(epub_path)
```

---

## Benefits

### Robustness

- Works with ANY chapter naming convention (no regex limitations)
- Handles arbitrary punctuation (`?`, `!`, emoji, unicode, etc.)
- Uses author's intended structure (most reliable)
- LLM handles edge cases patterns can't

### Simplicity

- **~50 lines less code** (remove pattern detection, add TOC extraction)
- No regex maintenance
- No keyword list updates
- Outsources to proven code (ebooklib + Ollama)

### Performance

- **30-60 seconds faster per book** (skip junk chapter processing)
- TOC filtering: 1 LLM call (~2 seconds)
- No HTML conversion for filtered chapters
- No tag generation for filtered chapters

### Coverage

For "How to Age":
- ✅ Captures "Introduction"
- ✅ Captures "1. What is Age?" (with `?`)
- ✅ Captures "Conclusion"
- ✅ Filters "Copyright" (ISBN chunk)
- ✅ Filters "Acknowledgements"
- ✅ Filters "About the Author"

---

## Edge Cases

### 1. Nested TOC Structure

**Example:**
```
Part I: The Problem
  - Chapter 1: Introduction
  - Chapter 2: History
Part II: The Solution
  - Chapter 3: Methods
```

**Handled by:** `flatten_toc()` recursively flattens nested lists

### 2. Missing TOC

**Example:** Poorly formatted EPUB with no `toc.ncx`

**Handled by:** Fallback to existing `epub_to_clean_markdown()`

### 3. TOC with Anchors

**Example:** `href="chapter1.xhtml#section2"`

**Handled by:** `get_chapter_content()` strips anchors (`split('#')[0]`)

### 4. Section Headers without Content

**Example:** "Part I" as separator, no actual text

**Handled by:** `get_chapter_content()` returns `None`, skipped gracefully

### 5. LLM Filtering Failure

**Example:** Ollama down, timeout, parsing error

**Handled by:** Exception caught, returns unfiltered chapters (fail-safe)

---

## Testing Strategy

### Before/After Comparison

Test with "How to Age":

```bash
# Process with old method
./lib "How to Age.epub"
# Check private/books/How_to_Age_The_School_of_Life/chunks.json
# Count chunks, verify which chapters captured

# Process with new method
./lib "How to Age.epub" --replace
# Check private/books/How_to_Age_The_School_of_Life/chunks.json
# Count chunks, verify Introduction/Conclusion captured, ISBN filtered
```

### Validation Checks

1. **Chapter count increases** (Introduction, Conclusion now captured)
2. **Junk chunks decrease** (Copyright, ISBN filtered)
3. **All chapter titles have proper headers** (from TOC, not pattern detection)
4. **No duplicate chapters** (TOC ensures uniqueness)
5. **Fallback works** (test with EPUB without TOC)

### Regression Testing

Process all existing books:
- Verify no books break
- Check chunk counts stay similar (±10%)
- Spot-check that important chapters still captured

---

## Performance Characteristics

### Old Method (Pattern-Based)

```
Stage 1: HTML pattern detection     ~100ms
Stage 2: Markdown pattern detection ~50ms
Stage 3: Process all chapters       ~30s (tag generation)
Stage 4: Chunk filtering           ~500ms
─────────────────────────────────────────
TOTAL                              ~30.65s
```

### New Method (TOC-Based)

```
Stage 1: TOC extraction             ~50ms
Stage 2: LLM TOC filtering         ~2s
Stage 3: Process filtered chapters  ~20s (fewer chapters)
Stage 4: Chunking                  ~500ms (no junk filtering)
─────────────────────────────────────────
TOTAL                              ~22.55s
```

**Savings:** ~8-10 seconds per book (26% faster)

---

## Future Enhancements

### Phase 2: Hierarchical Structure

Preserve TOC nesting for hierarchical navigation:

```json
{
  "title": "Part I: The Problem",
  "chapters": [
    {"title": "Chapter 1: Introduction", "chunks": [...]},
    {"title": "Chapter 2: History", "chunks": [...]}
  ]
}
```

### Phase 3: TOC-Based Search Filters

Enable filtering by book sections:
- "Show only Part II chapters"
- "Search within Introduction sections"

### Phase 4: Cross-Book Structure Analysis

Compare book structures:
- Find books with similar organization
- Identify common section types across library

---

## Implementation Checklist

- [ ] Add `flatten_toc()` function
- [ ] Add `get_chapter_content()` function
- [ ] Add `filter_toc_with_llm()` function
- [ ] Add `epub_to_markdown_with_toc()` function
- [ ] Update `main()` to call new function
- [ ] Test with "How to Age"
- [ ] Verify Introduction/Conclusion captured
- [ ] Verify ISBN chunk filtered
- [ ] Test with 2-3 other books for regression
- [ ] Update CLAUDE.md with new approach
- [ ] Commit changes

---

## Success Criteria

✅ "How to Age" captures Introduction, "1. What is Age?", and Conclusion
✅ "How to Age" filters ISBN/copyright chunks
✅ All existing books still process without errors
✅ Chunk counts stay within ±10% for existing books
✅ Code is simpler (~50 lines less)
✅ Processing is faster (~8-10s saved per book)

---

**Next Step:** Implementation (see `2026-01-12-toc-based-epub-parsing.md`)
