#!/usr/bin/env python3
"""
Sync script: Converts book data to GitHub Pages format
Supports incremental sync (only processes new/updated books)
"""

import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime
import yaml
import markdown
import hashlib
import time

# Configuration
TARGET_DIR = Path(__file__).parent.parent  # essay_search_engine/
SOURCE_DIR = TARGET_DIR / "private"  # ./private/
BOOKS_DIR = SOURCE_DIR / "books"
METADATA_FILE = SOURCE_DIR / "books_metadata.json"
OUTPUT_METADATA_FILE = TARGET_DIR / 'public' / 'data' / 'metadata.json'
SYNC_STATE_FILE = SOURCE_DIR / '.sync_state.json'

def load_sync_state():
    """Load the sync state (tracks last sync time per book)"""
    if SYNC_STATE_FILE.exists():
        with open(SYNC_STATE_FILE) as f:
            return json.load(f)
    return {"last_full_sync": None, "books": {}}

def save_sync_state(state):
    """Save the sync state"""
    SYNC_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SYNC_STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

def load_source_metadata():
    """Load books_metadata.json from source"""
    if not METADATA_FILE.exists():
        print(f"ERROR: {METADATA_FILE} not found")
        print("Please add books first using: ./lib <book.epub>")
        sys.exit(1)

    with open(METADATA_FILE) as f:
        return json.load(f)

def load_existing_output_metadata():
    """Load existing metadata.json if it exists"""
    if OUTPUT_METADATA_FILE.exists():
        with open(OUTPUT_METADATA_FILE) as f:
            return json.load(f)
    return None

def get_books_to_sync(books_metadata, sync_state, force=False):
    """Determine which books need syncing"""
    if force:
        print("\n🔄 Force sync: Processing all books")
        return books_metadata['books']

    books_to_sync = []
    unchanged_books = []

    for book in books_metadata['books']:
        safe_title = book['safe_title']
        added_date = book.get('added_date', '')

        # Check if book was synced before
        last_synced = sync_state['books'].get(safe_title, {}).get('last_synced')

        if not last_synced or added_date > last_synced:
            books_to_sync.append(book)
        else:
            unchanged_books.append(book)

    if books_to_sync:
        print(f"\n📚 Found {len(books_to_sync)} book(s) to sync:")
        for book in books_to_sync:
            print(f"   • {book['title']}")

    if unchanged_books:
        print(f"\n✓ {len(unchanged_books)} book(s) already synced (skipping)")

    return books_to_sync

def collect_chunks(books, all_books=False):
    """Collect chunk data from specified books"""
    all_chunks = []

    book_list = books if not all_books else books

    for book in book_list:
        safe_title = book['safe_title']
        chunks_json = BOOKS_DIR / safe_title / 'chunks.json'

        if not chunks_json.exists():
            print(f"  ⚠️  WARNING: {chunks_json} not found, skipping {book['title']}")
            continue

        with open(chunks_json) as f:
            chunks = json.load(f)

        for chunk in chunks:
            # Use global doc_id (fall back to chunk_id for backwards compatibility)
            doc_id = chunk.get('doc_id', chunk['chunk_id'])

            # Add book context
            chunk_data = {
                'chunk_id': doc_id,  # Use global doc_id as chunk_id
                'book_title': book['title'],
                'author': book['author'],
                'safe_title': book['safe_title'],
                'chapter_title': chunk.get('chapter_title', 'Untitled'),
                'tags': chunk.get('tags', ''),
                'content': chunk['content'],
                'word_count': chunk['metadata']['word_count'],
                'char_count': chunk['metadata']['char_count'],
                'file': f"chunk_{doc_id:03d}.html"  # Use global doc_id for filename
            }
            all_chunks.append(chunk_data)

    return all_chunks

def validate_chunks(chunks):
    """Validate that all chunk IDs are unique"""
    chunk_ids = [chunk['chunk_id'] for chunk in chunks]
    unique_ids = set(chunk_ids)

    if len(chunk_ids) != len(unique_ids):
        # Find duplicates
        from collections import Counter
        id_counts = Counter(chunk_ids)
        duplicates = {id: count for id, count in id_counts.items() if count > 1}

        print(f"\n⚠️  ERROR: Found {len(chunk_ids) - len(unique_ids)} duplicate chunk IDs!")
        print(f"  Total chunks: {len(chunk_ids)}")
        print(f"  Unique IDs: {len(unique_ids)}")
        print(f"\n  Duplicate IDs (showing first 10):")
        for chunk_id, count in sorted(duplicates.items())[:10]:
            print(f"    - chunk_id {chunk_id}: appears {count} times")

        # Show which books have these duplicates
        print(f"\n  Books with duplicate chunk_id {list(duplicates.keys())[0]}:")
        for chunk in chunks:
            if chunk['chunk_id'] == list(duplicates.keys())[0]:
                print(f"    - {chunk['book_title']} (chunk {chunk.get('book_local_chunk_id', '?')})")

        raise ValueError("Duplicate chunk IDs detected. Please run './lib --sync --force' to regenerate all chunks.")

    print(f"✓ Validation passed: All {len(chunks)} chunk IDs are unique")

