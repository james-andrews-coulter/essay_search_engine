/**
 * Service Worker for offline search capability
 * Caches model, embeddings, and metadata on first visit
 * Detects and downloads updates when new embeddings are published
 */

const CACHE_NAME = 'essay-search-v2';  // Bumped version for model caching
const MODEL_CACHE_NAME = 'transformers-model-v1';  // Separate cache for large model files

const ASSETS_TO_CACHE = [
  '/essay_search_engine/',
  '/essay_search_engine/index.html',
  '/essay_search_engine/data/metadata.json',
  '/essay_search_engine/data/version.json',
  '/essay_search_engine/data/embeddings.json'
];

// HuggingFace domains that serve model files
const MODEL_DOMAINS = [
  'huggingface.co',
  'cdn-lfs.huggingface.co',
  'cdn-lfs-us-1.huggingface.co'
];

/**
 * Install event: Pre-cache critical assets + all chunk HTML pages
 */
self.addEventListener('install', (event) => {
  console.log('[SW] Installing...');
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      console.log('[SW] Caching critical assets');
      // Try to cache critical assets, but don't fail if some don't exist yet
      return Promise.allSettled(
        ASSETS_TO_CACHE.map(url => cache.add(url).catch(() => {
          console.log(`[SW] Could not cache ${url} (may not exist yet)`);
        }))
      );
    }).then(() => {
      // After critical assets, fetch metadata and pre-cache all chunks
      return fetch('/essay_search_engine/data/metadata.json')
        .then(response => response.json())
        .then(metadata => {
          const chunks = metadata.chunks || [];
          console.log(`[SW] Pre-caching ${chunks.length} chunk pages...`);

          // Extract all unique chunk files from metadata
          const chunkFiles = new Set();
          chunks.forEach(chunk => {
            if (chunk.file) {
              chunkFiles.add(`/essay_search_engine/chunks/${chunk.file}`);
            }
          });

          // Pre-cache all chunks
          return caches.open(CACHE_NAME).then(cache => {
            return Promise.allSettled(
              Array.from(chunkFiles).map(url => {
                return cache.add(url).catch((err) => {
                  console.warn(`[SW] Could not cache chunk: ${url}`, err.message);
                });
              })
            );
          });
        })
        .catch(err => {
          console.warn('[SW] Could not pre-cache chunks:', err.message);
          // Don't fail install if chunk caching fails
        });
    }).then(() => {
      console.log('[SW] Install complete');
      self.skipWaiting();
    })
  );
});

/**
 * Activate event: Clean up old caches and claim clients
 */
self.addEventListener('activate', (event) => {
  console.log('[SW] Activating...');
  const CACHES_TO_KEEP = [CACHE_NAME, MODEL_CACHE_NAME];

  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames
          .filter(name => !CACHES_TO_KEEP.includes(name))
          .map(name => {
            console.log(`[SW] Deleting old cache: ${name}`);
            return caches.delete(name);
          })
      );
    }).then(() => self.clients.claim())
  );
});

/**
 * Check if URL is from a HuggingFace model CDN
 */
function isModelRequest(url) {
  return MODEL_DOMAINS.some(domain => url.hostname.includes(domain));
}

/**
 * Check if this is an app request (our domain)
 */
function isAppRequest(url) {
  return url.pathname.includes('/essay_search_engine/');
}

/**
 * Fetch event: Serve from cache, fallback to network
 * Handles both app assets and HuggingFace model files
 */
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // Skip non-GET requests
  if (event.request.method !== 'GET') {
    return;
  }

  // Skip HuggingFace model requests - let transformers.js handle its own caching
  // Note: Safari has issues with SW intercepting cross-origin requests
  if (isModelRequest(url)) {
    return;  // Don't intercept - pass through to network
  }

  // Skip other external domains
  if (!isAppRequest(url)) {
    return;
  }

  // Handle app requests
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

          // Cache large files (embeddings.json, models, chunks) for offline use
          const shouldCache =
            url.pathname.includes('embeddings.json') ||
            url.pathname.includes('metadata.json') ||
            url.pathname.includes('version.json') ||
            url.pathname.includes('/chunks/') ||
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
 * Handle model file requests from HuggingFace CDN
 * Uses cache-first strategy for offline support
 *
 * Note: Safari has stricter CORS handling for Service Workers.
 * We use a URL-based cache key to work around Safari's request object limitations.
 */
async function handleModelRequest(request, url) {
  const cache = await caches.open(MODEL_CACHE_NAME);
  const cacheKey = url.href;  // Use URL string as cache key for Safari compatibility

  // Try cache first using URL as key
  const cachedResponse = await cache.match(cacheKey);
  if (cachedResponse) {
    console.log('[SW] Model file served from cache:', url.pathname.slice(-50));
    return cachedResponse;
  }

  // Not in cache, fetch from network
  try {
    console.log('[SW] Fetching model file:', url.pathname.slice(-50));

    // Create a new request with explicit CORS mode for Safari compatibility
    const corsRequest = new Request(url.href, {
      method: 'GET',
      mode: 'cors',
      credentials: 'omit',
      headers: request.headers
    });

    const response = await fetch(corsRequest);

    // Only cache successful, non-opaque responses
    if (response.ok && response.type !== 'opaque') {
      // Cache model files (.onnx, .json config files, tokenizer files)
      const shouldCache =
        url.pathname.endsWith('.onnx') ||
        url.pathname.endsWith('.json') ||
        url.pathname.includes('tokenizer') ||
        url.pathname.includes('config') ||
        url.pathname.includes('model');

      if (shouldCache) {
        console.log('[SW] Caching model file for offline use');
        // Clone and cache with URL string key for Safari compatibility
        const responseToCache = response.clone();
        await cache.put(cacheKey, responseToCache);
      }
    }

    return response;
  } catch (error) {
    console.error('[SW] Failed to fetch model file:', error.message);
    // Return cached version if available (might have partial cache)
    const fallback = await cache.match(cacheKey);
    if (fallback) {
      return fallback;
    }
    // Don't throw - let the original request proceed without SW intervention
    return fetch(request);
  }
}

/**
 * Handle messages from clients (for update detection)
 */
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'CHECK_FOR_UPDATES') {
    console.log('[SW] Checking for updates...');
    // Note: event.ports[0] may be undefined if MessageChannel wasn't used
    checkForUpdates(event.ports?.[0] || null);
  }
});

/**
 * Check if new version of embeddings is available
 * Downloads in background if newer version exists
 */
async function checkForUpdates(port) {
  // Helper to safely post messages (port may be null)
  const notify = (message) => {
    if (port) {
      port.postMessage(message);
    } else {
      console.log('[SW] Update status:', message.type);
    }
  };

  try {
    // Fetch current version from network
    const response = await fetch('/essay_search_engine/data/version.json?t=' + Date.now());

    if (!response.ok) {
      notify({ type: 'UPDATE_CHECK_FAILED', error: `HTTP ${response.status}` });
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

          notify({ type: 'UPDATE_AVAILABLE', newVersion: newVersion });
        }
      } catch (err) {
        console.error('[SW] Failed to download new embeddings:', err);
        notify({ type: 'UPDATE_FAILED', error: err.message });
      }
    } else {
      notify({ type: 'UP_TO_DATE', version: cachedVersion });
    }
  } catch (error) {
    console.error('[SW] Update check error:', error);
    notify({ type: 'UPDATE_CHECK_FAILED', error: error.message });
  }
}
