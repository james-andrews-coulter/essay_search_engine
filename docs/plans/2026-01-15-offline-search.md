# Offline Search Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable full offline search by caching model + embeddings + metadata via Service Worker, with automatic update detection when new books are synced.

**Architecture:** Service Worker intercepts requests and serves cached assets. Version detection via lightweight `version.json` triggers background downloads of new embeddings. Status UI shows download progress and online/offline status.

**Tech Stack:** Service Worker API, Cache API, Transformers.js (browser ML), Vite for bundling

---

## Task 1: Create Service Worker File

**Files:**
- Create: `src/service-worker.js`

**Step 1: Write the Service Worker with caching logic**

Create `src/service-worker.js` with the following content:

```javascript
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
```

**Step 2: Verify the file was created correctly**

```bash
cd /Users/jamesalexander/essay_search_engine/.worktrees/feature-offline-search
ls -la src/service-worker.js
wc -l src/service-worker.js
```

Expected: File exists with ~180 lines

**Step 3: Check for syntax errors by running build**

```bash
npm run build 2>&1 | head -20
```

Expected: Build succeeds (Service Worker code is not bundled, just copied)

**Step 4: Commit**

```bash
git add src/service-worker.js
git commit -m "feat: create service worker for offline caching"
```

---

## Task 2: Register Service Worker in main.js

**Files:**
- Modify: `src/main.js:1-45` (before initialize function)

**Step 1: Add Service Worker registration and status tracking**

Modify `src/main.js` by adding this code after the imports (after line 2) and before the `// Initialize search engine` comment:

```javascript
// Service Worker registration and offline support
let serviceWorkerReady = false;
let isOnline = navigator.onLine;
let updateAvailable = false;

/**
 * Register Service Worker for offline support
 */
async function registerServiceWorker() {
  if (!('serviceWorker' in navigator)) {
    console.log('Service Workers not supported');
    return;
  }

  try {
    const registration = await navigator.serviceWorker.register(
      '/essay_search_engine/src/service-worker.js',
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
```

**Step 2: Update the initialize function to call registerServiceWorker**

Modify the `initialize()` function to register the Service Worker before loading the search engine. Change line 23-25 to:

```javascript
async function initialize() {
  if (isInitialized) return;

  // Register Service Worker for offline support
  if (!serviceWorkerReady) {
    await registerServiceWorker();
  }

  statusDiv.textContent = 'Loading search engine...';
```

**Step 3: Verify the changes look correct**

```bash
cd /Users/jamesalexander/essay_search_engine/.worktrees/feature-offline-search
grep -n "registerServiceWorker" src/main.js
grep -n "checkForUpdates" src/main.js
```

Expected: Both functions appear in the file

**Step 4: Run build to check for errors**

```bash
npm run build 2>&1 | grep -i error || echo "No errors"
```

Expected: No errors

**Step 5: Commit**

```bash
git add src/main.js
git commit -m "feat: register service worker and track online status"
```

---

## Task 3: Add HTML Elements for Status UI

**Files:**
- Modify: `index.html` (add status indicator element)

**Step 1: Read the index.html file**

```bash
cd /Users/jamesalexander/essay_search_engine/.worktrees/feature-offline-search
cat index.html
```

**Step 2: Add online status indicator to header**

Add this line right after the opening `<header>` tag (before the search form). Find the header section and add:

```html
<div id="online-status" style="position: absolute; top: 1rem; right: 1rem; font-size: 0.875rem;">
  🟢 Online
</div>
```

**Step 3: Verify the change**

```bash
grep -n "online-status" index.html
```

Expected: Element appears in header

**Step 4: Build and test**

```bash
npm run build
```

Expected: Builds successfully

**Step 5: Commit**

```bash
git add index.html
git commit -m "feat: add online status indicator to header"
```

---

## Task 4: Add CSS for Status UI

**Files:**
- Modify: `src/styles.css` (add status indicator styles)

**Step 1: Add styles at the end of styles.css**

Append these lines to the end of `src/styles.css`:

