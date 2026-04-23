import { SearchEngine } from './search.js';

async function registerServiceWorker() {
  const isDev = window.location.hostname === 'localhost' ||
                window.location.hostname === '127.0.0.1' ||
                window.location.port === '5173';

  if (isDev) {
    if ('serviceWorker' in navigator) {
      const regs = await navigator.serviceWorker.getRegistrations();
      for (const r of regs) await r.unregister();
    }
    return;
  }

  if (!('serviceWorker' in navigator)) return;

  try {
    await navigator.serviceWorker.register(
      '/essay_search_engine/service-worker.js',
      { scope: '/essay_search_engine/' }
    );
  } catch (err) {
    console.error('[App] Service Worker registration failed:', err);
  }
}

const searchEngine = new SearchEngine();
let isInitialized = false;
const selectedTags = new Set();
let allTags = [];

const searchForm = document.getElementById('searchForm');
const searchInput = document.getElementById('searchInput');
const searchButton = document.getElementById('searchButton');
const tagOptions = document.getElementById('tagOptions');
const statusEl = document.getElementById('status');
const resultsEl = document.getElementById('results');
const paginationEl = document.getElementById('pagination');
const tagBadgesEl = document.getElementById('tagBadges');

let allResults = [];
let currentPage = 1;
const resultsPerPage = 25;
let currentQuery = '';

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text == null ? '' : String(text);
  return div.innerHTML;
}

