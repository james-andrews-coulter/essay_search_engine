// Simplified Service Worker - Cache only, no update notifications
const CACHE_VERSION = 'v7';
const CACHE_NAME = `essay-search-${CACHE_VERSION}`;

// Assets to pre-cache
const PRECACHE_ASSETS = [
  '/essay_search_engine/',
  '/essay_search_engine/index.html',
  '/essay_search_engine/chunk.html',
  '/essay_search_engine/tags.html',
  '/essay_search_engine/data/metadata.json',
  '/essay_search_engine/data/embeddings.json',
  '/essay_search_engine/data/tags.json',
  '/essay_search_engine/models/Xenova/bge-large-en-v1.5/config.json',
  '/essay_search_engine/models/Xenova/bge-large-en-v1.5/tokenizer.json',
  '/essay_search_engine/models/Xenova/bge-large-en-v1.5/tokenizer_config.json',
  '/essay_search_engine/models/Xenova/bge-large-en-v1.5/onnx/model_quantized.onnx',
  '/essay_search_engine/wasm/ort-wasm-simd-threaded.wasm',
  '/essay_search_engine/wasm/ort-wasm-simd.wasm',
  '/essay_search_engine/wasm/ort-wasm-threaded.wasm',
  '/essay_search_engine/wasm/ort-wasm.wasm'
];

// Install: Cache assets
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(PRECACHE_ASSETS);
    }).then(() => self.skipWaiting())
  );
});

// Activate: Clean old caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames
          .filter((name) => name.startsWith('essay-search-') && name !== CACHE_NAME)
          .map((name) => caches.delete(name))
      );
    }).then(() => self.clients.claim())
  );
});

// Fetch: Cache-first strategy
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // Handle root with query params (e.g., /?tag=anxiety)
  if (url.pathname === '/essay_search_engine/' && url.search) {
    event.respondWith(
      caches.match('/essay_search_engine/index.html')
        .then((response) => response || fetch(event.request))
    );
    return;
  }

  // Handle chunk.html with query params (e.g., /chunk.html?id=123)
  if (url.pathname === '/essay_search_engine/chunk.html' && url.search) {
    event.respondWith(
      caches.match('/essay_search_engine/chunk.html')
        .then((response) => response || fetch(event.request))
    );
    return;
  }

  // Cache-first for all other requests
  event.respondWith(
    caches.match(event.request).then((cached) => {
      if (cached) return cached;

      return fetch(event.request).then((response) => {
        // Cache successful responses
        if (response && response.status === 200) {
          const responseClone = response.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, responseClone);
          });
        }
        return response;
      }).catch(() => {
        // Return 404 response if offline and not cached
        return new Response('Not found', { status: 404 });
      });
    })
  );
});
