import Fuse from 'fuse.js';

/**
 * Search Engine Class
 * Handles keyword/fuzzy search with Fuse.js and tag filtering
 */
export class SearchEngine {
  constructor() {
    this.fuse = null;
    this.metadata = null;
    this.isLoading = false;
    this.isReady = false;
  }

  /**
   * Initialize the search engine (load metadata only)
   * @param {Function} onProgress - Callback for progress updates
   */
  async initialize(onProgress = null) {
    if (this.isReady) return;
    if (this.isLoading) {
      throw new Error("Already initializing");
    }

    this.isLoading = true;

    try {
      // Load metadata only (no embeddings needed)
      if (onProgress) onProgress("Loading metadata...");
      const metadataResponse = await fetch(
        "/essay_search_engine/data/metadata.json",
      );
      this.metadata = await metadataResponse.json();

      // Initialize Fuse.js with weighted fields
      if (onProgress) onProgress("Initializing search...");
      this.fuse = new Fuse(this.metadata.chunks, {
        keys: [
          { name: 'book_title', weight: 0.4 },      // Highest priority
          { name: 'chapter_title', weight: 0.3 },   // Second priority
          { name: 'tags', weight: 0.2 },            // Third priority
          { name: 'content', weight: 0.1 }          // Lowest (avoids noise)
        ],
        threshold: 0.4,              // Match strictness (0.0 = exact, 1.0 = anything)
        ignoreLocation: true,        // Match anywhere in field
        minMatchCharLength: 2,       // Ignore single chars
        includeScore: true           // Include match score in results
      });

      if (onProgress) onProgress("Ready!");
      this.isReady = true;
    } catch (error) {
      this.isLoading = false;
      throw new Error(`Failed to initialize search engine: ${error.message}`);
    } finally {
      this.isLoading = false;
    }
  }

/**
   * Search for chunks matching the query with optional tag filtering
   * @param {string} query - Search query (keywords)
   * @param {Array<string>} tags - Array of exact tags to filter by (AND logic)
   * @param {number} limit - Maximum number of results (default: no limit)
   * @returns {Promise<Array>} - Array of search results with scores
   */
  async search(query, tags = [], limit = null) {
    if (!this.isReady) {
      throw new Error(
        "Search engine not initialized. Call initialize() first.",
      );
    }

    // Start with all chunks
    let results = this.metadata.chunks;

    // Step 1: Filter by tags (exact AND logic)
    if (tags.length > 0) {
      results = results.filter(chunk => {
        const chunkTags = chunk.tags?.split(',').map(t => t.trim()) || [];
        return tags.every(tag => chunkTags.includes(tag)); // ALL tags must match
      });
    }

    // Step 2: Fuzzy search within filtered results (if query exists)
    if (query && query.trim().length > 0) {
      const fuse = new Fuse(results, {
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
      });

      const fuseResults = fuse.search(query.trim());

      // Convert Fuse.js results format to our format
      results = fuseResults.map(result => ({
        chunk: result.item,
        score: 1 - result.score // Invert score (Fuse.js: 0=perfect, we want 1=perfect)
      }));
    } else {
      // No query, just return filtered results (from tag filtering)
      results = results.map(chunk => ({
        chunk: chunk,
        score: 1.0 // Perfect score for exact tag matches
      }));
    }

    return limit ? results.slice(0, limit) : results;
  }

  /**
   * Get total number of chunks
   */
  getTotalChunks() {
    return this.metadata ? this.metadata.total_chunks : 0;
  }

  /**
   * Get all books
   */
  getBooks() {
    return this.metadata ? this.metadata.books : [];
  }

  /**
   * Extract all unique tags from metadata
   * @returns {Array<string>} - Sorted array of unique tags
   */
  getAllTags() {
    if (!this.metadata) return [];

    const tagSet = new Set();
    this.metadata.chunks.forEach(chunk => {
      if (chunk.tags) {
        chunk.tags.split(',').forEach(tag => {
          const trimmed = tag.trim();
          if (trimmed) tagSet.add(trimmed);
        });
      }
    });

    return Array.from(tagSet).sort();
  }
}