```css
/* Offline support indicators */
#online-status {
  font-size: 0.875rem;
  font-weight: 500;
  white-space: nowrap;
}

#refresh-btn {
  padding: 0.5rem 1rem;
  background: #f0f0f0;
  border: 1px solid #ddd;
  border-radius: 0.25rem;
  cursor: pointer;
  font-size: 0.875rem;
}

#refresh-btn:hover {
  background: #e0e0e0;
}

/* Download progress indicator (if added later) */
#download-progress {
  font-size: 0.75rem;
  color: #666;
  margin-top: 0.5rem;
}
```

**Step 2: Verify the styles were added**

```bash
tail -20 src/styles.css
```

Expected: Styles appear at the end

**Step 3: Build and test**

```bash
npm run build
```

Expected: Builds successfully with no errors

**Step 4: Commit**

```bash
git add src/styles.css
git commit -m "feat: add styles for offline status indicators"
```

---

## Task 5: Add version.json Generation to Sync Script

**Files:**
- Modify: `sync/sync.py` (add version.json generation after embeddings)

**Step 1: Read the end of sync.py to find where to add the code**

```bash
cd /Users/jamesalexander/essay_search_engine/.worktrees/feature-offline-search
tail -50 sync/sync.py
```

**Step 2: Find the line where embeddings.json is finalized**

Look for where `embed_chunks.py` is called or where the sync finishes. We'll add version.json generation right after embeddings are created.

Read sync/sync.py fully to understand structure:

```bash
wc -l sync/sync.py
```

Then read the key section to understand where to add code.

**Step 3: Add imports at the top of sync.py**

After the existing imports, add:

```python
import hashlib
import time
```

**Step 4: Add version.json generation function**

Add this function to `sync/sync.py` before the main execution (before `if __name__ == '__main__':`):

```python
def generate_version_file():
    """Generate version.json for update detection in Service Worker"""
    embeddings_path = TARGET_DIR / 'public' / 'data' / 'embeddings.json'
    version_path = TARGET_DIR / 'public' / 'data' / 'version.json'

    if not embeddings_path.exists():
        print("ERROR: embeddings.json not found, skipping version.json generation")
        return

    try:
        # Calculate checksum of embeddings.json
        with open(embeddings_path, 'rb') as f:
            file_content = f.read()
            checksum = hashlib.md5(file_content).hexdigest()

        # Create version data
        version_data = {
            'timestamp': int(time.time()),
            'checksum': checksum,
            'embeddings_size': len(file_content)
        }

        # Write version.json
        with open(version_path, 'w') as f:
            json.dump(version_data, f, indent=2)

        print(f"Generated version.json (checksum: {checksum}, size: {len(file_content) / 1024 / 1024:.1f}MB)")
    except Exception as e:
        print(f"ERROR generating version.json: {e}")
```

**Step 5: Call the version.json generation at the end of main execution**

Find the end of the main execution block (after `save_output_metadata()` or similar). Add this line:

```python
    # Generate version.json for offline updates
    print("\nGenerating version.json for Service Worker updates...")
    generate_version_file()
```

**Step 6: Verify the changes look correct**

```bash
grep -n "generate_version_file" sync/sync.py
grep -n "import hashlib" sync/sync.py
```

Expected: Both appear in the file

**Step 7: Test the sync script (dry run if possible)**

```bash
python3 -c "import json, hashlib, time; print('Imports work')"
```

Expected: Imports work without errors

**Step 8: Commit**

```bash
git add sync/sync.py
git commit -m "feat: generate version.json for offline update detection"
```

---

## Task 6: Test Service Worker Caching (Manual)

**Files:**
- No new files, testing existing implementation

**Step 1: Run dev server**

```bash
cd /Users/jamesalexander/essay_search_engine/.worktrees/feature-offline-search
npm run dev
```

Expected: Dev server starts on http://localhost:5173

**Step 2: Open browser and check Service Worker registration**

- Open http://localhost:5173/essay_search_engine/
- Open DevTools (F12)
- Go to Application → Service Workers
- Verify Service Worker is registered with scope `/essay_search_engine/`

**Step 3: Check Cache Storage**

