#!/usr/bin/env python3
"""
Generate embeddings for all chunks using BAAI/bge-large-en-v1.5
Same model as TUI for consistent search quality
"""

import json
from pathlib import Path
from sentence_transformers import SentenceTransformer
import sys

# Paths
TARGET_DIR = Path(__file__).parent.parent
METADATA_FILE = TARGET_DIR / 'public' / 'data' / 'metadata.json'
EMBEDDINGS_FILE = TARGET_DIR / 'public' / 'data' / 'embeddings.json'
SOURCE_DIR = Path.home() / "Desktop" / "unified_library" / "books"

def generate_embeddings():
    """Generate embeddings for all chunks"""

    # Check if metadata exists
    if not METADATA_FILE.exists():
        print(f"ERROR: {METADATA_FILE} does not exist. Run sync.py first.")
        sys.exit(1)

    # Load model (same as TUI: BAAI/bge-large-en-v1.5)
    print("Loading embedding model: BAAI/bge-large-en-v1.5...")
    print("This may take a few minutes on first run...")
    model = SentenceTransformer('BAAI/bge-large-en-v1.5')
    print("Model loaded successfully!")

    # Load metadata
    with open(METADATA_FILE) as f:
        metadata = json.load(f)

    print(f"\nFound {len(metadata['chunks'])} chunks to embed")

    # Collect chunk content
    texts = []
    print("Loading chunk content...")

    for idx, chunk_meta in enumerate(metadata['chunks']):
        if (idx + 1) % 100 == 0:
            print(f"  Loaded {idx + 1}/{len(metadata['chunks'])} chunks...")

        chunk_id = chunk_meta['chunk_id']
        book_title = chunk_meta['book_title']

        # Find book safe_title
        book = next((b for b in metadata['books'] if b['title'] == book_title), None)
        if not book:
            print(f"WARNING: Book '{book_title}' not found in metadata, skipping chunk {chunk_id}")
            texts.append("")
            continue

        safe_title = book['safe_title']

        # Load chunks.json to get content
        chunks_file = SOURCE_DIR / safe_title / 'chunks.json'
        if not chunks_file.exists():
            print(f"WARNING: {chunks_file} not found, skipping chunk {chunk_id}")
            texts.append("")
            continue

        with open(chunks_file) as f:
            all_chunks = json.load(f)

        # Find matching chunk
        chunk = next((c for c in all_chunks if c['chunk_id'] == chunk_id), None)
        if not chunk:
            print(f"WARNING: Chunk {chunk_id} not found in {chunks_file}")
            texts.append("")
            continue

        # Use full content (model handles up to 512 tokens)
        texts.append(chunk['content'])

    print(f"\nGenerating embeddings for {len(texts)} chunks...")
    print("This will take several minutes...")

    # Generate embeddings (batched for efficiency)
    embeddings = model.encode(
        texts,
        batch_size=32,
        show_progress_bar=True,
        normalize_embeddings=True,  # Important for cosine similarity
        convert_to_numpy=True
    )

    # Convert to list of lists (JSON-serializable)
    embeddings_list = embeddings.tolist()

    # Save
    print("\nSaving embeddings...")
    output = {
        'model': 'Xenova/bge-large-en-v1.5',
        'dimensions': 1024,
        'embeddings': embeddings_list
    }

    EMBEDDINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(EMBEDDINGS_FILE, 'w') as f:
        json.dump(output, f)

    file_size_mb = EMBEDDINGS_FILE.stat().st_size / 1024 / 1024

    print(f"\n✓ Generated embeddings.json")
    print(f"  - Model: BAAI/bge-large-en-v1.5 (same as TUI)")
    print(f"  - Dimensions: 1024")
    print(f"  - Chunks: {len(embeddings_list)}")
    print(f"  - File size: {file_size_mb:.2f} MB")

if __name__ == '__main__':
    try:
        generate_embeddings()
    except Exception as e:
        print(f"\nERROR: {e}")
        sys.exit(1)
