#!/usr/bin/env python3
"""
Generate embeddings for chunks using BAAI/bge-large-en-v1.5
Supports incremental updates (only embed new/changed chunks)
"""

import argparse
import json
import sys
from pathlib import Path

from sentence_transformers import SentenceTransformer

# Paths
TARGET_DIR = Path(__file__).parent.parent
METADATA_FILE = TARGET_DIR / "public" / "data" / "metadata.json"
EMBEDDINGS_FILE = TARGET_DIR / "public" / "data" / "embeddings.json"
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

    total_chunks = len(metadata["chunks"])
    print(f"\nFound {total_chunks} total chunk(s) in metadata")

    # For incremental mode: check if we can reuse existing embeddings
    # Key insight: embeddings array MUST match metadata.chunks array order (index-by-index)
    existing_embeddings = None
    existing_embeddings_map = {}

    if incremental:
        existing_embeddings = load_existing_embeddings()
        if existing_embeddings:
            # Build a map of chunk_id -> embedding for reuse
            # Note: Old embeddings file may have misaligned data, so we check length
            if len(existing_embeddings["embeddings"]) == total_chunks:
                print(
                    f"Found {len(existing_embeddings['embeddings'])} existing embedding(s)"
                )
                for idx, chunk_meta in enumerate(metadata["chunks"]):
                    existing_embeddings_map[chunk_meta["chunk_id"]] = (
                        existing_embeddings["embeddings"][idx]
                    )
            else:
                print(
                    f"⚠️  Existing embeddings ({len(existing_embeddings['embeddings'])}) don't match metadata chunks ({total_chunks})"
                )
                print("   Will regenerate all embeddings to fix alignment issue")
                existing_embeddings_map = {}

    # For simplicity: always regenerate all embeddings to ensure correct order
    # This is safer than complex incremental logic and still reasonably fast
    if not incremental or not existing_embeddings_map:
        print(f"\n🔄 Generating embeddings for all {total_chunks} chunk(s)...")
        chunks_to_embed = metadata["chunks"]
        chunk_indices = list(range(len(chunks_to_embed)))
    else:
        # Incremental: only embed chunks not in existing_embeddings_map
        chunks_to_embed = []
        chunk_indices = []
        for idx, chunk_meta in enumerate(metadata["chunks"]):
            if chunk_meta["chunk_id"] not in existing_embeddings_map:
                chunks_to_embed.append(chunk_meta)
                chunk_indices.append(idx)

        if not chunks_to_embed:
            print("\n✓ All chunks already have embeddings!")
            print("   Use --force to regenerate all embeddings")
            return

        print(f"\n🆕 Need to embed {len(chunks_to_embed)} new chunk(s)")

    # Load model
    print("\n📥 Loading embedding model: BAAI/bge-large-en-v1.5...")
    print("   (This may take a few minutes on first run)")
    model = SentenceTransformer("BAAI/bge-large-en-v1.5")
    print("   ✓ Model loaded!")

    # Collect chunk content
    texts = []
    print(f"\n📖 Loading content for {len(chunks_to_embed)} chunk(s)...")

    for chunk_meta in chunks_to_embed:
        chunk_id = chunk_meta["chunk_id"]
        book_title = chunk_meta["book_title"]

        # Find book safe_title
        book = next((b for b in metadata["books"] if b["title"] == book_title), None)
        if not book:
            print(
                f"⚠️  WARNING: Book '{book_title}' not found in metadata, skipping chunk {chunk_id}"
            )
            texts.append("")
            continue

        safe_title = book["safe_title"]

        # Load chunks.json to get content
        chunks_file = SOURCE_DIR / safe_title / "chunks.json"
        if not chunks_file.exists():
            print(f"⚠️  WARNING: {chunks_file} not found, skipping chunk {chunk_id}")
            texts.append("")
            continue

        with open(chunks_file) as f:
            all_chunks = json.load(f)

        # Find matching chunk (use doc_id which is the global ID, fallback to chunk_id for old data)
        chunk = next(
            (c for c in all_chunks if c.get("doc_id", c["chunk_id"]) == chunk_id), None
        )
        if not chunk:
            print(f"⚠️  WARNING: Chunk {chunk_id} not found in {chunks_file}")
            texts.append("")
            continue

        # Use full content (model handles up to 512 tokens)
        texts.append(chunk["content"])

    print(f"\n🧠 Generating embeddings for {len(texts)} chunk(s)...")
    print("   (This will take 1-2 minutes)")

    # Generate embeddings (batched for efficiency)
    new_embeddings = model.encode(
        texts,
        batch_size=32,
        show_progress_bar=True,
        normalize_embeddings=True,  # Important for cosine similarity
        convert_to_numpy=True,
    )

    # Convert to list of lists (JSON-serializable)
    new_embeddings_list = new_embeddings.tolist()

    # Build final embeddings array in metadata.chunks order
    if existing_embeddings_map and incremental and len(chunks_to_embed) < total_chunks:
        print(
            f"\n🔄 Merging embeddings (reusing {len(existing_embeddings_map)} existing, adding {len(chunks_to_embed)} new)..."
        )

        # Build embeddings in exact metadata.chunks order
        embeddings_list = []
        new_embedding_idx = 0

        for idx, chunk_meta in enumerate(metadata["chunks"]):
            chunk_id = chunk_meta["chunk_id"]

            if idx in chunk_indices:
                # This chunk was newly embedded
                embeddings_list.append(new_embeddings_list[new_embedding_idx])
                new_embedding_idx += 1
            else:
                # Reuse existing embedding
                embeddings_list.append(existing_embeddings_map[chunk_id])

        print(
            f"   ✓ Merged: {len(embeddings_list)} total embeddings (matches metadata.chunks length)"
        )
    else:
        # Full regeneration: new_embeddings_list is already in metadata.chunks order
        embeddings_list = new_embeddings_list
        print(
            f"   ✓ Generated: {len(embeddings_list)} embeddings (matches metadata.chunks length)"
        )

    # Validation: ensure embeddings match metadata chunks count
    if len(embeddings_list) != total_chunks:
        raise ValueError(
            f"Embeddings count ({len(embeddings_list)}) doesn't match metadata chunks ({total_chunks})"
        )

    # Save
    print("\n💾 Saving embeddings...")
    output = {
        "model": "Xenova/bge-large-en-v1.5",
        "dimensions": 1024,
        "embeddings": embeddings_list,
    }

    EMBEDDINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(EMBEDDINGS_FILE, "w") as f:
        json.dump(output, f)

    file_size_mb = EMBEDDINGS_FILE.stat().st_size / 1024 / 1024

    print(f"\n✓ Saved embeddings.json")
    print(f"  • Model: BAAI/bge-large-en-v1.5")
    print(f"  • Dimensions: 1024")
    print(f"  • Total chunks: {len(embeddings_list)}")
    print(f"  • New chunks: {len(chunks_to_embed)}")
    print(f"  • File size: {file_size_mb:.2f} MB")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate embeddings for chunks")
    parser.add_argument(
        "--incremental",
        action="store_true",
        help="Only generate embeddings for new chunks (default)",
    )
    parser.add_argument(
        "--force", action="store_true", help="Force regenerate all embeddings"
    )
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