function excerpt(text, maxLen) {
  if (!text) return '';
  const clean = text.replace(/^#{1,6}\s+.*$/m, '').replace(/\s+/g, ' ').trim();
  if (clean.length <= maxLen) return clean;
  const cut = clean.slice(0, maxLen);
  const lastSpace = cut.lastIndexOf(' ');
  return (lastSpace > maxLen * 0.6 ? cut.slice(0, lastSpace) : cut) + '…';
}

function renderBadges() {
  if (selectedTags.size === 0) {
    tagBadgesEl.innerHTML = '';
    return;
  }
  tagBadgesEl.innerHTML = Array.from(selectedTags).map(tag => `
    <span class="badge" data-variant="secondary" data-tag="${escapeHtml(tag)}" role="listitem">
      ${escapeHtml(tag)}
      <button type="button" class="ghost" aria-label="Remove ${escapeHtml(tag)}">&times;</button>
    </span>
  `).join('');

  tagBadgesEl.querySelectorAll('button').forEach(btn => {
    btn.addEventListener('click', () => {
      const tag = btn.closest('[data-tag]').dataset.tag;
      selectedTags.delete(tag);
      renderBadges();
      if (currentQuery || selectedTags.size > 0) performSearch();
      else clearResults();
    });
  });
}

function addTagBadge(tag) {
  selectedTags.add(tag);
  renderBadges();
}

function clearResults() {
  resultsEl.innerHTML = '';
  paginationEl.innerHTML = '';
  allResults = [];
  currentQuery = '';
  statusEl.textContent = '';
}

async function initialize() {
  if (isInitialized) return;
  await registerServiceWorker();
  statusEl.textContent = 'Loading...';

  try {
    await searchEngine.initialize((progress) => {
      statusEl.textContent = progress;
    });

    allTags = searchEngine.getAllTags();
    tagOptions.innerHTML = allTags.map(t => `<option value="${escapeHtml(t)}">`).join('');

    isInitialized = true;
    searchInput.disabled = false;
    searchButton.disabled = false;
    searchInput.focus();
    statusEl.textContent = '';
  } catch (error) {
    console.error('Initialization error:', error);
    statusEl.textContent = `Error: ${error.message}`;
  }
}

async function performSearch() {
  const query = searchInput.value.trim();

  if (!query && selectedTags.size === 0) {
    clearResults();
    return;
  }

  if (!isInitialized) {
    statusEl.textContent = 'Please initialize the search engine first';
    return;
  }

  searchButton.disabled = true;
  statusEl.textContent = 'Searching...';

  try {
    const tags = Array.from(selectedTags);
    const results = await searchEngine.search(query, tags);
    searchButton.disabled = false;

    if (results.length === 0) {
      statusEl.textContent = '';
      resultsEl.innerHTML = '<p class="text-light">No results. Try different keywords or tags.</p>';
      paginationEl.innerHTML = '';
      allResults = [];
      currentQuery = '';
      return;
    }

    allResults = results;
    currentPage = 1;
    currentQuery = query;
    statusEl.textContent = '';
    renderResults();
  } catch (error) {
    console.error('Search error:', error);
    statusEl.textContent = `Search error: ${error.message}`;
    searchButton.disabled = false;
  }
}

function renderResults() {
  if (allResults.length === 0) {
    resultsEl.innerHTML = '';
    paginationEl.innerHTML = '';
    return;
  }

  const totalPages = Math.ceil(allResults.length / resultsPerPage);
  const startIdx = (currentPage - 1) * resultsPerPage;
  const endIdx = Math.min(startIdx + resultsPerPage, allResults.length);
  const pageResults = allResults.slice(startIdx, endIdx);

  resultsEl.innerHTML = '<div class="vstack">' + pageResults.map(r => {
    const tags = r.chunk.tags
      ? r.chunk.tags.split(',').map(t => t.trim()).filter(Boolean)
      : [];
    const preview = excerpt(r.chunk.content, 180);
    const href = `/essay_search_engine/chunk.html?id=${r.chunk.chunk_id}`;
    return `
      <article class="card">
        <header>
          <h3><a href="${href}">${escapeHtml(r.chunk.book_title)}</a></h3>
          ${r.chunk.chapter_title ? `<p class="text-light">${escapeHtml(r.chunk.chapter_title)}</p>` : ''}
        </header>
        ${preview ? `<p>${escapeHtml(preview)}</p>` : ''}
        ${tags.length ? `<footer class="hstack">${tags.map(t => `<a class="badge outline" href="/essay_search_engine/?tag=${encodeURIComponent(t)}">${escapeHtml(t)}</a>`).join('')}</footer>` : ''}
      </article>
    `;
  }).join('') + '</div>';

  if (totalPages <= 1) {
    paginationEl.innerHTML = '';
    return;
  }

  const pages = generatePageNumbers(currentPage, totalPages);
  paginationEl.innerHTML = `
    <menu class="buttons">
      <li><button type="button" class="small outline" id="prev-page" ${currentPage === 1 ? 'disabled' : ''}>← Prev</button></li>
      ${pages.map(p => {
        if (p === '...') return '<li aria-hidden="true"><span class="text-lighter">…</span></li>';
        const active = p === currentPage;
        return `<li><button type="button" class="small ${active ? '' : 'outline'} page-number" data-page="${p}" ${active ? 'aria-current="page" disabled' : ''}>${p}</button></li>`;
      }).join('')}
      <li><button type="button" class="small outline" id="next-page" ${currentPage === totalPages ? 'disabled' : ''}>Next →</button></li>
    </menu>
  `;

  paginationEl.querySelector('#prev-page')?.addEventListener('click', () => {
    if (currentPage > 1) { currentPage--; renderResults(); scrollTop(); }
  });
  paginationEl.querySelector('#next-page')?.addEventListener('click', () => {
    if (currentPage < totalPages) { currentPage++; renderResults(); scrollTop(); }
  });
  paginationEl.querySelectorAll('.page-number').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const p = parseInt(e.currentTarget.dataset.page);
      if (p !== currentPage) { currentPage = p; renderResults(); scrollTop(); }
    });
  });
}

function scrollTop() {
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function generatePageNumbers(current, total) {
  const pages = [];
  if (total <= 7) {
    for (let i = 1; i <= total; i++) pages.push(i);
    return pages;
  }
  pages.push(1);
  const start = Math.max(2, current - 2);
  const end = Math.min(total - 1, current + 2);
  if (start > 2) pages.push('...');
  for (let i = start; i <= end; i++) pages.push(i);
  if (end < total - 1) pages.push('...');
  pages.push(total);
  return pages;
}

searchForm.addEventListener('submit', (e) => {
  e.preventDefault();
  const value = searchInput.value.trim();
  if (allTags.includes(value)) {
    addTagBadge(value);
    searchInput.value = '';
  }
  performSearch();
});

searchInput.addEventListener('input', () => {
  if (allTags.includes(searchInput.value)) {
    addTagBadge(searchInput.value);
    searchInput.value = '';
    performSearch();
  }
});

window.addEventListener('DOMContentLoaded', async () => {
  await initialize();
  const tag = new URLSearchParams(window.location.search).get('tag');
  if (tag && isInitialized) {
    addTagBadge(tag);
    performSearch();
  }
});
