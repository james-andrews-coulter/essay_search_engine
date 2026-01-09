import { pipeline } from '@xenova/transformers';

/**
 * Search Engine Class
 * Handles semantic search with BGE-large-en-v1.5 model and tag boosting
 */
export class SearchEngine {
  constructor() {
    this.embedder = null;
    this.metadata = null;
    this.embeddings = null;
    this.isLoading = false;
    this.isReady = false;
  }

  /**
   * Initialize the search engine (load model and data)
   * @param {Function} onProgress - Callback for progress updates
   */
  async initialize(onProgress = null) {
    if (this.isReady) return;
    if (this.isLoading) {
      throw new Error('Already initializing');
    }

    this.isLoading = true;

    try {
      // Load metadata and embeddings
      if (onProgress) onProgress('Loading metadata...');
      const metadataResponse = await fetch('/essay_search_engine/data/metadata.json');
      this.metadata = await metadataResponse.json();

      if (onProgress) onProgress('Loading embeddings...');
      const embeddingsResponse = await fetch('/essay_search_engine/data/embeddings.json');
      this.embeddings = await embeddingsResponse.json();

      // Load embedding model (BGE-large-en-v1.5 - same as TUI)
      if (onProgress) onProgress('Loading AI model (327MB, may take a minute)...');
      this.embedder = await pipeline('feature-extraction', 'Xenova/bge-large-en-v1.5');

      if (onProgress) onProgress('Ready!');
      this.isReady = true;
    } catch (error) {
      this.isLoading = false;
      throw new Error(`Failed to initialize search engine: ${error.message}`);
    } finally {
      this.isLoading = false;
    }
  }

  /**
   * Compute cosine similarity between two vectors
   */
  cosineSimilarity(vecA, vecB) {
    if (vecA.length !== vecB.length) {
      throw new Error('Vectors must have the same length');
    }

    let dotProduct = 0;
    let normA = 0;
    let normB = 0;

    for (let i = 0; i < vecA.length; i++) {
      dotProduct += vecA[i] * vecB[i];
      normA += vecA[i] * vecA[i];
      normB += vecB[i] * vecB[i];
    }

    if (normA === 0 || normB === 0) {
      return 0;
    }

    return dotProduct / (Math.sqrt(normA) * Math.sqrt(normB));
  }

  /**
   * Search for chunks matching the query
   * @param {string} query - Search query
   * @param {number} limit - Maximum number of results (default: 20)
   * @returns {Promise<Array>} - Array of search results with scores
   */
  async search(query, limit = 20) {
    if (!this.isReady) {
      throw new Error('Search engine not initialized. Call initialize() first.');
    }

    if (!query || query.trim().length === 0) {
      return [];
    }

    // Embed the query (1024-dim)
    const output = await this.embedder(query.trim(), {
      pooling: 'mean',
      normalize: true
    });
    const queryEmbedding = Array.from(output.data);

    // Compute cosine similarity with all chunks
    let results = this.embeddings.embeddings.map((embedding, idx) => ({
      chunk: this.metadata.chunks[idx],
      score: this.cosineSimilarity(queryEmbedding, embedding),
      baseSimilarity: this.cosineSimilarity(queryEmbedding, embedding)
    }));

    // Multi-attribute boosting with hierarchy: Book Title > Chapter Title > Tags
    const queryLower = query.toLowerCase().trim();
    results = results.map(result => {
      const chunk = result.chunk;

      // Book Title boosting (highest priority)
      const bookTitle = chunk.book_title?.toLowerCase() || '';
      if (bookTitle.includes(queryLower) || queryLower.includes(bookTitle)) {
        result.score += 0.50; // +50% for book title match
        result.hasBookTitleMatch = true;
      }

      // Chapter Title boosting (high priority)
      const chapterTitle = chunk.chapter_title?.toLowerCase() || '';
      if (chapterTitle.includes(queryLower) || queryLower.includes(chapterTitle)) {
        result.score += 0.40; // +40% for chapter title match
        result.hasChapterTitleMatch = true;
      }

      // Tag boosting (medium priority)
      if (chunk.tags) {
        const tags = chunk.tags
          .toLowerCase()
          .split(',')
          .map(t => t.trim())
          .filter(t => t.length > 0);

        // Exact tag match: +30% score
        if (tags.some(tag => tag === queryLower)) {
          result.score += 0.30;
          result.hasExactTagMatch = true;
        }
        // Partial tag match: +15% score
        else if (tags.some(tag => tag.includes(queryLower) || queryLower.includes(tag))) {
          result.score += 0.15;
          result.hasPartialTagMatch = true;
        }
      }

      return result;
    });

    // Sort by score (descending)
    results.sort((a, b) => b.score - a.score);

    // Enhanced filtering: Require either attribute match OR very high semantic similarity
    // This prevents irrelevant results from appearing just because they have moderate similarity
    results = results.filter(r => {
      // Keep if has book/chapter title match (even with low similarity)
      if (r.hasBookTitleMatch || r.hasChapterTitleMatch) {
        return r.baseSimilarity >= 0.15; // Very low threshold OK with title match
      }
      // Keep if has any tag match and reasonable similarity
      if (r.hasExactTagMatch || r.hasPartialTagMatch) {
        return r.baseSimilarity >= 0.25; // Lower threshold OK with tag match
      }
      // Otherwise require very high semantic similarity
      return r.baseSimilarity >= 0.65; // High threshold required without any match
    });

    return results.slice(0, limit);
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
}
