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
