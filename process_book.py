#!/usr/bin/env python3
"""
EPUB to Markdown converter with hybrid semantic search indexing.
Converts EPUBs and adds them to a unified searchable library.
"""

import os
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'
os.environ['TOKENIZERS_PARALLELISM'] = 'false'

from pathlib import Path
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
import sys
import re
import json
import argparse
from datetime import datetime
import requests


def check_ollama_available():
    """Check if Ollama is running and has the required model."""
    try:
        response = requests.get('http://localhost:11434/api/tags', timeout=5)
        if response.status_code != 200:
            return False, "Ollama is not responding correctly"

        # Check if qwen2.5:7b model is available
        models = response.json().get('models', [])
        model_names = [model.get('name', '') for model in models]

        if not any('qwen2.5:7b' in name for name in model_names):
            return False, "qwen2.5:7b model not found"

        return True, "Ollama is ready"
    except requests.exceptions.ConnectionError:
        return False, "Cannot connect to Ollama (is it running?)"
    except Exception as e:
        return False, f"Error checking Ollama: {e}"


# Chapter detection configuration
CHAPTER_DETECTION_CONFIG = {
    'enable_html_normalization': True,
    'enable_markdown_normalization': True,
}

# Chunk filtering configuration
CHUNK_FILTER_CONFIG = {
    'enable_toc_filter': True,
    'enable_bibliography_filter': True,
    'enable_diagnostic_output': False,  # Set to True to see what's being filtered

    # Thresholds
    'toc_min_list_ratio': 0.4,  # 40% of lines are list items
    'bibliography_min_citation_density': 0.3,  # 30% of lines are citations
}

# TOC Detection Patterns
TOC_TITLE_PATTERNS = [
    r'^contents?$',
    r'^table of contents?$',
    r'^list of (chapters?|sections?)$',
]

TOC_SECTION_KEYWORDS = [
    'introduction', 'preface', 'foreword', 'prologue', 'epilogue',
    'acknowledgments', 'acknowledgements', 'bibliography', 'references',
    'appendix', 'index', 'glossary', 'afterword', 'conclusion',
    'some final thoughts', 'homework', 'further reading', 'notes',
]

# Bibliography Detection Patterns
BIBLIOGRAPHY_TITLE_PATTERNS = [
    r'^bibliograph(y|ies)$',
    r'^references?$',
    r'^works? cited$',
    r'^sources?$',
    r'^further reading$',
    r'^selected bibliograph(y|ies)$',
    r'^notes?$',
    r'^endnotes?$',
]

BIBLIOGRAPHY_CITATION_PATTERNS = [
    r'\b(tr\.|ed\.|intro\.|foreword|afterword)\s',  # Translator/editor abbreviations
    r'\([12]\d{3}\)',  # Publication years (1900-2999)
    r'\(.*?:\s*[A-Z][a-z]+',  # (City: Publisher...
    r'Harmondsworth:\s*Penguin',  # Common publisher patterns
    r'(New York|London|Paris|Oxford|Cambridge|Chicago|Boston):\s*\w+',
]


def html_to_markdown(soup):
    """Convert BeautifulSoup HTML to markdown, preserving structure."""
    markdown_lines = []

    for element in soup.descendants:
        if element.name is None:
            continue

        if element.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            level = int(element.name[1])
            text = element.get_text().strip()
            if text:
                markdown_lines.append(f"{'#' * level} {text}\n\n")

        elif element.name == 'p':
            text = element.get_text().strip()
            if text:
                markdown_lines.append(f"{text}\n\n")

        elif element.name == 'li':
            text = element.get_text().strip()
            if text and element.parent.name in ['ul', 'ol']:
                prefix = '-' if element.parent.name == 'ul' else '1.'
                markdown_lines.append(f"{prefix} {text}\n")

        elif element.name == 'blockquote':
            text = element.get_text().strip()
            if text:
                quoted = '\n'.join(f"> {line}" for line in text.split('\n'))
                markdown_lines.append(f"{quoted}\n\n")

        elif element.name == 'br':
            markdown_lines.append('\n')

    return ''.join(markdown_lines)


