import { marked } from 'marked';
import { escapeHtml, parseTags } from './utils.js';

const titleEl = document.getElementById('title');
const chapterEl = document.getElementById('chapter');
const contentEl = document.getElementById('content');
const tagsEl = document.getElementById('tags');

document.getElementById('backLink').addEventListener('click', (e) => {
  e.preventDefault();
  history.back();
});

function stripLeadingChapterHeading(body, chapterTitle) {
  const escaped = chapterTitle.trim().replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return body.replace(new RegExp(`^\\s*#{1,6}\\s+${escaped}\\s*\\n+`), '');
}

async function loadChunk() {
  try {
    const chunkId = parseInt(new URLSearchParams(location.search).get('id'));
    if (isNaN(chunkId)) throw new Error('Invalid chunk ID');

    const res = await fetch(`${import.meta.env.BASE_URL}data/metadata.json`);
    const metadata = await res.json();
    const chunk = metadata.chunks.find(c => c.chunk_id === chunkId);
    if (!chunk) throw new Error(`Chunk ${chunkId} not found`);

    document.title = chunk.chapter_title || chunk.book_title;
    titleEl.textContent = chunk.book_title;
    chapterEl.textContent = chunk.chapter_title || '';

    const raw = chunk.content || '';
    const body = chunk.chapter_title ? stripLeadingChapterHeading(raw, chunk.chapter_title) : raw;
    contentEl.innerHTML = marked.parse(body);

    const base = import.meta.env.BASE_URL;
    tagsEl.innerHTML = parseTags(chunk.tags).map(t =>
      `<a class="badge outline" href="${base}?tag=${encodeURIComponent(t)}">${escapeHtml(t)}</a>`
    ).join('');
  } catch (error) {
    contentEl.innerHTML = `<p role="alert" data-variant="danger">Error: ${escapeHtml(error.message)}</p>`;
  }
}

loadChunk();
