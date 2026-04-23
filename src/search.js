import Fuse from 'fuse.js';

const FUSE_OPTIONS = {
  keys: [
    { name: 'book_title', weight: 0.4 },
    { name: 'chapter_title', weight: 0.3 },
    { name: 'tags', weight: 0.2 },
    { name: 'content', weight: 0.1 }
  ],
  threshold: 0.4,
  ignoreLocation: true,
  minMatchCharLength: 2,
  includeScore: true
};

export class SearchEngine {
  constructor() {
    this.metadata = null;
    this.isLoading = false;
    this.isReady = false;
  }

  async initialize(onProgress = null) {
    if (this.isReady) return;
    if (this.isLoading) throw new Error('Already initializing');

    this.isLoading = true;
    try {
      onProgress?.('Loading metadata...');
      const res = await fetch('/essay_search_engine/data/metadata.json');
      this.metadata = await res.json();
      onProgress?.('Ready!');
      this.isReady = true;
    } catch (error) {
      throw new Error('Failed to initialize search engine', { cause: error });
    } finally {
      this.isLoading = false;
    }
  }

  async search(query, tags = [], limit = null) {
    if (!this.isReady) throw new Error('Search engine not initialized. Call initialize() first.');

    let chunks = this.metadata.chunks;

    if (tags.length > 0) {
      chunks = chunks.filter(chunk => {
        const chunkTags = chunk.tags?.split(',').map(t => t.trim()) || [];
        return tags.every(tag => chunkTags.includes(tag));
      });
    }

    const trimmed = query?.trim();
    let results;
    if (trimmed) {
      results = new Fuse(chunks, FUSE_OPTIONS).search(trimmed).map(r => ({
        chunk: r.item,
        score: 1 - r.score
      }));
    } else {
      results = chunks.map(chunk => ({ chunk, score: 1.0 }));
    }

    return limit ? results.slice(0, limit) : results;
  }

  getTotalChunks() {
    return this.metadata?.total_chunks ?? 0;
  }

  getBooks() {
    return this.metadata?.books ?? [];
  }

  getAllTags() {
    if (!this.metadata) return [];
    const tagSet = new Set();
    for (const chunk of this.metadata.chunks) {
      if (!chunk.tags) continue;
      for (const tag of chunk.tags.split(',')) {
        const trimmed = tag.trim();
        if (trimmed) tagSet.add(trimmed);
      }
    }
    return Array.from(tagSet).sort();
  }
}
