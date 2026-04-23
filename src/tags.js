import { escapeHtml } from './utils.js';

const listEl = document.getElementById('tagList');

async function render() {
  try {
    const res = await fetch('/essay_search_engine/data/tags.json');
    const data = await res.json();
    const tags = (data.tags || []).slice().sort((a, b) => a.tag.localeCompare(b.tag));
    if (tags.length === 0) {
      listEl.innerHTML = '<p class="text-light">No tags yet.</p>';
      return;
    }
    listEl.innerHTML = tags.map(({ tag, count }) => {
      const href = `/essay_search_engine/?tag=${encodeURIComponent(tag)}`;
      return `<a href="${href}" class="badge outline" role="listitem">${escapeHtml(tag)} <small>(${count})</small></a>`;
    }).join('');
  } catch (error) {
    listEl.innerHTML = `<p role="alert" data-variant="danger">Error loading tags: ${escapeHtml(error.message)}</p>`;
  }
}

render();
