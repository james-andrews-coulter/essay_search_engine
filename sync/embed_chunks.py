#!/usr/bin/env python3
"""
Generate embeddings for chunks using BAAI/bge-large-en-v1.5
Supports incremental updates (only embed new/changed chunks)
"""

import json
from pathlib import Path
from sentence_transformers import SentenceTransformer
import sys
import argparse

# Paths
TARGET_DIR = Path(__file__).parent.parent
METADATA_FILE = TARGET_DIR / 'public' / 'data' / 'metadata.json'
EMBEDDINGS_FILE = TARGET_DIR / 'public' / 'data' / 'embeddings.json'
SOURCE_DIR = TARGET_DIR / "private" / "books"

def load_existing_embeddings():
    """Load existing embeddings if they exist"""
    if EMBEDDINGS_FILE.exists():
        print("Loading existing embeddings...")
        with open(EMBEDDINGS_FILE) as f:
            return json.load(f)
    return None

def generate_embeddings(incremental=True):
    """Generate embeddings for chunks"""

    # Check if metadata exists
    if not METADATA_FILE.exists():
        print(f"ERROR: {METADATA_FILE} does not exist. Run sync.py first.")
        sys.exit(1)

    # Load metadata
    with open(METADATA_FILE) as f:
        metadata = json.load(f)

    total_chunks = len(metadata['chunks'])
    print(f"\nFound {total_chunks} total chunk(s) in metadata")

    # Load existing embeddings if incremental
    existing_embeddings = None
    existing_chunk_ids = set()

    if incremental:
        existing_embeddings = load_existing_embeddings()
        if existing_embeddings:
            existing_chunk_ids = set(range(len(existing_embeddings['embeddings'])))
            print(f"Found {len(existing_chunk_ids)} existing embedding(s)")

    # Determine which chunks need embedding
    chunks_to_embed = []
    chunk_indices = []

    for idx, chunk_meta in enumerate(metadata['chunks']):
        chunk_id = chunk_meta['chunk_id']

        # Check if we need to embed this chunk
        if not incremental or chunk_id not in existing_chunk_ids:
            chunks_to_embed.append(chunk_meta)
            chunk_indices.append(idx)

    if not chunks_to_embed:
        print("\n✓ All chunks already have embeddings!")
        print("   Use --force to regenerate all embeddings")
        return

    print(f"\n🆕 Need to embed {len(chunks_to_embed)} new/updated chunk(s)")

    # Load model
    print("\n📥 Loading embedding model: BAAI/bge-large-en-v1.5...")
    print("   (This may take a few minutes on first run)")
    model = SentenceTransformer('BAAI/bge-large-en-v1.5')
    print("   ✓ Model loaded!")

    # Collect chunk content
    texts = []
    print(f"\n📖 Loading content for {len(chunks_to_embed)} chunk(s)...")

    for chunk_meta in chunks_to_embed:
        chunk_id = chunk_meta['chunk_id']
        book_title = chunk_meta['book_title']

        # Find book safe_title
        book = next((b for b in metadata['books'] if b['title'] == book_title), None)
        if not book:
            print(f"⚠️  WARNING: Book '{book_title}' not found in metadata, skipping chunk {chunk_id}")
            texts.append("")
            continue

        safe_title = book['safe_title']

        # Load chunks.json to get content
        chunks_file = SOURCE_DIR / safe_title / 'chunks.json'
        if not chunks_file.exists():
            print(f"⚠️  WARNING: {chunks_file} not found, skipping chunk {chunk_id}")
            texts.append("")
            continue

        with open(chunks_file) as f:
            all_chunks = json.load(f)

        # Find matching chunk
        chunk = next((c for c in all_chunks if c['chunk_id'] == chunk_id), None)
        if not chunk:
            print(f"⚠️  WARNING: Chunk {chunk_id} not found in {chunks_file}")
            texts.append("")
            continue

        # Construct searchable text with hierarchy: Book Title > Chapter Title > Content
        # This ensures book/chapter titles have semantic weight in embeddings
        searchable_text = f"{book_title}\n{chunk_meta['chapter_title']}\n\n{chunk['content']}"
        texts.append(searchable_text)

    print(f"\n🧠 Generating embeddings for {len(texts)} chunk(s)...")
    print("   (This will take 1-2 minutes)")

    # Generate embeddings (batched for efficiency)
    new_embeddings = model.encode(
        texts,
        batch_size=32,
        show_progress_bar=True,
        normalize_embeddings=True,  # Important for cosine similarity
        convert_to_numpy=True
    )

    # Convert to list of lists (JSON-serializable)
    new_embeddings_list = new_embeddings.tolist()

    # Merge with existing embeddings if incremental
    if existing_embeddings and incremental:
        print(f"\n🔄 Merging with existing embeddings...")

        # Create full embeddings array (preserve order)
        final_embeddings = existing_embeddings['embeddings'].copy()

        # Update/add new embeddings
        for i, chunk_idx in enumerate(chunk_indices):
            chunk_id = metadata['chunks'][chunk_idx]['chunk_id']
            if chunk_id < len(final_embeddings):
                # Update existing
                final_embeddings[chunk_id] = new_embeddings_list[i]
            else:
                # Append new
                final_embeddings.append(new_embeddings_list[i])

        embeddings_list = final_embeddings
        print(f"   ✓ Merged: {len(embeddings_list)} total embeddings")
    else:
        embeddings_list = new_embeddings_list
        print(f"   ✓ Created: {len(embeddings_list)} embeddings")

    # Save
    print("\n💾 Saving embeddings...")
    output = {
        'model': 'Xenova/bge-large-en-v1.5',
        'dimensions': 1024,
        'embeddings': embeddings_list
    }

    EMBEDDINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(EMBEDDINGS_FILE, 'w') as f:
        json.dump(output, f)

    file_size_mb = EMBEDDINGS_FILE.stat().st_size / 1024 / 1024

    print(f"\n✓ Saved embeddings.json")
    print(f"  • Model: BAAI/bge-large-en-v1.5")
    print(f"  • Dimensions: 1024")
    print(f"  • Total chunks: {len(embeddings_list)}")
    print(f"  • New chunks: {len(chunks_to_embed)}")
    print(f"  • File size: {file_size_mb:.2f} MB")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate embeddings for chunks')
    parser.add_argument('--incremental', action='store_true',
                       help='Only generate embeddings for new chunks (default)')
    parser.add_argument('--force', action='store_true',
                       help='Force regenerate all embeddings')
    args = parser.parse_args()

    try:
        # Incremental is default, force overrides it
        incremental = not args.force
        generate_embeddings(incremental=incremental)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
