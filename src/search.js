import { pipeline, env } from "@xenova/transformers";

console.log('[Search] === WASM CONFIGURATION DIAGNOSTIC ===');
console.log('[Search] Setting WASM paths to:', "/essay_search_engine/wasm/");

// Configure WASM files to load from our server instead of CDN (for offline support)
env.backends.onnx.wasm.wasmPaths = "/essay_search_engine/wasm/";

console.log('[Search] WASM paths configured:', env.backends.onnx.wasm.wasmPaths);
console.log('[Search] Available backends:', Object.keys(env.backends));
console.log('[Search] ===================================');

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
    console.log('[Search] === INITIALIZATION DIAGNOSTIC START ===');

    if (this.isReady) {
      console.log('[Search] Already initialized, skipping');
      return;
    }
    if (this.isLoading) {
      throw new Error("Already initializing");
    }

    this.isLoading = true;

    try {
      // Load metadata and embeddings
      if (onProgress) onProgress("Loading metadata...");
      console.log('[Search] Fetching metadata.json...');
      const metadataResponse = await fetch(
        "/essay_search_engine/data/metadata.json",
      );
      console.log('[Search] Metadata response status:', metadataResponse.status);
      this.metadata = await metadataResponse.json();
      console.log('[Search] ✓ Metadata loaded:', this.metadata.total_chunks, 'chunks');

      if (onProgress) onProgress("Loading embeddings...");
      console.log('[Search] Fetching embeddings.json...');
      const embeddingsResponse = await fetch(
        "/essay_search_engine/data/embeddings.json",
      );
      console.log('[Search] Embeddings response status:', embeddingsResponse.status);
      this.embeddings = await embeddingsResponse.json();
      console.log('[Search] ✓ Embeddings loaded:', this.embeddings.embeddings.length, 'vectors');

      // Load embedding model (BGE-large-en-v1.5 - same as TUI)
      if (onProgress)
        onProgress("Loading AI model (327MB, may take a minute)...");
      console.log('[Search] Loading pipeline (Xenova/bge-large-en-v1.5)...');
      console.log('[Search] Current WASM paths:', env.backends.onnx.wasm.wasmPaths);

      try {
        this.embedder = await pipeline(
          "feature-extraction",
          "Xenova/bge-large-en-v1.5",
        );
        console.log('[Search] ✓ Pipeline loaded successfully');
      } catch (pipelineError) {
        console.error('[Search] ❌ Pipeline load failed:', pipelineError);
        console.error('[Search] Error name:', pipelineError.name);
        console.error('[Search] Error message:', pipelineError.message);
        console.error('[Search] Error stack:', pipelineError.stack);
        throw pipelineError;
      }

      if (onProgress) onProgress("Ready!");
      this.isReady = true;
      console.log('[Search] ✓ Initialization complete');
      console.log('[Search] === INITIALIZATION DIAGNOSTIC END ===');
    } catch (error) {
      console.error('[Search] ❌ Initialization failed:', error);
      console.error('[Search] Error name:', error.name);
      console.error('[Search] Error message:', error.message);
      console.error('[Search] Error stack:', error.stack);
      console.log('[Search] === INITIALIZATION DIAGNOSTIC END ===');
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
      throw new Error("Vectors must have the same length");
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
   * @param {number} limit - Maximum number of results (default: no limit, returns all)
   * @returns {Promise<Array>} - Array of search results with scores
   */
  async search(query, limit = null) {
    if (!this.isReady) {
      throw new Error(
        "Search engine not initialized. Call initialize() first.",
      );
    }

    if (!query || query.trim().length === 0) {
      return [];
    }

    // Embed the query (1024-dim)
    const output = await this.embedder(query.trim(), {
      pooling: "mean",
      normalize: true,
    });
    const queryEmbedding = Array.from(output.data);

    // Compute cosine similarity with all chunks
    let results = this.embeddings.embeddings
      .map((embedding, idx) => ({
        chunk: this.metadata.chunks[idx],
        score: this.cosineSimilarity(queryEmbedding, embedding),
        baseSimilarity: this.cosineSimilarity(queryEmbedding, embedding),
      }))
      .filter((result) => result.chunk !== undefined);

    // Relevance boosting (ranked by importance)
    const queryLower = query.toLowerCase().trim();
    results = results.map((result) => {
      const chunk = result.chunk;

      // Book Title matching (highest priority: +50% for exact, +40% for partial)
      const bookTitle = chunk.book_title ? chunk.book_title.toLowerCase() : "";
      if (bookTitle === queryLower) {
        result.score += 0.5;
        result.hasBookTitleExact = true;
      } else if (
        bookTitle.includes(queryLower) ||
        queryLower
          .split(" ")
          .some((word) => word.length > 2 && bookTitle.includes(word))
      ) {
        result.score += 0.4;
        result.hasBookTitlePartial = true;
      }

      // Chapter Title matching (second priority: +40% for exact, +30% for partial)
      const chapterTitle = chunk.chapter_title
        ? chunk.chapter_title.toLowerCase()
        : "";
      if (chapterTitle === queryLower) {
        result.score += 0.4;
        result.hasChapterTitleExact = true;
      } else if (
        chapterTitle.includes(queryLower) ||
        queryLower
          .split(" ")
          .some((word) => word.length > 2 && chapterTitle.includes(word))
      ) {
        result.score += 0.3;
        result.hasChapterTitlePartial = true;
      }

      // Tag matching (third priority: +30% for exact, +15% for partial)
      if (chunk.tags) {
        const tags = chunk.tags
          .toLowerCase()
          .split(",")
          .map((t) => t.trim())
          .filter((t) => t.length > 0);

        // Exact tag match: +30% score
        if (tags.some((tag) => tag === queryLower)) {
          result.score += 0.3;
          result.hasExactMatch = true;
        }
        // Partial tag match: +15% score
        else if (
          tags.some(
            (tag) => tag.includes(queryLower) || queryLower.includes(tag),
          )
        ) {
          result.score += 0.15;
          result.hasPartialMatch = true;
        }
      }

      return result;
    });

    // Sort by score (descending)
    results.sort((a, b) => b.score - a.score);

    // Enhanced filtering: Prioritize title matches, then tag matches, then semantic similarity
    results = results.filter((r) => {
      // Keep if has book title match (even with very low semantic similarity)
      if (r.hasBookTitleExact || r.hasBookTitlePartial) {
        return r.baseSimilarity >= 0.15; // Very low threshold for book title matches
      }
      // Keep if has chapter title match
      if (r.hasChapterTitleExact || r.hasChapterTitlePartial) {
        return r.baseSimilarity >= 0.2; // Low threshold for chapter title matches
      }
      // Keep if has tag match and reasonable similarity
      if (r.hasExactMatch || r.hasPartialMatch) {
        return r.baseSimilarity >= 0.25; // Moderate threshold for tag matches
      }
      // Otherwise require very high semantic similarity
      return r.baseSimilarity >= 0.65; // High threshold required without any match
    });

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
}