def normalize_chapter_markers(soup):
    """
    Detect plain-text chapter markers in <p> tags and convert to proper HTML headers.

    This function handles books with inconsistent heading structure where chapters
    are formatted as plain text instead of proper HTML headers.

    Patterns detected:
    - Roman numerals: "II. Specialisation", "IISpecialisation", "III Introduction"
    - Arabic numerals: "1. Chapter Title", "2.", "Chapter 3"
    - Keywords: "Chapter One", "CHAPTER 1", "Part II"

    Returns: Modified BeautifulSoup object with normalized headers
    """
    if not CHAPTER_DETECTION_CONFIG['enable_html_normalization']:
        return soup

    # Pattern definitions with priority order
    patterns = [
        # Pattern 1: Roman numeral with optional period + title
        # Matches: "II. Specialisation", "IISpecialisation", "III Introduction"
        {
            'regex': re.compile(
                r'^([IVX]{1,10})\.?\s*([A-Z][a-zA-Z\s].*)?$'
            ),
            'level': 2,
            'name': 'roman_numeral'
        },

        # Pattern 2: Arabic numeral with period + title
        # Matches: "1. Hyperactivity", "10. Creative Play"
        {
            'regex': re.compile(r'^(\d{1,3})\.\s+([A-Z][A-Za-z\s]{3,})$'),
            'level': 2,
            'name': 'arabic_numeral'
        },

        # Pattern 3: "Chapter" keyword patterns
        # Matches: "Chapter 1", "CHAPTER ONE", "Chapter One: Title"
        {
            'regex': re.compile(
                r'^(Chapter|CHAPTER)\s+([IVX]{1,10}|\d{1,3}|One|Two|Three|Four|Five|Six|Seven|Eight|Nine|Ten)'
                r'(:?\s*[A-Z].*)?$'
            ),
            'level': 2,
            'name': 'chapter_keyword'
        },

        # Pattern 4: "Part" keyword patterns
        # Matches: "Part I", "PART TWO", "Part 1: The Problem"
        {
            'regex': re.compile(
                r'^(Part|PART)\s+([IVX]{1,10}|\d{1,3}|One|Two|Three|Four|Five|ONE|TWO|THREE|FOUR|FIVE)'
                r'(:?\s*[A-Z].*)?$'
            ),
            'level': 2,
            'name': 'part_keyword'
        }
    ]

    conversions = {pattern['name']: 0 for pattern in patterns}

    # Iterate through all <p> tags
    for p_tag in soup.find_all('p'):
        text = p_tag.get_text().strip()

        # Skip empty or very long paragraphs (likely not chapter markers)
        if not text or len(text) > 100:
            continue

        # Check against each pattern
        for pattern_def in patterns:
            match = pattern_def['regex'].match(text)
            if match:
                # Handle edge case: "IISpecialisation" → inject space
                if pattern_def['name'] == 'roman_numeral':
                    text = re.sub(r'^([IVX]+)([A-Z][a-z])', r'\1. \2', text)

                # Convert <p> to <h2> (or appropriate level)
                new_tag = soup.new_tag(f"h{pattern_def['level']}")
                new_tag.string = text
                p_tag.replace_with(new_tag)
                conversions[pattern_def['name']] += 1
                break  # Stop after first match

    # Print diagnostic output
    total_conversions = sum(conversions.values())
    if total_conversions > 0:
        print(f"  HTML normalization: {total_conversions} chapters detected")
        for name, count in conversions.items():
            if count > 0:
                print(f"    - {name}: {count}")

    return soup


def normalize_markdown_headers(markdown_content):
    """
    Post-process markdown to add headers where plain-text chapter markers exist.

    This is a fallback for patterns missed by HTML normalization, operating
    directly on markdown text to inject ## headers.

    Handles edge cases like:
    - Chapters that span multiple <p> tags in HTML
    - Unusual spacing/formatting in source
    """
    if not CHAPTER_DETECTION_CONFIG['enable_markdown_normalization']:
        return markdown_content

    lines = markdown_content.split('\n')
    normalized_lines = []

    # Same patterns as HTML normalization, but operating on markdown text
    chapter_patterns = [
        # Roman numeral patterns
        re.compile(r'^([IVX]{1,10})\.?\s+([A-Z][a-zA-Z].*)$'),
        # Arabic numeral patterns
        re.compile(r'^(\d{1,3})\.\s+([A-Z][A-Za-z\s]{3,})$'),
        # Chapter/Part keywords (case-insensitive for word numbers)
        re.compile(r'^(Chapter|CHAPTER|Part|PART)\s+([IVX\d]+|One|Two|Three|Four|Five|Six|Seven|Eight|Nine|Ten|ONE|TWO|THREE|FOUR|FIVE|SIX|SEVEN|EIGHT|NINE|TEN).*$')
    ]

    for line in lines:
        stripped = line.strip()

        # Skip if already a header or empty line
        if stripped.startswith('#') or not stripped:
            normalized_lines.append(line)
            continue

        # Check if line matches chapter pattern
        matched = False
        for pattern in chapter_patterns:
            if pattern.match(stripped):
                # Convert to H2 header
                normalized_lines.append(f"## {stripped}")
                matched = True
                break

        if not matched:
            normalized_lines.append(line)

    return '\n'.join(normalized_lines)


