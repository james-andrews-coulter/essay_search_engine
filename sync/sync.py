#!/usr/bin/env python3
"""
Sync script: Converts book-library-tui data to GitHub Pages format
"""

import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime
import yaml
import markdown

# Configuration
TARGET_DIR = Path(__file__).parent.parent  # essay_search_engine/
SOURCE_DIR = TARGET_DIR / "private"  # ./private/
BOOKS_DIR = SOURCE_DIR / "books"
METADATA_FILE = SOURCE_DIR / "books_metadata.json"

def load_source_metadata():
    """Load books_metadata.json from source"""
    if not METADATA_FILE.exists():
        print(f"ERROR: {METADATA_FILE} not found")
        print("Please add books first using: ./lib <book.epub>")
        sys.exit(1)

    with open(METADATA_FILE) as f:
        return json.load(f)

def collect_chunks(books_metadata):
    """Collect all chunk data from source"""
    all_chunks = []

    print(f"\nCollecting chunks from {len(books_metadata['books'])} books...")

    for book in books_metadata['books']:
        safe_title = book['safe_title']
        chunks_json = BOOKS_DIR / safe_title / 'chunks.json'

        if not chunks_json.exists():
            print(f"  WARNING: {chunks_json} not found, skipping {book['title']}")
            continue

        with open(chunks_json) as f:
            chunks = json.load(f)

        print(f"  {book['title']}: {len(chunks)} chunks")

        for chunk in chunks:
            # Add book context
            chunk_data = {
                'chunk_id': chunk['chunk_id'],
                'book_title': book['title'],
                'author': book['author'],
                'safe_title': book['safe_title'],
                'chapter_title': chunk.get('chapter_title', 'Untitled'),
                'tags': chunk.get('tags', ''),
                'content': chunk['content'],
                'word_count': chunk['metadata']['word_count'],
                'char_count': chunk['metadata']['char_count'],
                'file': f"chunk_{chunk['chunk_id']:03d}.html"
            }
            all_chunks.append(chunk_data)

    return all_chunks

def generate_metadata_json(books_metadata, chunks):
    """Generate public/data/metadata.json"""
    metadata = {
        'books': [
            {
                'title': b['title'],
                'author': b['author'],
                'safe_title': b['safe_title'],
                'chunk_count': b['chunk_count']
            }
            for b in books_metadata['books']
        ],
        'chunks': [
            {
                'chunk_id': c['chunk_id'],
                'book_title': c['book_title'],
                'author': c['author'],
                'chapter_title': c['chapter_title'],
                'tags': c['tags'],
                'word_count': c['word_count'],
                'char_count': c['char_count'],
                'file': c['file']
            }
            for c in chunks
        ],
        'total_chunks': len(chunks),
        'last_updated': datetime.utcnow().isoformat() + 'Z'
    }

    output_file = TARGET_DIR / 'public' / 'data' / 'metadata.json'
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, 'w') as f:
        json.dump(metadata, f, indent=2)

    file_size_kb = output_file.stat().st_size / 1024
    print(f"\n✓ Generated metadata.json ({len(chunks)} chunks, {file_size_kb:.1f} KB)")