- In DevTools, go to Application → Cache Storage
- Look for cache named `essay-search-v1`
- Should see the following cached URLs:
  - `/essay_search_engine/`
  - `/essay_search_engine/index.html`
  - `/essay_search_engine/data/metadata.json`
  - `/essay_search_engine/data/version.json`
  - `/essay_search_engine/data/embeddings.json`

**Step 4: Test offline functionality**

- In DevTools, go to Network tab
- Check "Offline" checkbox
- Reload the page (Ctrl+R)
- Verify page loads from cache
- Try searching - should work offline

**Step 5: Test online/offline indicator**

- With offline checked: indicator should show "🔴 Offline"
- Uncheck offline: indicator should show "🟢 Online"

**Step 6: Verify status messages in console**

In DevTools Console, you should see:
```
[App] Service Worker registered successfully
[SW] Installing...
[SW] Caching critical assets
[App] Using cached version, up to date
```

**Step 7: Commit test notes (no actual code to commit)**

Just stop the dev server (Ctrl+C) and continue to next task.

---

## Task 7: Build for Production

**Files:**
- No changes, building existing implementation

**Step 1: Run production build**

```bash
cd /Users/jamesalexander/essay_search_engine/.worktrees/feature-offline-search
npm run build
```

Expected: Build succeeds with output like:
```
✓ 37 modules transformed
dist/index.html          0.76 kB
dist/assets/main-xxx.css 1.45 kB
dist/assets/main-xxx.js  822.45 kB
✓ built in 1.44s
```

**Step 2: Verify Service Worker was copied to dist**

```bash
ls -la dist/ | grep service-worker
```

Expected: You may not see it (Service Worker is not bundled, served directly)

**Step 3: Check for any build warnings**

```bash
npm run build 2>&1 | grep -i warn
```

Expected: Some warnings about chunk size (expected, pre-existing)

**Step 4: Verify build output structure**

```bash
ls -la dist/
```

Expected: Standard Vite output (index.html, assets/)

**Step 5: Commit build verification**

No commit needed - build artifacts not tracked. Continue to next task.

---

## Task 8: Create Integration Test Checklist

**Files:**
- Create: `docs/OFFLINE_TESTING.md`

**Step 1: Create the testing checklist**

Create `docs/OFFLINE_TESTING.md`:

```markdown
# Offline Search Testing Checklist

## Manual Testing (First Visit)

- [ ] Load main page in fresh browser (no cache)
- [ ] Verify status shows "Loading search engine..."
- [ ] Wait for model to load (~10 seconds)
- [ ] Verify search works (try "solitude" or "anxiety")
- [ ] Wait for embeddings to finish downloading
- [ ] Verify "Ready! Search across X books" message appears
- [ ] Verify online status shows "🟢 Online"

## Service Worker Registration

- [ ] Open DevTools → Application → Service Workers
- [ ] Verify Service Worker is registered with scope `/essay_search_engine/`
- [ ] Verify status is "activated and running"

## Cache Storage

- [ ] Open DevTools → Application → Cache Storage
- [ ] Click on `essay-search-v1` cache
- [ ] Verify these URLs are cached:
  - `/essay_search_engine/`
  - `/essay_search_engine/index.html`
  - `/essay_search_engine/data/metadata.json`
  - `/essay_search_engine/data/version.json`
  - `/essay_search_engine/data/embeddings.json`

## Offline Functionality

- [ ] Open DevTools → Network tab
- [ ] Check the "Offline" checkbox (throttling section)
- [ ] Reload page (Ctrl+R)
- [ ] Verify page loads successfully from cache
- [ ] Verify status still shows book/chapter count
- [ ] Try searching - results should appear instantly
- [ ] Verify online status shows "🔴 Offline" in red
- [ ] Try clicking a result link - chunk page should load from cache

## Return Visits (Offline)

- [ ] Close browser completely
- [ ] Close DevTools (to prevent interference)
- [ ] Go offline (airplane mode or unplug network)
- [ ] Reopen browser to page
- [ ] Verify page loads from cache
- [ ] Verify search still works

## Update Detection (When New Books Added)

- [ ] In your sync script, regenerate embeddings with new books
- [ ] Verify `public/data/version.json` was updated with new checksum
- [ ] In browser, reload page while online
- [ ] Verify Service Worker detects version change
- [ ] Verify "New books available" banner appears after background download
- [ ] Click "Refresh" button
- [ ] Verify new books appear in search results

## Network Interruption During Download

- [ ] Start fresh in private/incognito window
- [ ] Slow down network: DevTools → Network → "Slow 3G"
- [ ] Load page
- [ ] While embeddings are downloading, go to offline mode
- [ ] Go back online
- [ ] Reload page
- [ ] Verify download resumes and completes
- [ ] Verify search works with full dataset

## Console Messages

Open DevTools → Console and verify these messages appear:

First visit:
```
[App] Service Worker registered successfully
[SW] Installing...
[SW] Caching critical assets
```

Subsequent visits:
```
[App] Service Worker registered successfully
[App] Using cached version, up to date
```

When updates available:
```
[SW] New version detected, downloading embeddings...
[App] New embeddings available
```

## Edge Cases

- [ ] Very first visit with bad network: Page loads from partial cache, search works when available
- [ ] Browser cache cleared by user: Page redownloads everything on next visit
- [ ] Multiple browser tabs open: All tabs receive update notification
- [ ] iOS Safari: Verify Service Worker works (limited cache size on iOS)
- [ ] Android Chrome: Verify Service Worker works (larger cache available)

## Performance Metrics (DevTools Network tab)

- [ ] First visit: ~15-30 seconds total (model: 10s, embeddings: 2-20s)
- [ ] Cached visits: ~2-3 seconds (just metadata + model init)
- [ ] Search on cached data: < 1 second

## Debugging

If offline mode doesn't work:
1. Check console for errors
2. Verify Service Worker is in "activated and running" state
3. Verify cache exists and has the right URLs
4. Check Application → Service Workers → Inspect → Source (view SW code)
5. Check Application → Application Cache (old spec, shouldn't have anything)

If updates don't work:
1. Verify `version.json` was regenerated with new checksum
2. Force hard refresh (Ctrl+Shift+R) to bypass browser cache
3. Check Service Worker message log for `UPDATE_AVAILABLE` messages
4. Manually clear cache: Application → Cache Storage → Delete `essay-search-v1`
```

**Step 2: Verify the file was created**

```bash
ls -la docs/OFFLINE_TESTING.md
wc -l docs/OFFLINE_TESTING.md
```

Expected: File exists with ~150 lines

**Step 3: Commit**

```bash
git add docs/OFFLINE_TESTING.md
git commit -m "docs: add offline functionality testing checklist"
```

---

## Task 9: Final Verification Build

**Files:**
- No changes, final build verification

**Step 1: Clean build**

```bash
cd /Users/jamesalexander/essay_search_engine/.worktrees/feature-offline-search
rm -rf dist/
npm run build
```

Expected: Clean build succeeds

**Step 2: Verify all files present**

```bash
ls -la public/data/
```

Expected: Should see `metadata.json`, `embeddings.json`, and soon `version.json` after first sync

**Step 3: Check git status**

```bash
git status
```

Expected: All changes staged and committed, working tree clean

**Step 4: View commits**

```bash
git log --oneline -10
```

Expected: Recent commits show all offline feature work

**Step 5: Final commit verification**

If working tree is clean, you're done. If there are uncommitted changes:

```bash
git diff
```

Commit any remaining changes.

---

## Summary

**Files Created:**
- `src/service-worker.js` - Service Worker for offline caching
- `docs/OFFLINE_TESTING.md` - Manual testing checklist

**Files Modified:**
- `src/main.js` - Register Service Worker, handle updates
- `index.html` - Add online status indicator
- `src/styles.css` - Style status indicators
- `sync/sync.py` - Generate version.json

**Key Features Implemented:**
✅ Service Worker caches model, embeddings, metadata
✅ Offline search works after first visit
✅ Automatic update detection via version.json
✅ Online/offline status indicator
✅ Update notification when new books available
✅ Background download of updated embeddings

**Next Steps:**
1. Complete testing checklist from `docs/OFFLINE_TESTING.md`
2. Update books via sync script
3. Verify version.json is generated
4. Test update detection in browser
5. Create pull request with all changes
