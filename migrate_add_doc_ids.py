#!/usr/bin/env python3
"""
Migration script to add doc_ids to existing chunks.json files.
This script reads the id_range from books_metadata.json and adds doc_id to each chunk.
"""

import json
from pathlib import Path

def migrate_chunks():
    """Add doc_ids to all existing chunks based on books_metadata.json"""
    private_dir = Path("./private")
    books_metadata_path = private_dir / "books_metadata.json"

    if not books_metadata_path.exists():
        print("❌ Error: books_metadata.json not found")
        return False

    # Load books metadata
    with open(books_metadata_path, 'r') as f:
        books_metadata = json.load(f)

    print(f"Found {len(books_metadata['books'])} books in metadata")
    print("")

    total_chunks_migrated = 0

    for book in books_metadata['books']:
        safe_title = book['safe_title']
        id_range = book.get('id_range', [None, None])

        if id_range[0] is None:
            print(f"⚠️  WARNING: {book['title']} has no id_range, skipping")
            continue

        chunks_json_path = private_dir / "books" / safe_title / "chunks.json"

        if not chunks_json_path.exists():
            print(f"⚠️  WARNING: {chunks_json_path} not found, skipping")
            continue

        # Load chunks
        with open(chunks_json_path, 'r', encoding='utf-8') as f:
            chunks = json.load(f)

        # Check if already migrated
        if chunks and 'doc_id' in chunks[0]:
            print(f"✓ {book['title']}: Already has doc_ids, skipping")
            continue

        # Add doc_ids
        start_doc_id = id_range[0]
        for i, chunk in enumerate(chunks):
            chunk['doc_id'] = start_doc_id + i

        # Save updated chunks
        with open(chunks_json_path, 'w', encoding='utf-8') as f:
            json.dump(chunks, f, indent=2, ensure_ascii=False)

        print(f"✓ {book['title']}: Added doc_ids {start_doc_id} to {start_doc_id + len(chunks) - 1} ({len(chunks)} chunks)")
        total_chunks_migrated += len(chunks)

    print("")
    print(f"✓ Migration complete! Added doc_ids to {total_chunks_migrated} chunks")
    return True

if __name__ == "__main__":
    print("=" * 60)
    print("Migration: Add doc_ids to existing chunks")
    print("=" * 60)
    print("")

    success = migrate_chunks()

    if success:
        print("")
        print("Next steps:")
        print("  1. Run './lib --sync --force' to regenerate HTML and embeddings")
        print("  2. Test the search functionality")
    else:
        print("")
        print("❌ Migration failed")
