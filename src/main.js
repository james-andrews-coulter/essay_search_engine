import './styles.css';
import { SearchEngine } from './search.js';

// Service Worker registration and offline support
let serviceWorkerReady = false;
let isOnline = navigator.onLine;
let updateAvailable = false;

/**
 * Register Service Worker for offline support
 * Only registers in production (not during Vite dev server)
 */
async function registerServiceWorker() {
  // Skip SW in development - it interferes with Vite's dev server
  const isDev = window.location.hostname === 'localhost' ||
                window.location.hostname === '127.0.0.1' ||
                window.location.port === '5173';

  if (isDev) {
    console.log('[App] Skipping Service Worker in development mode');
    // Unregister any existing SW from previous sessions
    if ('serviceWorker' in navigator) {
      const registrations = await navigator.serviceWorker.getRegistrations();
      for (const registration of registrations) {
        await registration.unregister();
      }
    }
    return;
  }

  if (!('serviceWorker' in navigator)) {
    console.log('Service Workers not supported');
    return;
  }

  try {
    const registration = await navigator.serviceWorker.register(
      '/essay_search_engine/service-worker.js',
      { scope: '/essay_search_engine/' }
    );
    console.log('[App] Service Worker registered successfully');
    serviceWorkerReady = true;

    // Check for updates periodically (every 5 minutes)
    checkForUpdatesIfOnline();
    setInterval(() => {
      if (isOnline) checkForUpdatesIfOnline();
    }, 5 * 60 * 1000);

  } catch (error) {
    console.error('[App] Service Worker registration failed:', error);
  }
}

/**
 * Check if new version of embeddings is available
 */
function checkForUpdatesIfOnline() {
  if (!isOnline || !serviceWorkerReady) return;

  navigator.serviceWorker.controller?.postMessage({
    type: 'CHECK_FOR_UPDATES'
  });
}

/**
 * Handle messages from Service Worker
 */
navigator.serviceWorker?.addEventListener('message', (event) => {
  const message = event.data;

  if (message.type === 'UPDATE_AVAILABLE') {
    console.log('[App] New embeddings available');
    updateAvailable = true;
    showUpdateNotification();
  } else if (message.type === 'UP_TO_DATE') {
    console.log('[App] Using cached version, up to date');
  } else if (message.type === 'UPDATE_FAILED') {
    console.warn('[App] Failed to download update:', message.error);
  }
});

/**
 * Show notification that updates are available
 */
function showUpdateNotification() {
  const statusDiv = document.getElementById('status');
  if (statusDiv && !statusDiv.textContent.includes('New books')) {
    const original = statusDiv.textContent;
    statusDiv.innerHTML = `
      ${original}
      <button id="refresh-btn" style="margin-left: 1rem; padding: 0.5rem 1rem;">
        📚 New books available. Refresh
      </button>
    `;

    document.getElementById('refresh-btn')?.addEventListener('click', () => {
      window.location.reload();
    });
  }
}

/**
 * Track online/offline status
 */
window.addEventListener('online', () => {
  isOnline = true;
  updateOnlineStatus();
  checkForUpdatesIfOnline();
});

window.addEventListener('offline', () => {
  isOnline = false;
  updateOnlineStatus();
});

/**
 * Update UI to show online/offline status
 */
function updateOnlineStatus() {
  const statusIndicator = document.getElementById('online-status');
  if (statusIndicator) {
    if (isOnline) {
      statusIndicator.textContent = '🟢 Online';
      statusIndicator.style.color = '#22863a';
    } else {
      statusIndicator.textContent = '🔴 Offline';
      statusIndicator.style.color = '#cb2431';
    }
  }
}

// Initialize search engine
const searchEngine = new SearchEngine();
let isInitialized = false;

// DOM elements
const searchInput = document.getElementById('searchInput');
const searchButton = document.getElementById('searchButton');
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

  // Register Service Worker for offline support
  if (!serviceWorkerReady) {
    await registerServiceWorker();
  }

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
      <a href="/essay_search_engine/chunk.html?id=${result.chunk.chunk_id}" class="result">
        <h2>${escapeHtml(result.chunk.book_title)}</h2>
        <div class="meta">
          ${escapeHtml(result.chunk.chapter_title)}
          ${tags.length > 0 ? `<br><span class="tags">${tags.join(', ')}</span>` : ''}
        </div>
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

// Event listeners - handle search button click and Enter key
searchButton.addEventListener('click', () => {
  performSearch();
});

searchInput.addEventListener('keypress', (e) => {
  if (e.key === 'Enter') {
    performSearch();
  }
});

// Auto-initialize on page load and handle tag parameters
window.addEventListener('DOMContentLoaded', async () => {
  await initialize();

  // Check for tag parameter in URL
  const urlParams = new URLSearchParams(window.location.search);
  const tag = urlParams.get('tag');

  if (tag && isInitialized) {
    searchInput.value = tag;
    performSearch();
  }
});
