#!/usr/bin/env python3
"""
Unified build script for essay search engine.
Generates metadata.json, tags.json, tags.html, and embeddings.json.
"""

import json
import os
from pathlib import Path
from sentence_transformers import SentenceTransformer

# Paths
TARGET_DIR = Path(__file__).parent.parent
SOURCE_DIR = TARGET_DIR / "private" / "books"
METADATA_FILE = TARGET_DIR / "private" / "books_metadata.json"
OUTPUT_DIR = TARGET_DIR / "public" / "data"
TAGS_OUTPUT = TARGET_DIR / "public" / "data" / "tags.json"
TAGS_HTML = TARGET_DIR / "public" / "tags.html"

def load_chunks():
    """Load all chunks from source books."""
    print("=" * 60)
    print("Loading chunks from source...")

    if not METADATA_FILE.exists():
        print(f"❌ Error: {METADATA_FILE} not found")
        return []

    with open(METADATA_FILE, 'r') as f:
        metadata = json.load(f)
        books_metadata = metadata.get('books', [])

    all_chunks = []
    for book in books_metadata:
        book_dir = SOURCE_DIR / book['safe_title']
        chunks_file = book_dir / 'chunks.json'

        if not chunks_file.exists():
            print(f"⚠️  Warning: {chunks_file} not found")
            continue

        with open(chunks_file, 'r') as f:
            chunks = json.load(f)

        for chunk in chunks:
            # Add minimal metadata (remove word_count, char_count, doc_id, author)
            all_chunks.append({
                'chunk_id': chunk['chunk_id'],
                'book_title': book['title'],
                'chapter_title': chunk.get('chapter_title', ''),
                'tags': chunk.get('tags', ''),
                'content': chunk.get('content', '')
            })

    print(f"✓ Loaded {len(all_chunks)} chunks from {len(books_metadata)} books")
    return all_chunks

def generate_metadata(chunks):
    """Generate metadata.json."""
    print("\nGenerating metadata.json...")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    metadata = {
        'total_chunks': len(chunks),
        'chunks': chunks
    }

    output_file = OUTPUT_DIR / 'metadata.json'
    with open(output_file, 'w') as f:
        json.dump(metadata, f, indent=2)

    size_mb = output_file.stat().st_size / (1024 * 1024)
    print(f"✓ Generated metadata.json ({size_mb:.1f}MB)")

def generate_tags(chunks):
    """Generate tags.json and tags.html."""
    print("\nGenerating tags data...")

    # Collect all tags with counts
    tag_counts = {}
    for chunk in chunks:
        if chunk.get('tags'):
            tags = [t.strip() for t in chunk['tags'].split(',')]
            for tag in tags:
                if tag:
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1

    # Sort alphabetically
    sorted_tags = sorted(tag_counts.items())

    # Generate tags.json
    tags_data = {
        'total_tags': len(sorted_tags),
        'tags': [{'tag': tag, 'count': count} for tag, count in sorted_tags]
    }

    with open(TAGS_OUTPUT, 'w') as f:
        json.dump(tags_data, f, indent=2)

    print(f"✓ Generated tags.json ({len(sorted_tags)} unique tags)")

    # Generate tags.html
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Browse Tags</title>
    <style>
        body {{ max-width: 50rem; margin: 0 auto; padding: 1rem; font-family: system-ui; }}
        h1 {{ font-size: 1.5rem; }}
        .tag-list {{ display: flex; flex-wrap: wrap; gap: 0.5rem; }}
        .tag {{ display: inline-block; padding: 0.25rem 0.5rem; background: #f0f0f0; border-radius: 4px; text-decoration: none; color: #333; }}
        .tag:hover {{ background: #e0e0e0; }}
        .count {{ color: #666; font-size: 0.875rem; }}
    </style>
</head>
<body>
    <h1>Browse Tags</h1>
    <p><a href="/essay_search_engine/">← Back to Search</a></p>
    <div class="tag-list">
"""

    for tag, count in sorted_tags:
        html += f'        <a href="/essay_search_engine/?tag={tag}" class="tag">{tag} <span class="count">({count})</span></a>\n'

    html += """    </div>
</body>
</html>"""

    with open(TAGS_HTML, 'w') as f:
        f.write(html)

    print(f"✓ Generated tags.html")

def generate_embeddings(chunks):
    """Generate embeddings.json."""
    print("\nGenerating embeddings...")
    print("Loading BGE-large-en-v1.5 model...")

    model = SentenceTransformer('BAAI/bge-large-en-v1.5')

    # Extract content for embedding
    texts = [chunk['content'] for chunk in chunks]

    print(f"Embedding {len(texts)} chunks...")
    embeddings = model.encode(
        texts,
        batch_size=32,
        show_progress_bar=True,
        normalize_embeddings=True  # CRITICAL: must match browser
    )

    # Convert to list of lists (JSON serializable)
    embeddings_list = [emb.tolist() for emb in embeddings]

    output_data = {
        'model': 'BAAI/bge-large-en-v1.5',
        'dimensions': len(embeddings_list[0]),
        'total_chunks': len(embeddings_list),
        'embeddings': embeddings_list
    }

    output_file = OUTPUT_DIR / 'embeddings.json'
    with open(output_file, 'w') as f:
        json.dump(output_data, f)

    size_mb = output_file.stat().st_size / (1024 * 1024)
    print(f"✓ Generated embeddings.json ({size_mb:.1f}MB)")

def main():
    """Main build process."""
    print("\n" + "=" * 60)
    print("Essay Search Engine - Build Script")
    print("=" * 60 + "\n")

    # Load chunks
    chunks = load_chunks()
    if not chunks:
        print("\n❌ No chunks found. Run ./lib to process books first.")
        return 1

    # Generate outputs
    generate_metadata(chunks)
    generate_tags(chunks)
    generate_embeddings(chunks)

    print("\n" + "=" * 60)
    print("✓ Build complete!")
    print("=" * 60 + "\n")

    return 0

if __name__ == '__main__':
    exit(main())
