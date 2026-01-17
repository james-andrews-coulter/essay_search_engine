import { pipeline, env } from "@xenova/transformers";

// Configure for offline support with self-hosted models
env.backends.onnx.wasm.wasmPaths = "/essay_search_engine/wasm/";
env.remoteHost = "/essay_search_engine/models/";
env.remotePathTemplate = "{model}/"; // Flat structure without /resolve/main/

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
      throw new Error("Already initializing");
    }

    this.isLoading = true;

    try {
      // Load metadata and embeddings
      if (onProgress) onProgress("Loading metadata...");
      const metadataResponse = await fetch(
        "/essay_search_engine/data/metadata.json",
      );
      this.metadata = await metadataResponse.json();

      if (onProgress) onProgress("Loading embeddings...");
      const embeddingsResponse = await fetch(
        "/essay_search_engine/data/embeddings.json",
      );
      this.embeddings = await embeddingsResponse.json();

      // Load embedding model (BGE-large-en-v1.5 - same as TUI)
      if (onProgress)
        onProgress("Loading AI model (327MB, may take a minute)...");
      this.embedder = await pipeline(
        "feature-extraction",
        "Xenova/bge-large-en-v1.5",
      );

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
