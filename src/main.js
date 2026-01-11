import './styles.css';
import { SearchEngine } from './search.js';

// Initialize search engine
const searchEngine = new SearchEngine();
let isInitialized = false;

// DOM elements
const searchInput = document.getElementById('search-input');
const searchButton = document.getElementById('search-button');
const statusDiv = document.getElementById('status');
const resultsDiv = document.getElementById('results');

// Pagination state
let allResults = [];
let currentPage = 1;
const resultsPerPage = 25;
let currentQuery = '';

/**
 * Initialize the search engine
 */
async function initialize() {
  if (isInitialized) return;

  statusDiv.textContent = 'Loading search engine...';

  try {
    await searchEngine.initialize((progress) => {
      statusDiv.textContent = progress;
    });

    isInitialized = true;
    searchInput.disabled = false;
    searchButton.disabled = false;
    searchInput.focus();

    const totalChunks = searchEngine.getTotalChunks();
    const books = searchEngine.getBooks();
    statusDiv.textContent = `Ready! Search across ${books.length} books (${totalChunks} chapters)`;
  } catch (error) {
    console.error('Initialization error:', error);
    statusDiv.textContent = `Error: ${error.message}`;
  }
}

/**
 * Perform search
 */
async function performSearch() {
  const query = searchInput.value.trim();

  if (!query) {
    resultsDiv.innerHTML = '';
    allResults = [];
    currentQuery = '';
    return;
  }

  if (!isInitialized) {
    statusDiv.textContent = 'Please initialize the search engine first';
    return;
  }

  // Show loading state
  searchButton.disabled = true;
  statusDiv.textContent = 'Searching...';

  try {
    // Get all results (no limit)
    const results = await searchEngine.search(query);

    // Hide loading state
    searchButton.disabled = false;

    if (results.length === 0) {
      statusDiv.textContent = `No results found for "${query}"`;
      resultsDiv.innerHTML = '<p>No results found. Try different keywords.</p>';
      allResults = [];
      currentQuery = '';
      return;
    }

    // Store results and reset pagination
    allResults = results;
    currentPage = 1;
    currentQuery = query;

    // Render paginated results
    renderResults();
  } catch (error) {
    console.error('Search error:', error);
    statusDiv.textContent = `Search error: ${error.message}`;
    searchButton.disabled = false;
  }
}

/**
 * Render paginated results
 */
function renderResults() {
  if (allResults.length === 0) {
    resultsDiv.innerHTML = '';
    return;
  }

  const totalPages = Math.ceil(allResults.length / resultsPerPage);
  const startIdx = (currentPage - 1) * resultsPerPage;
  const endIdx = Math.min(startIdx + resultsPerPage, allResults.length);
  const pageResults = allResults.slice(startIdx, endIdx);

  statusDiv.textContent = `Found ${allResults.length} results for "${currentQuery}" (showing ${startIdx + 1}-${endIdx})`;

  // Render results
  const resultsHtml = pageResults.map((result, idx) => {
    const score = (result.score * 100).toFixed(1);
    const tags = result.chunk.tags
      ? result.chunk.tags.split(',').map(t => t.trim()).filter(t => t.length > 0)
      : [];

    return `
      <a href="/essay_search_engine/chunks/${result.chunk.file}" class="result-card">
        <div class="result-header">
          <h3 class="result-title">
            ${escapeHtml(result.chunk.book_title)}
          </h3>
          <span class="result-score">
            ${score}%
          </span>
        </div>
        <p class="result-chapter">
          ${escapeHtml(result.chunk.chapter_title)}
        </p>
        <p class="result-meta">
          by ${escapeHtml(result.chunk.author)} •
          ${result.chunk.word_count.toLocaleString()} words
        </p>
        ${tags.length > 0 ? `
          <div class="result-tags">
            ${tags.map(tag => `
              <span class="tag">
                ${escapeHtml(tag)}
              </span>
            `).join('')}
          </div>
        ` : ''}
      </a>
    `;
  }).join('');

  // Render pagination controls
  const paginationHtml = totalPages > 1 ? `
    <nav class="pagination">
      <button id="prev-page" ${currentPage === 1 ? 'disabled' : ''}>
        Previous
      </button>

      <div class="page-numbers">
        ${generatePageNumbers(currentPage, totalPages)}
      </div>

      <button id="next-page" ${currentPage === totalPages ? 'disabled' : ''}>
        Next
      </button>
    </nav>
  ` : '';

  resultsDiv.innerHTML = resultsHtml + paginationHtml;

  // Add pagination event listeners
  if (totalPages > 1) {
    const prevBtn = document.getElementById('prev-page');
    const nextBtn = document.getElementById('next-page');

    prevBtn?.addEventListener('click', () => {
      if (currentPage > 1) {
        currentPage--;
        renderResults();
        window.scrollTo({ top: 0, behavior: 'smooth' });
      }
    });

    nextBtn?.addEventListener('click', () => {
      if (currentPage < totalPages) {
        currentPage++;
        renderResults();
        window.scrollTo({ top: 0, behavior: 'smooth' });
      }
    });

    // Add event listeners for page number buttons
    document.querySelectorAll('.page-number').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const page = parseInt(e.target.dataset.page);
        if (page !== currentPage) {
          currentPage = page;
          renderResults();
          window.scrollTo({ top: 0, behavior: 'smooth' });
        }
      });
    });
  }
}

/**
 * Generate page number buttons
 */
function generatePageNumbers(current, total) {
  const pages = [];
  const maxVisible = 7;

  if (total <= maxVisible) {
    // Show all pages
    for (let i = 1; i <= total; i++) {
      pages.push(i);
    }
  } else {
    // Show first, last, current, and nearby pages
    pages.push(1);

    let start = Math.max(2, current - 2);
    let end = Math.min(total - 1, current + 2);

    if (start > 2) pages.push('...');

    for (let i = start; i <= end; i++) {
      pages.push(i);
    }

    if (end < total - 1) pages.push('...');
    pages.push(total);
  }

  return pages.map(page => {
    if (page === '...') {
      return '<span class="ellipsis">...</span>';
    }

    const isActive = page === current;
    return `
      <button class="page-number ${isActive ? 'active' : ''}"
              data-page="${page}"
              ${isActive ? 'disabled' : ''}>
        ${page}
      </button>
    `;
  }).join('');
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// Event listeners - search on button click or Enter only
searchButton.addEventListener('click', performSearch);
searchInput.addEventListener('keypress', (e) => {
  if (e.key === 'Enter') {
    e.preventDefault();
    performSearch();
  }
});

// Auto-initialize on page load
window.addEventListener('DOMContentLoaded', initialize);
