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
    const results = await searchEngine.search(query, 20);

    // Hide loading state
    loadingDiv.classList.add('hidden');
    searchButton.disabled = false;

    if (results.length === 0) {
      updateStatus(`No results found for "${query}"`);
      resultsDiv.innerHTML = '<p class="text-gray-500 text-center py-8">No results found. Try different keywords.</p>';
      return;
    }

    updateStatus(`Found ${results.length} results for "${query}"`);

    // Render results
    resultsDiv.innerHTML = results.map((result, idx) => {
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
  } catch (error) {
    console.error('Search error:', error);
    updateStatus(`Search error: ${error.message}`, 'error');
    loadingDiv.classList.add('hidden');
    searchButton.disabled = false;
  }
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