def epub_to_clean_markdown(epub_path):
    """Extract clean markdown from epub using ebooklib."""
    print(f"Reading EPUB: {epub_path}")
    book = epub.read_epub(str(epub_path))

    # Get book metadata
    title_meta = book.get_metadata('DC', 'title')
    book_title = title_meta[0][0] if title_meta else Path(epub_path).stem

    author_meta = book.get_metadata('DC', 'creator')
    book_author = author_meta[0][0] if author_meta else "Unknown Author"

    print(f"Book: {book_title}")
    print(f"Author: {book_author}")

    markdown_parts = []
    markdown_parts.append(f"# {book_title}\n\n")
    markdown_parts.append(f"**Author:** {book_author}\n\n")
    markdown_parts.append("---\n\n")

    document_count = 0
    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            document_count += 1
            content = item.get_content()
            soup = BeautifulSoup(content, 'html.parser')

            for script in soup(["script", "style"]):
                script.decompose()

            # Layer 1: Normalize chapter markers in HTML
            soup = normalize_chapter_markers(soup)

            markdown_text = html_to_markdown(soup)

            if markdown_text.strip():
                markdown_parts.append(markdown_text)

    print(f"Processed {document_count} document sections")

    final_markdown = ''.join(markdown_parts)

    # Layer 2: Normalize chapter markers in markdown
    final_markdown = normalize_markdown_headers(final_markdown)

    final_markdown = re.sub(r'\n{3,}', '\n\n', final_markdown)

    return final_markdown, book_title, book_author