def merge_metadata(existing_metadata, books_metadata, new_chunks):
    """Merge new chunks with existing metadata"""
    if not existing_metadata:
        # First time sync
        return {
            'books': [
                {
                    'title': b['title'],
                    'author': b['author'],
                    'safe_title': b['safe_title'],
                    'chunk_count': b['chunk_count']
                }
                for b in books_metadata['books']
            ],
            'chunks': new_chunks,
            'total_chunks': len(new_chunks),
            'last_updated': datetime.utcnow().isoformat() + 'Z'
        }

    # Get safe_titles of books being updated
    new_book_titles = {chunk['safe_title'] for chunk in new_chunks}

    # Remove old chunks from books being updated
    existing_chunks = [
        c for c in existing_metadata.get('chunks', [])
        if c.get('safe_title') not in new_book_titles
    ]

    # Add new chunks
    merged_chunks = existing_chunks + new_chunks

    # Update books list
    existing_books_dict = {b['safe_title']: b for b in existing_metadata.get('books', [])}

    for book in books_metadata['books']:
        existing_books_dict[book['safe_title']] = {
            'title': book['title'],
            'author': book['author'],
            'safe_title': book['safe_title'],
            'chunk_count': book['chunk_count']
        }

    return {
        'books': list(existing_books_dict.values()),
        'chunks': merged_chunks,
        'total_chunks': len(merged_chunks),
        'last_updated': datetime.utcnow().isoformat() + 'Z'
    }

def generate_metadata_json(books_metadata, chunks, existing_metadata=None, force=False):
    """Generate or update public/data/metadata.json"""
    # On force sync, ignore existing metadata and start fresh
    if force:
        existing_metadata = None

    metadata = merge_metadata(existing_metadata, books_metadata, chunks)

    output_file = OUTPUT_METADATA_FILE
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, 'w') as f:
        json.dump(metadata, f, indent=2)

    file_size_kb = output_file.stat().st_size / 1024
    print(f"\n✓ Updated metadata.json ({len(chunks)} new/updated chunks, {file_size_kb:.1f} KB total)")

def generate_chunk_pages(chunks):
    """Generate individual chunk HTML pages for new/updated chunks"""
    output_dir = TARGET_DIR / 'public' / 'chunks'
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n📄 Generating {len(chunks)} chunk HTML page(s)...")

    for i, chunk in enumerate(chunks):
        if (i + 1) % 50 == 0:
            print(f"   Generated {i + 1}/{len(chunks)} pages...")

        # Render markdown to HTML
        content_html = markdown.markdown(
            chunk['content'],
            extensions=['extra', 'codehilite', 'fenced_code', 'tables']
        )

        # Note: We don't have prev/next context for incremental sync
        # These would need to be computed from full metadata

        # Generate tags HTML (plain text, no styling)
        tags_text = ''
        if chunk['tags']:
            tags = [tag.strip() for tag in chunk['tags'].split(',') if tag.strip()]
            tags_text = f"<p>Tags: {', '.join(tags)}</p>"

        # Generate HTML (zero styling for Safari Reader)
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{chunk['chapter_title']} - {chunk['book_title']}</title>
</head>
<body>
    <button onclick="if (document.referrer.includes('/essay_search_engine/') || document.referrer.includes('localhost')) {{ history.back(); }} else {{ window.location.href = '../../index.html'; }}">← Back</button>

    <h1>{chunk['book_title']}</h1>
    <p>by {chunk['author']}</p>
    <h2>{chunk['chapter_title']}</h2>

    {tags_text}

    <article>
        {content_html}
    </article>
