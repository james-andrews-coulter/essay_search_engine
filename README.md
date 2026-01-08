# Essay Search Engine

A mobile-accessible semantic search engine for your personal essay collection, powered by AI.

## Features

- **Semantic Search**: Uses BGE-large-en-v1.5 (same model as the TUI) for intelligent, meaning-based search
- **Tag Boosting**: Enhanced relevance for keyword searches through AI-generated tags
- **Mobile-Friendly**: Responsive design accessible from any device
- **Offline-First**: Model and data cached in browser after initial load
- **GitHub Pages**: Static deployment, no server required

## Architecture

- **Frontend**: Vanilla JavaScript + Vite + Tailwind CSS
- **AI Model**: Xenova/bge-large-en-v1.5 (327MB quantized, 1024-dim embeddings)
- **Search**: Client-side with pre-computed embeddings (~15MB)
- **Data**: 672 chapters from 16 books

## Project Structure

```
essay_search_engine/
├── public/
│   ├── data/
│   │   ├── metadata.json          # Book/chunk metadata (219KB)
│   │   └── embeddings.json        # Pre-computed vectors (15MB)
│   └── chunks/
│       └── chunk_*.html           # 672 individual chapter pages
├── src/
│   ├── main.js                    # UI logic
│   ├── search.js                  # Search engine + Transformers.js
│   └── styles.css                 # Tailwind CSS
├── sync/
│   ├── sync.py                    # Main sync script
│   ├── embed_chunks.py            # Embedding generation
│   └── requirements.txt           # Python dependencies
└── index.html                     # Search page
```

## Setup

### Prerequisites

- Node.js 20+
- Python 3.8+
- book-library-tui installed and configured

### Installation

1. Clone the repository:
```bash
git clone <repo-url>
cd essay_search_engine
```

2. Install dependencies:
```bash
npm install
```

3. Install Python dependencies for sync:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r sync/requirements.txt
```

## Usage

### Syncing Data (After Adding New Books)

When you process new EPUBs with book-library-tui:

```bash
# Activate Python environment
source venv/bin/activate

# Run sync script (generates all data files)
python3 sync/sync.py

# This will:
# 1. Read from ~/Desktop/unified_library/
# 2. Generate metadata.json
# 3. Generate embeddings.json (takes ~2-3 minutes)
# 4. Generate 672+ chunk HTML pages
```

### Development

```bash
npm run dev
```

Visit http://localhost:5173 to test locally.

### Building for Production

```bash
npm run build
```

Output in `dist/` directory.

### Deploying to GitHub Pages

1. Commit changes:
```bash
git add .
git commit -m "Update with new books"
```

2. Push to GitHub:
```bash
git push origin main
```

3. GitHub Actions will automatically build and deploy to Pages (~2-3 minutes)

### Enabling GitHub Pages

1. Go to repository Settings → Pages
2. Source: "GitHub Actions"
3. Save

## Performance

**Initial Load:**
- First visit: ~331MB download (327MB model + 15MB data)
- Cached visits: ~15MB (only data updates)
- Time to ready: ~10-15s on WiFi

**Search:**
- First query: ~5-10s (model initialization)
- Subsequent queries: ~1s
- Works offline after initial load

**Mobile:**
- 4G: ~20-30s initial load
- 3G: ~60-90s initial load
- WiFi: ~10-15s initial load

## How It Works

1. **Preprocessing** (Local, via sync script):
   - Read chunks from book-library-tui
   - Generate 1024-dim embeddings using BAAI/bge-large-en-v1.5
   - Save as JSON files

2. **Search** (Browser):
   - Load BGE-large-en-v1.5 model (Xenova quantized version)
   - Embed user query (1024-dim)
   - Compute cosine similarity with all chunk embeddings
   - Apply tag boosting (+20% for exact match, +10% for partial)
   - Sort and return top 20 results

3. **Display**:
   - Show book title, chapter, score, and tags
   - Click to view full chunk content
   - Navigate between chunks

## Customization

### Changing the Number of Results

Edit `src/main.js`:
```javascript
const results = await searchEngine.search(query, 20); // Change 20 to desired number
```

### Changing the Score Threshold

Edit `src/search.js`:
```javascript
results = results.filter(r => r.score >= 0.3); // Change 0.3 to desired threshold
```

### Customizing Tag Boosting

Edit `src/search.js`:
```javascript
// Exact tag match: +20% score
if (tags.some(tag => tag === queryLower)) {
  result.score += 0.20; // Adjust this value
}
```

## Troubleshooting

### Sync Script Fails

- Ensure book-library-tui is properly set up
- Check `~/Desktop/unified_library/books_metadata.json` exists
- Verify Python dependencies are installed

### Model Download Fails

- Check internet connection
- Try manually downloading from: https://huggingface.co/Xenova/bge-large-en-v1.5
- Clear browser cache and retry

### Search Returns No Results

- Lower the score threshold in `src/search.js`
- Try more general keywords
- Check browser console for errors

## License

Private project for personal use.

## Credits

- **Embedding Model**: [BAAI/bge-large-en-v1.5](https://huggingface.co/BAAI/bge-large-en-v1.5)
- **Browser ML**: [Transformers.js](https://github.com/xenova/transformers.js)
- **UI**: Tailwind CSS
- **Build**: Vite
