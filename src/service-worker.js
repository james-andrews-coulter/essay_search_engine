/**
 * Service Worker for offline search capability
 * Caches model, embeddings, and metadata on first visit
 * Detects and downloads updates when new embeddings are published
 */

const CACHE_NAME = 'essay-search-v1';
const ASSETS_TO_CACHE = [
  '/essay_search_engine/',
  '/essay_search_engine/index.html',
  '/essay_search_engine/data/metadata.json',
  '/essay_search_engine/data/version.json',
  '/essay_search_engine/data/embeddings.json'
];

/**
 * Install event: Pre-cache critical assets
 */
self.addEventListener('install', (event) => {
  console.log('[SW] Installing...');
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      console.log('[SW] Caching critical assets');
      // Try to cache, but don't fail if some assets don't exist yet
      return Promise.allSettled(
        ASSETS_TO_CACHE.map(url => cache.add(url).catch(() => {
          console.log(`[SW] Could not cache ${url} (may not exist yet)`);
        }))
      );
    }).then(() => self.skipWaiting())
  );
});

/**
 * Activate event: Clean up old caches and claim clients
 */
self.addEventListener('activate', (event) => {
  console.log('[SW] Activating...');
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames
          .filter(name => name !== CACHE_NAME)
          .map(name => {
            console.log(`[SW] Deleting old cache: ${name}`);
            return caches.delete(name);
          })
      );
    }).then(() => self.clients.claim())
  );
});

/**
 * Fetch event: Serve from cache, fallback to network
 */
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // Skip non-GET requests
  if (event.request.method !== 'GET') {
    return;
  }

  // Skip external domains
  if (!url.pathname.includes('/essay_search_engine/')) {
    return;
  }

  event.respondWith(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.match(event.request).then((response) => {
        // Return cached response if available
        if (response) {
          return response;
        }

        // Otherwise fetch from network
        return fetch(event.request).then((response) => {
          // Don't cache non-successful responses
          if (!response || response.status !== 200) {
            return response;
          }

          // Clone the response before caching
          const responseToCache = response.clone();

          // Cache large files (embeddings.json, models) for offline use
          const shouldCache =
            url.pathname.includes('embeddings.json') ||
            url.pathname.includes('metadata.json') ||
            url.pathname.includes('version.json') ||
            url.pathname.endsWith('.js') ||
            url.pathname.endsWith('.css') ||
            url.pathname.endsWith('.html');

          if (shouldCache) {
            cache.put(event.request, responseToCache);
          }

          return response;
        });
      }).catch(() => {
        // Offline fallback: return cached response or offline page
        return cache.match(event.request);
      });
    })
  );
});

/**
 * Handle messages from clients (for update detection)
 */
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'CHECK_FOR_UPDATES') {
    console.log('[SW] Checking for updates...');
    checkForUpdates(event.ports[0]);
  }
});

/**
 * Check if new version of embeddings is available
 * Downloads in background if newer version exists
 */
async function checkForUpdates(port) {
  try {
    // Fetch current version from network
    const response = await fetch('/essay_search_engine/data/version.json?t=' + Date.now());

    if (!response.ok) {
      port.postMessage({
        type: 'UPDATE_CHECK_FAILED',
        error: `HTTP ${response.status}`
      });
      return;
    }

    const newVersion = await response.json();

    // Get cached version
    const cache = await caches.open(CACHE_NAME);
    const cachedVersionResponse = await cache.match('/essay_search_engine/data/version.json');
    const cachedVersion = cachedVersionResponse ? await cachedVersionResponse.json() : null;

    // Compare versions
    if (!cachedVersion || newVersion.checksum !== cachedVersion.checksum) {
      console.log('[SW] New version detected, downloading embeddings...');

      // Download new embeddings in background
      try {
        const embeddingsResponse = await fetch('/essay_search_engine/data/embeddings.json');
        if (embeddingsResponse.ok) {
          await cache.put('/essay_search_engine/data/embeddings.json', embeddingsResponse);
          await cache.put('/essay_search_engine/data/version.json',
            new Response(JSON.stringify(newVersion)));

          port.postMessage({
            type: 'UPDATE_AVAILABLE',
            newVersion: newVersion
          });
        }
      } catch (err) {
        console.error('[SW] Failed to download new embeddings:', err);
        port.postMessage({
          type: 'UPDATE_FAILED',
          error: err.message
        });
      }
    } else {
      port.postMessage({
        type: 'UP_TO_DATE',
        version: cachedVersion
      });
    }
  } catch (error) {
    console.error('[SW] Update check error:', error);
    port.postMessage({
      type: 'UPDATE_CHECK_FAILED',
      error: error.message
    });
  }
}