def generate_tags_with_ollama(text, book_title, chapter_title, model="qwen2.5:7b"):
    """Generate semantic tags for a text chunk using Ollama."""
    # Extract key sentences from beginning, middle, and end for better theme understanding
    words = text.split()
    if len(words) > 600:
        # Take first 200, middle 200, last 200 words for better coverage
        sample = ' '.join(words[:200]) + ' [...] ' + ' '.join(words[len(words)//2-100:len(words)//2+100]) + ' [...] ' + ' '.join(words[-200:])
    else:
        sample = text

    prompt = f"""Read this passage from "{book_title}" and identify what it's REALLY about.

Chapter: {chapter_title}

Passage:
{sample}

Generate 3-5 tags that capture the MAIN THEME, key concepts, and close synonyms. DO NOT INVENT TAGS IF THEY DON'T RELATE TO THE PASSAGE. 

Rules:
- Focus on what the passage teaches or explores, not just words mentioned
- Use natural search terms: "envy" not "competitive-dynamics"
- Include closely related synonyms: "envy" and "jealousy" and "competition"
- Keep tags SHORT: 1 word maxiumum
- Maximum 5 tags

Output format: comma-separated lowercase tags ONLY, no explanation
Example: jealousy, comparison, inferiority, envy, insecurity, rivalry"""

    try:
        response = requests.post(
            'http://localhost:11434/api/generate',
            json={
                'model': model,
                'prompt': prompt,
                'stream': False,
                'options': {
                    'temperature': 0.3,  # Lower temperature for more focused tags
                    'num_predict': 50    # Limit output length
                }
            },
            timeout=30
        )

        if response.status_code == 200:
            tags_text = response.json()['response'].strip()
            # Clean up the response
            tags_text = tags_text.strip('"').strip("'").strip()
            # Remove any leading/trailing brackets or quotes
            tags_text = tags_text.replace('["', '').replace('"]', '').replace('[', '').replace(']', '')
            # Remove extra quotes around individual tags
            tags_text = tags_text.replace('"', '').replace("'", '')
            # Clean up extra whitespace and limit to 5 tags maximum
            tags_list = [tag.strip() for tag in tags_text.split(',') if tag.strip()]
            tags_list = tags_list[:5]  # Hard limit to 5 tags
            return ', '.join(tags_list)
        else:
            raise RuntimeError(f"Ollama returned status {response.status_code}")
    except requests.exceptions.ConnectionError:
        raise RuntimeError("Cannot connect to Ollama (is it running?)")
    except Exception as e:
        if isinstance(e, RuntimeError):
            raise
        raise RuntimeError(f"Error generating tags: {e}")


def is_table_of_contents(chapter_title, content, word_count):
    """
    Detect if chunk is a Table of Contents.

    Primary signal: Chapter title contains "contents"
    Secondary validation: High ratio of list items or TOC section keywords

    Returns:
        tuple: (is_toc: bool, reason: str)
    """
    title_lower = chapter_title.lower().strip()

    # Primary signal: Title match
    title_is_toc = any(re.match(pattern, title_lower) for pattern in TOC_TITLE_PATTERNS)

    if not title_is_toc:
        return False, ""

    # Secondary validation: Content analysis
    lines = [l.strip() for l in content.split('\n') if l.strip() and not l.strip().startswith('#')]

    if len(lines) == 0:
        return True, "empty TOC"

    # Count list items (numbered or Roman numerals)
    list_lines = sum(1 for l in lines if re.match(r'^\d+\.', l) or re.match(r'^[IVX]+\.', l))

    # Count TOC section keywords
    toc_keyword_lines = sum(1 for l in lines
                           if any(keyword in l.lower() for keyword in TOC_SECTION_KEYWORDS))

    list_ratio = list_lines / len(lines) if lines else 0
    keyword_ratio = toc_keyword_lines / len(lines) if lines else 0

    # Filter if:
    # - Mostly numbered lists, OR
    # - Mostly TOC keywords (chapter/section names), OR
    # - Very short with some TOC keywords
    is_toc = (
        list_ratio >= CHUNK_FILTER_CONFIG['toc_min_list_ratio'] or
        keyword_ratio >= 0.4 or
        (word_count < 100 and keyword_ratio >= 0.2)
    )

    if is_toc:
        reason = f"list_ratio={list_ratio:.2f}, keyword_ratio={keyword_ratio:.2f}"
        return True, reason

    return False, ""


def is_bibliography(chapter_title, content, word_count):
    """
    Detect if chunk is a Bibliography/References section.

    Primary signal: Chapter title is "Bibliography", "References", etc.
    Secondary validation: High density of academic citation patterns

    Returns:
        tuple: (is_bib: bool, reason: str)
    """
    title_lower = chapter_title.lower().strip()

    # Primary signal: Title match
    title_is_bib = any(re.match(pattern, title_lower) for pattern in BIBLIOGRAPHY_TITLE_PATTERNS)

    if not title_is_bib:
        return False, ""

    # Secondary validation: Citation pattern density
    lines = [l.strip() for l in content.split('\n') if l.strip() and not l.strip().startswith('#')]

    if len(lines) == 0:
        return True, "empty bibliography"

    # Count lines matching citation patterns
    citation_lines = 0
    for line in lines:
        # A line is a citation if it matches multiple citation patterns
        pattern_matches = sum(1 for pattern in BIBLIOGRAPHY_CITATION_PATTERNS
                             if re.search(pattern, line))
        if pattern_matches >= 2:  # At least 2 citation indicators
            citation_lines += 1

    citation_density = citation_lines / len(lines) if lines else 0

    # Additional signals for bibliographies
    has_author_names = bool(re.findall(r'\b[A-Z][a-z]+,\s*[A-Z]', content))  # "Smith, J."
    has_multiple_years = len(re.findall(r'\([12]\d{3}\)', content)) >= 3

    is_bib = (
        citation_density >= CHUNK_FILTER_CONFIG['bibliography_min_citation_density'] or
        (citation_density >= 0.2 and has_author_names and has_multiple_years)
    )

    if is_bib:
        reason = f"citation_density={citation_density:.2f}, authors={has_author_names}, years={has_multiple_years}"
        return True, reason

    return False, ""


def chunk_markdown_hierarchically(markdown_content, book_title):
    """Split markdown into hierarchical chunks using LlamaIndex."""
    from llama_index.core import Document
    from llama_index.core.node_parser import MarkdownNodeParser

    print("\nChunking markdown into hierarchical sections...")

    document = Document(text=markdown_content, metadata={"title": book_title})
    parser = MarkdownNodeParser()
    nodes = parser.get_nodes_from_documents([document])

    # Metadata/junk keywords to filter out
    junk_patterns = [
        'contents',
        'table of contents',
        'copyright',
        'published in',
        'isbn',
        'all rights reserved',
        'cover',
        'title page',
        'dedication',
        'acknowledgments',
        'acknowledgements',
        'about the author',
        'also by',
        'other books',
        'guide',
        'designed and typeset',
        'first published',
        'ISBN',
        'illustration list',
        'image credits',
        'series editor',
        'dedicated to exploring',
        'dedicated to helping',
        'visit us at',
        'follow us on',
        'announces a rebirth',
        'series that examines'
    ]

    chunks = []
    filtered_count = 0
    filter_reasons = {}  # Track why chunks were filtered (for diagnostics)

    print("Generating semantic tags for chunks (this may take a few minutes)...")

    for i, node in enumerate(nodes):
        content = node.get_content()
        content_lower = content.lower()
        word_count = len(content.split())
        lines = [l.strip() for l in content.split('\n') if l.strip()]

        # === EXTRACT CHAPTER TITLE FIRST (needed for title-based filtering) ===
        chapter_title = "Unknown Chapter"
        for line in content.split('\n'):
            line = line.strip()
            if line.startswith('#'):
                chapter_title = line.lstrip('#').strip()
                break

        # === FILTER 1: MINIMUM LENGTH ===
        if word_count < 30:
            filtered_count += 1
            filter_reasons['too_short'] = filter_reasons.get('too_short', 0) + 1
            continue

        # === FILTER 2: TABLE OF CONTENTS (new dedicated filter) ===
        if CHUNK_FILTER_CONFIG['enable_toc_filter']:
            is_toc, toc_reason = is_table_of_contents(chapter_title, content, word_count)
            if is_toc:
                filtered_count += 1
                filter_reasons['table_of_contents'] = filter_reasons.get('table_of_contents', 0) + 1
                if CHUNK_FILTER_CONFIG['enable_diagnostic_output']:
                    print(f"  [FILTERED TOC] {chapter_title[:40]} - {toc_reason}")
                continue

        # === FILTER 3: BIBLIOGRAPHY/REFERENCES (new dedicated filter) ===
        if CHUNK_FILTER_CONFIG['enable_bibliography_filter']:
            is_bib, bib_reason = is_bibliography(chapter_title, content, word_count)
            if is_bib:
                filtered_count += 1
                filter_reasons['bibliography'] = filter_reasons.get('bibliography', 0) + 1
                if CHUNK_FILTER_CONFIG['enable_diagnostic_output']:
                    print(f"  [FILTERED BIBLIOGRAPHY] {chapter_title[:40]} - {bib_reason}")
                continue

        # === FILTER 4: COPYRIGHT/PUBLICATION METADATA ===
        has_copyright = 'copyright' in content_lower or '©' in content
        has_isbn = 'isbn' in content_lower
        has_published = 'published in' in content_lower or 'first published' in content_lower

        if (has_copyright and has_isbn) or (has_copyright and has_published and word_count < 300):
            filtered_count += 1
            filter_reasons['copyright_metadata'] = filter_reasons.get('copyright_metadata', 0) + 1
            continue

        # Skip chunks with standalone ISBN numbers (publication metadata)
        if re.search(r'isbn:\s*978-[\d-]+', content_lower) and word_count < 200:
            filtered_count += 1
            filter_reasons['isbn_metadata'] = filter_reasons.get('isbn_metadata', 0) + 1
            continue

        # === FILTER 5: FRONT/BACK MATTER (dedications, acknowledgments, etc) ===
        # Skip if contains multiple junk keywords
        junk_word_count = sum(1 for pattern in junk_patterns if pattern in content_lower)
        if junk_word_count >= 3:
            filtered_count += 1
            filter_reasons['multiple_junk_keywords'] = filter_reasons.get('multiple_junk_keywords', 0) + 1
            continue

        # Skip "Guide" sections that are just lists
        if 'guide' in content_lower and word_count < 100:
            filtered_count += 1
            filter_reasons['guide_section'] = filter_reasons.get('guide_section', 0) + 1
            continue

        # === FILTER 6: ILLUSTRATION LISTS AND IMAGE CREDITS ===
        if 'illustration list' in content_lower or 'also available from' in content_lower:
            filtered_count += 1
            filter_reasons['illustration_list'] = filter_reasons.get('illustration_list', 0) + 1
            continue

        # Skip if it's mostly a list of images/photos (photo credits)
        photo_credit_patterns = ['photo ©', 'oil on canvas', 'cm.', 'bridgeman images', 'tate, london', 'metropolitan museum']
        photo_matches = sum(1 for pattern in photo_credit_patterns if pattern in content_lower)
        if photo_matches >= 3 and word_count < 300:
            filtered_count += 1
            filter_reasons['image_credits'] = filter_reasons.get('image_credits', 0) + 1
            continue

        # === FILTER 7: PUBLISHER BRANDING/PROMOTIONAL CONTENT ===
        # Skip publisher branding/promotional content (contains URLs/website domains)
        url_patterns = re.findall(r'(?:[a-zA-Z0-9-]+\.)+(?:com|org|net|edu|gov|io|co\.uk)', content_lower)
        if url_patterns and word_count < 250:
            # Short chunks with URLs are likely promotional/branding
            filtered_count += 1
            filter_reasons['publisher_branding'] = filter_reasons.get('publisher_branding', 0) + 1
            continue

        # === CHUNK PASSED ALL FILTERS - GENERATE TAGS AND SAVE ===
        print(f"  Chunk {len(chunks) + 1}: {chapter_title[:50]}...")
        tags = generate_tags_with_ollama(content, book_title, chapter_title)

        chunk_data = {
            "chunk_id": len(chunks),  # Reindex after filtering
            "content": content,
            "chapter_title": chapter_title,
            "tags": tags,
            "metadata": {
                "char_count": len(content),
                "word_count": word_count,
                "chapter_title": chapter_title,
                "tags": tags,
                **node.metadata
            }
        }
        chunks.append(chunk_data)

    # Print filtering summary
    print(f"\nCreated {len(chunks)} chunks (filtered {filtered_count} metadata/junk chunks)")

    if CHUNK_FILTER_CONFIG['enable_diagnostic_output'] and filter_reasons:
        print("\nFilter breakdown:")
        for reason, count in sorted(filter_reasons.items(), key=lambda x: x[1], reverse=True):
            print(f"  - {reason}: {count}")

    return chunks


def save_chunks(chunks, output_dir, book_title):
    """Save chunks to both JSON and individual markdown files."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    safe_title = re.sub(r'[^\w\s-]', '', book_title)
    safe_title = re.sub(r'[-\s]+', '_', safe_title)

    chunks_dir = output_path / safe_title
    chunks_dir.mkdir(exist_ok=True)

    json_path = chunks_dir / "chunks.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(chunks, f, indent=2, ensure_ascii=False)

    print(f"\n✓ Chunks saved to JSON: {json_path}")

    for chunk in chunks:
        chunk_filename = f"chunk_{chunk['chunk_id']:03d}.md"
        chunk_path = chunks_dir / chunk_filename

        chunk_content = f"""---
chunk_id: {chunk['chunk_id']}
chapter_title: {chunk['chapter_title']}
tags: {chunk['tags']}
char_count: {chunk['metadata']['char_count']}
word_count: {chunk['metadata']['word_count']}
---

{chunk['content']}
"""
        chunk_path.write_text(chunk_content, encoding='utf-8')

    print(f"✓ Individual chunk files saved to: {chunks_dir}")
    print(f"  Total chunks: {len(chunks)}")

    total_words = sum(c['metadata']['word_count'] for c in chunks)
    avg_words = total_words // len(chunks) if chunks else 0
    print(f"\nChunk Statistics:")
    print(f"  Total words: {total_words:,}")
    print(f"  Average words per chunk: {avg_words:,}")
    print(f"  Smallest chunk: {min(c['metadata']['word_count'] for c in chunks):,} words")
    print(f"  Largest chunk: {max(c['metadata']['word_count'] for c in chunks):,} words")


def update_books_metadata(chunks, book_title, author, index_dir, chunk_dir, auto_replace=False):
    """Update the books_metadata.json file with new book information."""
    metadata_path = index_dir / "books_metadata.json"

    # Load or create metadata
    if metadata_path.exists():
        with open(metadata_path, 'r') as f:
            books_metadata = json.load(f)
    else:
        books_metadata = {"books": [], "next_id": 0}

    # Check if book already exists
    safe_title = re.sub(r'[^\w\s-]', '', book_title)
    safe_title = re.sub(r'[-\s]+', '_', safe_title)

    existing_book = next((b for b in books_metadata["books"] if b["safe_title"] == safe_title), None)

    if existing_book:
        if auto_replace:
            print(f"\n⚠️  Book '{book_title}' already in metadata - replacing...")
        else:
            print(f"\n⚠️  Book '{book_title}' already in metadata!")
            response = input("Replace it? (y/N): ").strip().lower()
            if response != 'y':
                print("Skipping...")
                return
        # Remove old book metadata
        books_metadata["books"] = [b for b in books_metadata["books"] if b["safe_title"] != safe_title]

    # Get starting ID
    start_id = books_metadata["next_id"]

    print(f"\nUpdating metadata for {len(chunks)} chunks...")
    print(f"Book: {book_title} by {author}")

    # Update metadata
    books_metadata["books"].append({
        "title": book_title,
        "author": author,
        "safe_title": safe_title,
        "chunk_count": len(chunks),
        "chunk_dir": str(chunk_dir),
        "added_date": datetime.now().isoformat(),
        "id_range": [start_id, start_id + len(chunks) - 1]
    })
    books_metadata["next_id"] = start_id + len(chunks)

    # Ensure directory exists
    metadata_path.parent.mkdir(parents=True, exist_ok=True)

    with open(metadata_path, 'w') as f:
        json.dump(books_metadata, f, indent=2)

    print(f"✓ Metadata updated: {metadata_path}")
    print(f"✓ Total books: {len(books_metadata['books'])}")


def list_books(index_dir):
    """List all books in the unified index."""
    index_dir = Path(index_dir).expanduser()
    metadata_path = index_dir / "books_metadata.json"

    if not metadata_path.exists():
        print("No books found in library.")
        print(f"Library location: {index_dir}")
        return

    with open(metadata_path) as f:
        books_metadata = json.load(f)

    books = books_metadata.get("books", [])

    if not books:
        print("No books found in library.")
        print(f"Library location: {index_dir}")
        return

    print(f"\n{'='*80}")
    print(f"Books in Library: {index_dir}")
    print(f"{'='*80}\n")

    for i, book in enumerate(books, 1):
        title = book.get("title", "Unknown")
        author = book.get("author", "Unknown")
        chunk_count = book.get("chunk_count", 0)
        added_date = book.get("added_date", "Unknown")
        safe_title = book.get("safe_title", "")

        # Format date
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(added_date)
            date_str = dt.strftime("%Y-%m-%d")
        except:
            date_str = added_date

        print(f"{i}. {title}")
        print(f"   Author: {author}")
        print(f"   Chunks: {chunk_count} | Added: {date_str}")
        print(f"   ID: {safe_title}")
        print()

    print(f"{'='*80}")
    print(f"Total: {len(books)} book(s)")
    print(f"{'='*80}\n")


def delete_book(book_identifier, index_dir, force=False):
    """
    Delete a book from the unified index.

    Args:
        book_identifier: Book title (partial match) or safe_title
        index_dir: Library directory path
        force: Skip confirmation prompt
    """
    index_dir = Path(index_dir).expanduser()
    metadata_path = index_dir / "books_metadata.json"

    if not metadata_path.exists():
        print("Error: No library found at this location.")
        return

    with open(metadata_path) as f:
        books_metadata = json.load(f)

    books = books_metadata.get("books", [])

    # Find matching books
    matches = []
    identifier_lower = book_identifier.lower()

    for book in books:
        title_match = identifier_lower in book.get("title", "").lower()
        safe_title_match = identifier_lower in book.get("safe_title", "").lower()
        exact_safe_title = identifier_lower == book.get("safe_title", "").lower()

        if title_match or safe_title_match or exact_safe_title:
            matches.append(book)

    if not matches:
        print(f"Error: No books found matching '{book_identifier}'")
        print("\nUse --list to see all indexed books.")
        return

    # Handle multiple matches
    if len(matches) > 1:
        print(f"\nMultiple books match '{book_identifier}':\n")
        for i, book in enumerate(matches, 1):
            print(f"{i}. {book['title']} by {book['author']}")
            print(f"   ID: {book['safe_title']}\n")

        print("Please be more specific, or use the exact safe_title ID.")
        return

    # Single match found
    book_to_delete = matches[0]
    title = book_to_delete.get("title", "Unknown")
    author = book_to_delete.get("author", "Unknown")
    safe_title = book_to_delete.get("safe_title", "")
    chunk_count = book_to_delete.get("chunk_count", 0)

    # Confirm deletion
    if not force:
        print(f"\n{'='*60}")
        print(f"Delete Book")
        print(f"{'='*60}")
        print(f"Title:  {title}")
        print(f"Author: {author}")
        print(f"Chunks: {chunk_count}")
        print(f"{'='*60}\n")

        response = input("Are you sure you want to delete this book? (y/N): ").strip().lower()
        if response != 'y':
            print("Cancelled.")
            return

    print(f"\nDeleting '{title}'...")

    # Remove book directory
    book_dir = index_dir / "books" / safe_title
    if book_dir.exists():
        import shutil
        shutil.rmtree(book_dir)
        print(f"  ✓ Removed book directory")
    else:
        print(f"  ⚠️  Book directory not found (may have been manually deleted)")

    # Remove from metadata
    books_metadata["books"] = [b for b in books_metadata["books"] if b["safe_title"] != safe_title]

    with open(metadata_path, 'w') as f:
        json.dump(books_metadata, f, indent=2)
    print(f"  ✓ Updated metadata")

    # Completion message
    print(f"\n{'='*60}")
    print(f"Book deleted successfully!")
    print(f"{'='*60}")
    print(f"\nRun './lib --sync' to update the web search data.")
    print()


def main():
    """Index an EPUB file into the unified library."""
    parser = argparse.ArgumentParser(
        description='Manage your book library - index, list, and delete books',
        epilog='Examples:\n'
               '  %(prog)s book.epub              # Index a book\n'
               '  %(prog)s --list                 # List all books\n'
               '  %(prog)s --delete "Book Title"  # Delete a book\n',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('epub_file', nargs='?', help='Path to EPUB file to index')
    parser.add_argument('--index-dir', default='./private',
                        help='Library directory (default: ./private)')
    parser.add_argument('--replace', action='store_true',
                        help='Automatically replace existing book without prompting')
    parser.add_argument('--list', action='store_true',
                        help='List all books in the library')
    parser.add_argument('--delete', metavar='BOOK',
                        help='Delete a book (by title or safe_title ID)')
    parser.add_argument('--force', action='store_true',
                        help='Skip confirmation prompts (use with --delete)')

    args = parser.parse_args()

    index_dir = Path(args.index_dir).expanduser()

    # Check Ollama availability (only for add operations, not --list or --delete)
    if not args.list and not args.delete:
        ollama_ok, ollama_msg = check_ollama_available()
        if not ollama_ok:
            print(f"\n❌ Error: {ollama_msg}")
            print("\nOllama is required for processing books (generates semantic tags).")
            print("\nSetup instructions:")
            print("  1. Install Ollama: https://ollama.ai")
            print("  2. Start Ollama: ollama serve")
            print("  3. Pull model: ollama pull qwen2.5:7b")
            print("\nOnce Ollama is running, try again.")
            sys.exit(1)
        print(f"✓ {ollama_msg}")

    # Handle --list command
    if args.list:
        list_books(index_dir)
        return

    # Handle --delete command
    if args.delete:
        delete_book(args.delete, index_dir, force=args.force)
        return

    # If no epub_file provided and no command, show error
    if not args.epub_file:
        parser.error("Please provide an EPUB file to index, or use --list or --delete")

    # Handle glob patterns and find file
    import glob
    input_path = os.path.expanduser(args.epub_file)

    if not os.path.exists(input_path):
        matches = glob.glob(input_path)
        if matches:
            epub_path = Path(matches[0])
        else:
            print(f"Error: File not found: {input_path}")
            sys.exit(1)
    else:
        epub_path = Path(input_path)

    if not epub_path.suffix.lower() == '.epub':
        print(f"Error: File must be an EPUB file")
        sys.exit(1)

    # Convert and chunk
    markdown_content, book_title, author = epub_to_clean_markdown(epub_path)
    chunks = chunk_markdown_hierarchically(markdown_content, book_title)

    # Save markdown and chunks
    safe_title = re.sub(r'[^\w\s-]', '', book_title)
    safe_title = re.sub(r'[-\s]+', '_', safe_title)

    chunk_dir = index_dir / "books" / safe_title
    output_md = chunk_dir / f"{safe_title}.md"
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(markdown_content, encoding='utf-8')

    print(f"\n✓ Markdown saved to: {output_md}")

    save_chunks(chunks, index_dir / "books", book_title)

    # Update metadata
    update_books_metadata(chunks, book_title, author, index_dir, chunk_dir, args.replace)

    print(f"\n✓ Book processing complete!")
    print(f"  Run './lib --sync' to generate embeddings and sync to web.")


if __name__ == "__main__":
    main()
