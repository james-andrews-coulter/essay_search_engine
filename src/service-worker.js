const CACHE_VERSION = 'v10';
const CACHE_NAME = `shelf-${CACHE_VERSION}`;

// Derive base path from the SW's own URL so the same code works for any repo name
const BASE = self.location.pathname.replace(/service-worker\.js$/, '');

const PRECACHE_ASSETS = [
  BASE,
  `${BASE}index.html`,
  `${BASE}chunk.html`,
  `${BASE}tags.html`,
  `${BASE}data/metadata.json`,
  `${BASE}data/tags.json`
];

// Paths that carry query strings — strip the query when matching cache
const NAV_PATHS = new Set([BASE, `${BASE}chunk.html`]);

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(PRECACHE_ASSETS))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((names) => Promise.all(
        names
          .filter((n) => (n.startsWith('shelf-') || n.startsWith('essay-search-')) && n !== CACHE_NAME)
          .map((n) => caches.delete(n))
      ))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  const cacheKey = url.search && NAV_PATHS.has(url.pathname) ? url.pathname : event.request;

  event.respondWith(
    caches.match(cacheKey).then((cached) => {
      if (cached) return cached;
      return fetch(event.request).then((response) => {
        if (response?.status === 200) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
        }
        return response;
      }).catch(() => new Response('Not found', { status: 404 }));
    })
  );
});
