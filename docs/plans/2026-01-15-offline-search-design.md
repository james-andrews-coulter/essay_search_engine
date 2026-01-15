# Offline Search Feature Design

**Date**: 2026-01-15
**Status**: Design Complete, Ready for Implementation

## Overview

Enable full offline search capability by using a Service Worker to cache the model (~327MB), embeddings (~15MB), and metadata (~219KB). After first visit, users can search their entire collection without internet, with automatic updates when new books are added.

## Architecture

### Service Worker Pattern

**Responsibilities:**
- Cache model, embeddings, and metadata on first visit
- Intercept requests and serve from cache when offline
- Detect new embeddings via `version.json`
- Auto-download updates on next page load
- Handle partial downloads and corruption

**Cache strategy:**
- Cache name: `essay-search-v1` (versioned for easy updates)
- Cached assets:
  - `data/embeddings.json` (15MB)
  - `data/metadata.json` (219KB)
  - `data/version.json` (50 bytes - new file for update detection)
  - HTML/CSS/JS
  - Browser model cache (automatic via Transformers.js)

**Update detection:**

```json
// public/data/version.json (generated during sync)
{
  "timestamp": 1673472000,
  "checksum": "abc123def456"
}
```

When page loads:
1. Service Worker fetches `version.json` (tiny, ~50 bytes)
2. Compares with cached version
3. If different, queues new embeddings for background download
4. User searches with current data
5. On download completion, shows: "📚 New books available. [Refresh]"

### Data Flow

**First Visit:**
```
Page Load
  ↓
Service Worker registers
  ↓
Check for 'essay-search-v1' cache
  ↓
Not found → Start background downloads
  ↓
Model loads (~10s) → Search works immediately
  ↓
Embeddings download (~1-2s on WiFi) → Full offline capability
```

**Subsequent Visits (Online):**
```
Page Load
  ↓
Service Worker fetches version.json (50 bytes)
  ↓
Check against cached version
  ↓
Version matches → Serve from cache, search works offline
  ↓
Version differs → Download new embeddings in background
  ↓
Show notification: "New books available"
```

**Subsequent Visits (Offline):**
```
Page Load
  ↓
Service Worker serves everything from cache
  ↓
Search works perfectly, no network needed
```

## User Interface Changes

**Status indicators** (non-intrusive):
- Footer indicator during first visit: "⬇ Preparing offline access (X% complete)"
- Fades away once download completes
- Network status badge: "🟢 Online" or "🔴 Offline"

**Update notifications:**
- Subtle banner when new books available: "📚 New books available. [Refresh]"
- Dismissible, doesn't block search
- Shows once per update

**Search behavior:**
- Works identically—users don't need to change anything
- Offline capability is transparent and automatic

## Implementation Details

### Files to Create/Modify

**New files:**
- `src/service-worker.js` (200-300 lines) - Caching and update logic
- `public/data/version.json` (50 bytes) - Generated during sync

**Modified files:**
- `src/main.js` - Register Service Worker, handle status UI updates
- `src/styles.css` - 5-10 lines for status indicators
- `sync/sync.py` - Generate `version.json` after embeddings

**No changes needed:**
- `src/search.js` - Already completely offline-capable

### Version.json Generation

Add to `sync/sync.py` after embeddings.json is created:

```python
import json
import time
import hashlib

# Generate version file for update detection
with open('public/data/embeddings.json', 'rb') as f:
  checksum = hashlib.md5(f.read()).hexdigest()

version_data = {
  'timestamp': int(time.time()),
  'checksum': checksum
}

with open('public/data/version.json', 'w') as f:
  json.dump(version_data, f)

print(f"Generated version.json (checksum: {checksum})")
```

### Service Worker Responsibilities

1. **Install event** - Precache critical assets (HTML, CSS, JS)
2. **Fetch event** - Serve from cache with network fallback
3. **Background update** - Detect and download new embeddings
4. **Cache cleanup** - Remove old cache versions on update

### Error Handling

**Partial downloads:** Service Worker uses range requests to resume mid-download on next visit

**Corrupted cache:** Detect via checksum mismatch, purge and re-download automatically

**Storage full:** Browser handles eviction; user gets warning if offline mode unavailable

**Unsupported browsers:** Graceful degradation—search works online, Service Worker ignored

**Network interruption:** Shows user-friendly message while waiting for connection

## Testing Checklist

- [ ] First visit: Downloads everything, search works offline after
- [ ] Return visit (offline): Search works from cache
- [ ] Return visit (online): Detects new version, downloads quietly
- [ ] Update detection: "New books available" banner shows
- [ ] Network interruption mid-download: Resumes on next visit
- [ ] Clear cache: Resets and re-downloads everything
- [ ] Mobile/low bandwidth: Works but takes longer
- [ ] Storage pressure: Browser handles gracefully

## Storage Requirements

- **Initial cache:** ~342MB (model + embeddings + metadata)
- **Browser limit:** 500MB-2GB per origin (typically 50% of available disk)
- **Fits on:** All modern devices (phones, tablets, desktops)
- **User control:** Can clear cache anytime via browser settings

## Success Criteria

✅ Users can search their entire collection without internet after first visit
✅ Updates detected automatically and applied transparently
✅ No changes to existing search UI or behavior
✅ Works on mobile and desktop
✅ Graceful degradation on unsupported browsers

## Future Enhancements

1. **Selective offline:** Users choose which books to cache (useful if more books added over time)
2. **Compression:** Binary format for embeddings to reduce ~50% storage
3. **Incremental sync:** Only re-cache changed embeddings (faster updates)
4. **Bandwidth indicator:** Show estimated download time before caching starts
