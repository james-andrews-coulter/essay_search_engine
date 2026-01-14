#!/usr/bin/env python3
"""
Fix duplicate doc_ids in source data by reassigning sequential IDs
This ensures each chunk has a unique global doc_id
"""

import json
from pathlib import Path

# Paths
TARGET_DIR = Path(__file__).parent.parent
SOURCE_DIR = TARGET_DIR / "private" / "books"
METADATA_FILE = TARGET_DIR / "private" / "books_metadata.json"


def fix_doc_ids():
    """Reassign doc_ids to all chunks sequentially"""

    print("=" * 60)
    print("Fixing duplicate doc_ids in source data")
    print("=" * 60)

    # Load books_metadata.json to get book order
    if not METADATA_FILE.exists():
        print(f"ERROR: {METADATA_FILE} not found")
        return False

    with open(METADATA_FILE) as f:
        metadata = json.load(f)

    print(f"\nFound {len(metadata['books'])} books")

    # Track next available doc_id
    next_doc_id = 0
    updated_books = []
    total_chunks = 0

    # Process each book in order
    for book in metadata["books"]:
        safe_title = book["safe_title"]
        chunks_file = SOURCE_DIR / safe_title / "chunks.json"

        if not chunks_file.exists():
            print(f"⚠️  WARNING: {chunks_file} not found, skipping")
            updated_books.append(book)
            continue

        # Load chunks
        with open(chunks_file) as f:
            chunks = json.load(f)

        if not chunks:
            print(f"⚠️  WARNING: {book['title']} has no chunks, skipping")
            updated_books.append(book)
            continue

        # Reassign doc_ids
        doc_id_start = next_doc_id

        for chunk in chunks:
            chunk["doc_id"] = next_doc_id
            next_doc_id += 1

        doc_id_end = next_doc_id - 1

        # Save updated chunks.json
        with open(chunks_file, "w") as f:
            json.dump(chunks, f, indent=2)

        # Update book metadata
        book["doc_id_start"] = doc_id_start
        book["doc_id_end"] = doc_id_end
        book["chunk_count"] = len(chunks)
        updated_books.append(book)

        total_chunks += len(chunks)
        print(
            f"✓ {book['title']}: {len(chunks)} chunks (doc_id {doc_id_start}-{doc_id_end})"
        )

    # Save updated books_metadata.json
    metadata["books"] = updated_books
    with open(METADATA_FILE, "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"\n" + "=" * 60)
    print(f"✓ Fixed doc_ids for {len(updated_books)} books")
    print(f"  Total chunks: {total_chunks}")
    print(f"  doc_id range: 0-{next_doc_id - 1}")
    print("=" * 60)

    return True


if __name__ == "__main__":
    try:
        success = fix_doc_ids()
        if success:
            print("\n💡 Next step: Run './lib --sync --force' to regenerate web data")
        else:
            exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
        exit(1)
