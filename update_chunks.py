#!/usr/bin/env python3
"""
Bulk update script to fix the "Back to Search" button in all existing chunk HTML files.

This script updates:
1. The CSS styling for .back-link (to support button element)
2. The HTML element from <a> tag to <button> with history.back() fallback logic
"""

import re
from pathlib import Path

def update_chunk_file(file_path):
    """Update a single chunk HTML file with the new back button."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    original_content = content

    # Update 1: Fix CSS for .back-link to support button element
    old_css = r'\.back-link \{ color: #0066cc; text-decoration: none; font-size: 14px; display: inline-block; margin-bottom: 15px; \}'
    new_css = '.back-link { color: #0066cc; background: none; border: none; font-size: 14px; display: inline-block; margin-bottom: 15px; cursor: pointer; padding: 0; font-family: inherit; }'
    content = re.sub(old_css, new_css, content)

    # Update 2: Replace <a> tag with <button> and add history.back() logic
    old_html = r'<a href="../../index\.html" class="back-link">← Back to Search</a>'
    new_html = '<button onclick="if (document.referrer.includes(\'/essay_search_engine/\') || document.referrer.includes(\'localhost\')) { history.back(); } else { window.location.href = \'../../index.html\'; }" class="back-link">← Back to Search</button>'
    content = re.sub(old_html, new_html, content)

    # Only write if changes were made
    if content != original_content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    return False

def main():
    """Main function to process all chunk files."""
    chunks_dir = Path(__file__).parent / 'public' / 'chunks'

    if not chunks_dir.exists():
        print(f"❌ Error: Chunks directory not found at {chunks_dir}")
        return

    # Find all chunk HTML files
    chunk_files = sorted(chunks_dir.glob('chunk_*.html'))

    if not chunk_files:
        print(f"❌ No chunk files found in {chunks_dir}")
        return

    print(f"📄 Found {len(chunk_files)} chunk files to update...")

    updated_count = 0
    for i, file_path in enumerate(chunk_files):
        if update_chunk_file(file_path):
            updated_count += 1

        # Progress indicator every 50 files
        if (i + 1) % 50 == 0:
            print(f"   Processed {i + 1}/{len(chunk_files)} files...")

    print(f"\n✓ Successfully updated {updated_count} out of {len(chunk_files)} files")

    if updated_count < len(chunk_files):
        print(f"ℹ️  {len(chunk_files) - updated_count} files were already up to date")

if __name__ == '__main__':
    main()