def generate_chunk_pages(chunks):
    """Generate individual chunk HTML pages"""
    output_dir = TARGET_DIR / 'public' / 'chunks'
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nGenerating {len(chunks)} chunk HTML pages...")

    for i, chunk in enumerate(chunks):
        if (i + 1) % 100 == 0:
            print(f"  Generated {i + 1}/{len(chunks)} pages...")

        # Render markdown to HTML
        content_html = markdown.markdown(
            chunk['content'],
            extensions=['extra', 'codehilite', 'fenced_code', 'tables']
        )

        # Find previous/next chunks (same book only)
        prev_chunk_id = None
        next_chunk_id = None

        if i > 0 and chunks[i-1]['book_title'] == chunk['book_title']:
            prev_chunk_id = chunks[i-1]['chunk_id']

        if i < len(chunks)-1 and chunks[i+1]['book_title'] == chunk['book_title']:
            next_chunk_id = chunks[i+1]['chunk_id']

        # Generate tags HTML
        tags_html = ''
        if chunk['tags']:
            tags = [tag.strip() for tag in chunk['tags'].split(',') if tag.strip()]
            tag_spans = ''.join([f'<span class="tag">{tag}</span>' for tag in tags])
            tags_html = f'<div class="tags">{tag_spans}</div>'

        # Generate HTML
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{chunk['chapter_title']} - {chunk['book_title']}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif; line-height: 1.6; color: #333; background: #f5f5f5; }}
        .container {{ max-width: 800px; margin: 0 auto; padding: 20px; background: white; min-height: 100vh; }}
        .header {{ border-bottom: 2px solid #e0e0e0; padding-bottom: 20px; margin-bottom: 30px; }}
        .back-link {{ color: #0066cc; text-decoration: none; font-size: 14px; display: inline-block; margin-bottom: 15px; }}
        .back-link:hover {{ text-decoration: underline; }}
        .book-info {{ margin-bottom: 10px; }}
        .book-title {{ font-size: 24px; font-weight: bold; color: #000; }}
        .author {{ font-size: 16px; color: #666; margin-top: 5px; }}
        .chapter-title {{ font-size: 20px; font-weight: 600; color: #000; margin-top: 15px; }}
        .meta-info {{ display: flex; gap: 20px; font-size: 14px; color: #666; margin-top: 10px; flex-wrap: wrap; }}
        .tags {{ margin-top: 10px; }}
        .tag {{ display: inline-block; background: #e8f4f8; color: #0066cc; padding: 4px 12px; border-radius: 12px; font-size: 13px; margin-right: 8px; margin-bottom: 8px; }}
        .content {{ margin: 30px 0; font-size: 16px; line-height: 1.8; }}
        .content h1, .content h2, .content h3 {{ margin-top: 30px; margin-bottom: 15px; color: #000; }}
        .content h1 {{ font-size: 28px; }}
        .content h2 {{ font-size: 24px; }}
        .content h3 {{ font-size: 20px; }}
        .content p {{ margin-bottom: 15px; }}
        .content blockquote {{ border-left: 4px solid #0066cc; padding-left: 20px; margin: 20px 0; color: #555; font-style: italic; }}
        .content code {{ background: #f4f4f4; padding: 2px 6px; border-radius: 3px; font-family: 'Courier New', monospace; font-size: 14px; }}
        .content pre {{ background: #f4f4f4; padding: 15px; border-radius: 5px; overflow-x: auto; margin: 20px 0; }}
        .content pre code {{ background: none; padding: 0; }}
        .navigation {{ border-top: 2px solid #e0e0e0; padding-top: 20px; margin-top: 40px; display: flex; justify-content: space-between; gap: 20px; }}
        .nav-button {{ padding: 10px 20px; background: #0066cc; color: white; text-decoration: none; border-radius: 5px; font-size: 14px; display: inline-block; }}
        .nav-button:hover {{ background: #0052a3; }}
        .nav-button:disabled, .nav-button.disabled {{ background: #ccc; cursor: not-allowed; }}
        @media (max-width: 640px) {{
            .container {{ padding: 15px; }}
            .book-title {{ font-size: 20px; }}
            .chapter-title {{ font-size: 18px; }}
            .content {{ font-size: 15px; }}
            .meta-info {{ flex-direction: column; gap: 5px; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <a href="../../index.html" class="back-link">← Back to Search</a>
            <div class="book-info">
                <div class="book-title">{chunk['book_title']}</div>
                <div class="author">by {chunk['author']}</div>
            </div>
            <div class="chapter-title">{chunk['chapter_title']}</div>
            <div class="meta-info">
                <span>Words: {chunk['word_count']:,}</span>
                <span>Characters: {chunk['char_count']:,}</span>
                <span>Chunk ID: {chunk['chunk_id']}</span>
            </div>
            {tags_html}
        </div>

        <div class="content">
            {content_html}
        </div>

        <div class="navigation">
            {f'<a href="chunk_{prev_chunk_id:03d}.html" class="nav-button">← Previous Chunk</a>' if prev_chunk_id is not None else '<span class="nav-button disabled">← Previous Chunk</span>'}
            {f'<a href="chunk_{next_chunk_id:03d}.html" class="nav-button">Next Chunk →</a>' if next_chunk_id is not None else '<span class="nav-button disabled">Next Chunk →</span>'}
        </div>
    </div>
</body>
</html>
"""

        # Write file
        output_file = output_dir / f"chunk_{chunk['chunk_id']:03d}.html"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html)

    print(f"  ✓ Generated all {len(chunks)} chunk HTML pages")

def main():
    print("=" * 60)
    print("Essay Search Engine - Sync Script")
    print("=" * 60)

    # Load source data
    print("\nLoading source data from ./private/...")
    books_metadata = load_source_metadata()
    print(f"Found {len(books_metadata['books'])} books")

    chunks = collect_chunks(books_metadata)
    print(f"Total chunks collected: {len(chunks)}")

    if len(chunks) == 0:
        print("\nERROR: No chunks found. Please check your source data.")
        sys.exit(1)

    # Generate outputs
    generate_metadata_json(books_metadata, chunks)
    generate_chunk_pages(chunks)

    # Generate embeddings (separate script)
    print("\n" + "=" * 60)
    print("Generating embeddings (this will take several minutes)...")
    print("=" * 60)

    try:
        subprocess.run([
            sys.executable,
            str(TARGET_DIR / 'sync' / 'embed_chunks.py')
        ], check=True)
    except subprocess.CalledProcessError as e:
        print(f"\nERROR: Embedding generation failed: {e}")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("✓ Sync complete!")
    print("=" * 60)
    print(f"  - {len(books_metadata['books'])} books")
    print(f"  - {len(chunks)} chunks")
    print(f"\nNext steps:")
    print("  1. Run 'npm install' to install frontend dependencies")
    print("  2. Run 'npm run dev' to test locally")
    print("  3. Run 'npm run build' to build for production")
    print("  4. Commit and push to deploy to GitHub Pages")

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