</body>
</html>
"""

        # Write file
        output_file = output_dir / f"chunk_{chunk['chunk_id']:03d}.html"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html)

    print(f"   ✓ Generated {len(chunks)} HTML page(s)")

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

def generate_tags_json(tag_counts):
    """Generate public/data/tags.json"""
    output_file = TARGET_DIR / 'public' / 'data' / 'tags.json'
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, 'w') as f:
        json.dump(tag_counts, f, indent=2, sort_keys=True)

    file_size_kb = output_file.stat().st_size / 1024
    print(f"\n✓ Generated tags.json ({len(tag_counts)} unique tags, {file_size_kb:.1f} KB)")

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

def generate_version_file():
    """Generate version.json for update detection in Service Worker"""
    embeddings_path = TARGET_DIR / 'public' / 'data' / 'embeddings.json'
    version_path = TARGET_DIR / 'public' / 'data' / 'version.json'

    if not embeddings_path.exists():
        print("ERROR: embeddings.json not found, skipping version.json generation")
        return

    try:
        # Calculate checksum of embeddings.json
        with open(embeddings_path, 'rb') as f:
            file_content = f.read()
            checksum = hashlib.md5(file_content).hexdigest()

        # Create version data
        version_data = {
            'timestamp': int(time.time()),
            'checksum': checksum,
            'embeddings_size': len(file_content)
        }

        # Write version.json
        with open(version_path, 'w') as f:
            json.dump(version_data, f, indent=2)

        print(f"✓ Generated version.json (checksum: {checksum}, size: {len(file_content) / 1024 / 1024:.1f}MB)")
    except Exception as e:
        print(f"ERROR generating version.json: {e}")

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Sync books to web format')
    parser.add_argument('--force', action='store_true',
                       help='Force sync all books (ignore last sync state)')
    args = parser.parse_args()

    print("=" * 60)
    print("Essay Search Engine - Incremental Sync")
    print("=" * 60)

    # Load sync state
    sync_state = load_sync_state()

    # Load source data
    print("\n📖 Loading source data from ./private/...")
    books_metadata = load_source_metadata()
    print(f"   Found {len(books_metadata['books'])} book(s) in library")

    # Load existing output metadata
    existing_metadata = load_existing_output_metadata()

    # Determine which books need syncing
    books_to_sync = get_books_to_sync(books_metadata, sync_state, force=args.force)

    if not books_to_sync:
        print("\n✓ Everything is up to date! No books to sync.")
        print("\nTip: Use './lib --sync --force' to force re-sync all books")
        return

    # Collect chunks from books that need syncing
    print(f"\n📦 Collecting chunks from {len(books_to_sync)} book(s)...")
    new_chunks = collect_chunks(books_to_sync)
    print(f"   Collected {len(new_chunks)} chunk(s)")

    if len(new_chunks) == 0:
        print("\n⚠️  No chunks found. Please check your source data.")
        sys.exit(1)

    # Validate chunk IDs are unique
    print(f"\n🔍 Validating chunk IDs...")
    validate_chunks(new_chunks)

    # Generate outputs
    generate_metadata_json(books_metadata, new_chunks, existing_metadata, force=args.force)
    generate_chunk_pages(new_chunks)

    # Generate tag index (after generate_chunk_pages)
    print("\n🏷️  Generating tag index...")

    # Need to load ALL chunks for complete tag index
    all_chunks = collect_chunks(books_metadata['books'], all_books=True)
    tag_counts = extract_tags(all_chunks)
    print(f"   Found {len(tag_counts)} unique tags")

    generate_tags_json(tag_counts)
    generate_tags_html(tag_counts)

    # Generate embeddings (separate script)
    print("\n" + "=" * 60)
    print("🧠 Generating embeddings...")
    print("=" * 60)

    try:
        subprocess.run([
            sys.executable,
            str(TARGET_DIR / 'sync' / 'embed_chunks.py'),
            '--incremental' if not args.force else '--force'
        ], check=True)
    except subprocess.CalledProcessError as e:
        print(f"\n❌ ERROR: Embedding generation failed: {e}")
        sys.exit(1)

    # Generate version.json for offline updates
    print("\nGenerating version.json for Service Worker updates...")
    generate_version_file()

    # Update sync state
    now = datetime.utcnow().isoformat() + 'Z'
    for book in books_to_sync:
        sync_state['books'][book['safe_title']] = {
            'last_synced': now,
            'chunk_count': book['chunk_count']
        }
    sync_state['last_full_sync'] = now if args.force else sync_state.get('last_full_sync')
    save_sync_state(sync_state)

    print("\n" + "=" * 60)
    print("✓ Sync complete!")
    print("=" * 60)
    print(f"  • Synced: {len(books_to_sync)} book(s)")
    print(f"  • New/updated chunks: {len(new_chunks)}")
    print(f"  • Total in library: {len(books_metadata['books'])} book(s)")
    print(f"\n💡 Next steps:")
    print("  1. Test locally: npm run dev")
    print("  2. Build: npm run build")
    print("  3. Deploy: git add public/ && git commit && git push")

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
