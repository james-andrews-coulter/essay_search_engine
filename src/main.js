import './styles.css';
import { SearchEngine } from './search.js';

// Initialize search engine
const searchEngine = new SearchEngine();
let isInitialized = false;

// DOM elements
const searchInput = document.getElementById('search-input');
const searchButton = document.getElementById('search-button');
const initButton = document.getElementById('init-button');
const statusDiv = document.getElementById('status');
const resultsDiv = document.getElementById('results');
const loadingDiv = document.getElementById('loading');

// Pagination state
let allResults = [];
let currentPage = 1;
const resultsPerPage = 25;
let currentQuery = '';

// Debounce timer
let debounceTimer = null;

/**
 * Update status message
 */
function updateStatus(message, type = 'info') {
  statusDiv.textContent = message;
  statusDiv.className = `text-sm ${type === 'error' ? 'text-red-600' : 'text-gray-600'}`;
}

/**
 * Initialize the search engine
 */
async function initialize() {
  if (isInitialized) return;

  initButton.disabled = true;
  initButton.textContent = 'Initializing...';
  loadingDiv.classList.remove('hidden');

  try {
    await searchEngine.initialize((progress) => {
      updateStatus(progress);
    });

    isInitialized = true;
    initButton.classList.add('hidden');
    searchInput.disabled = false;
    searchButton.disabled = false;
    searchInput.focus();

    const totalChunks = searchEngine.getTotalChunks();
    const books = searchEngine.getBooks();
    updateStatus(`Ready! Search across ${books.length} books (${totalChunks} chapters)`);
    loadingDiv.classList.add('hidden');
  } catch (error) {
    console.error('Initialization error:', error);
    updateStatus(`Error: ${error.message}`, 'error');
    initButton.disabled = false;
    initButton.textContent = 'Retry Initialization';
    loadingDiv.classList.add('hidden');
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
    updateStatus('Please initialize the search engine first', 'error');
    return;
  }

  // Show loading state
  loadingDiv.classList.remove('hidden');
  searchButton.disabled = true;
  updateStatus('Searching...');

  try {
    // Get all results (no limit)
    const results = await searchEngine.search(query);

    // Hide loading state
    loadingDiv.classList.add('hidden');
    searchButton.disabled = false;

    if (results.length === 0) {
      updateStatus(`No results found for "${query}"`);
      resultsDiv.innerHTML = '<p class="text-gray-500 text-center py-8">No results found. Try different keywords.</p>';
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
    updateStatus(`Search error: ${error.message}`, 'error');
    loadingDiv.classList.add('hidden');
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

  updateStatus(`Found ${allResults.length} results for "${currentQuery}" (showing ${startIdx + 1}-${endIdx})`);

  // Render results
  const resultsHtml = pageResults.map((result, idx) => {
    const score = (result.score * 100).toFixed(1);
    const tags = result.chunk.tags
      ? result.chunk.tags.split(',').map(t => t.trim()).filter(t => t.length > 0)
      : [];

    return `
      <a href="/essay_search_engine/chunks/${result.chunk.file}"
         class="block bg-white rounded-lg shadow-md hover:shadow-lg transition-shadow p-6 mb-4">
        <div class="flex justify-between items-start mb-2">
          <h3 class="text-xl font-semibold text-gray-900 flex-1">
            ${escapeHtml(result.chunk.book_title)}
          </h3>
          <span class="text-sm font-medium text-blue-600 ml-4">
            ${score}%
          </span>
        </div>
        <p class="text-gray-700 font-medium mb-2">
          ${escapeHtml(result.chunk.chapter_title)}
        </p>
        <p class="text-sm text-gray-500 mb-3">
          by ${escapeHtml(result.chunk.author)} •
          ${result.chunk.word_count.toLocaleString()} words
        </p>
        ${tags.length > 0 ? `
          <div class="flex flex-wrap gap-2">
            ${tags.map(tag => `
              <span class="text-xs bg-blue-50 text-blue-700 px-3 py-1 rounded-full">
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
    <div class="flex justify-center items-center gap-2 mt-8 mb-4">
      <button id="prev-page"
              class="px-4 py-2 rounded-lg border ${currentPage === 1 ? 'border-gray-200 text-gray-400 cursor-not-allowed' : 'border-blue-500 text-blue-600 hover:bg-blue-50'}"
              ${currentPage === 1 ? 'disabled' : ''}>
        Previous
      </button>

      <div class="flex items-center gap-1">
        ${generatePageNumbers(currentPage, totalPages)}
      </div>

      <button id="next-page"
              class="px-4 py-2 rounded-lg border ${currentPage === totalPages ? 'border-gray-200 text-gray-400 cursor-not-allowed' : 'border-blue-500 text-blue-600 hover:bg-blue-50'}"
              ${currentPage === totalPages ? 'disabled' : ''}>
        Next
      </button>
    </div>
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
      return '<span class="px-2 text-gray-400">...</span>';
    }

    const isActive = page === current;
    return `
      <button class="page-number px-3 py-1 rounded ${isActive ? 'bg-blue-600 text-white' : 'hover:bg-gray-100 text-gray-700'}"
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

/**
 * Handle search with debouncing
 */
function handleSearchInput() {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(performSearch, 300);
}

// Event listeners
initButton.addEventListener('click', initialize);
searchButton.addEventListener('click', performSearch);
searchInput.addEventListener('input', handleSearchInput);
searchInput.addEventListener('keypress', (e) => {
  if (e.key === 'Enter') {
    clearTimeout(debounceTimer);
    performSearch();
  }
});

// Auto-initialize on load (optional - you can remove this if you want manual init)
// window.addEventListener('load', initialize);
