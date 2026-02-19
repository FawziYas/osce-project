/**
 * OSCE Examiner - Service Worker
 * 
 * Provides offline-first functionality for tablet-based marking.
 * 
 * Strategy:
 * - Cache static assets (CSS, JS, icons) on install
 * - Cache API responses for exam data
 * - Serve from cache when offline
 * - Sync data when back online
 */

const CACHE_VERSION = 'osce-examiner-v2';
const STATIC_CACHE = `${CACHE_VERSION}-static`;
const DATA_CACHE = `${CACHE_VERSION}-data`;

// Static assets to cache on install
const STATIC_ASSETS = [
    '/examiner/',
    '/examiner/login',
    '/examiner/static/css/examiner.css',
    '/examiner/static/js/examiner.js',
    '/examiner/static/icons/icon-192.png',
    '/examiner/static/icons/icon-512.png',
    // Bootstrap from CDN - optional, may fail offline
    'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css',
    'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js',
    'https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.0/font/bootstrap-icons.css'
];

// API routes to cache
const API_ROUTES = [
    '/examiner/api/stations',
    '/examiner/api/session'
];

// ==========================================================================
// Install Event
// ==========================================================================

self.addEventListener('install', (event) => {
    console.log('Service Worker: Installing...');
    
    event.waitUntil(
        caches.open(STATIC_CACHE)
            .then(cache => {
                console.log('Service Worker: Caching static assets');
                return cache.addAll(STATIC_ASSETS.map(url => {
                    return new Request(url, { mode: 'cors' });
                })).catch(err => {
                    console.warn('Some static assets failed to cache:', err);
                    // Don't fail installation if CDN assets fail
                });
            })
            .then(() => {
                console.log('Service Worker: Installed');
                return self.skipWaiting();
            })
    );
});

// ==========================================================================
// Activate Event
// ==========================================================================

self.addEventListener('activate', (event) => {
    console.log('Service Worker: Activating...');
    
    event.waitUntil(
        caches.keys()
            .then(cacheNames => {
                return Promise.all(
                    cacheNames
                        .filter(cacheName => {
                            // Delete old caches
                            return cacheName.startsWith('osce-examiner-') && 
                                   cacheName !== STATIC_CACHE && 
                                   cacheName !== DATA_CACHE;
                        })
                        .map(cacheName => {
                            console.log('Service Worker: Deleting old cache:', cacheName);
                            return caches.delete(cacheName);
                        })
                );
            })
            .then(() => {
                console.log('Service Worker: Activated');
                return self.clients.claim();
            })
    );
});

// ==========================================================================
// Fetch Event
// ==========================================================================

self.addEventListener('fetch', (event) => {
    const url = new URL(event.request.url);
    
    // Only handle same-origin requests or known CDN assets
    if (!url.origin.includes(self.location.origin) && 
        !url.origin.includes('cdn.jsdelivr.net')) {
        return;
    }
    
    // Handle API requests
    if (url.pathname.startsWith('/examiner/api/')) {
        event.respondWith(handleApiRequest(event.request));
        return;
    }
    
    // Handle static assets and pages
    event.respondWith(handleStaticRequest(event.request));
});

// ==========================================================================
// Request Handlers
// ==========================================================================

async function handleStaticRequest(request) {
    // Try cache first
    const cachedResponse = await caches.match(request);
    if (cachedResponse) {
        return cachedResponse;
    }
    
    // Try network
    try {
        const networkResponse = await fetch(request);
        
        // Cache successful responses
        if (networkResponse.ok) {
            const cache = await caches.open(STATIC_CACHE);
            cache.put(request, networkResponse.clone());
        }
        
        return networkResponse;
    } catch (error) {
        console.log('Service Worker: Network failed, serving offline page');
        
        // If it's a navigation request, show offline page
        if (request.mode === 'navigate') {
            return caches.match('/examiner/offline');
        }
        
        throw error;
    }
}

async function handleApiRequest(request) {
    const url = new URL(request.url);
    
    // For GET requests, try network first, fall back to cache
    if (request.method === 'GET') {
        try {
            const networkResponse = await fetch(request);
            
            if (networkResponse.ok) {
                // Cache the response
                const cache = await caches.open(DATA_CACHE);
                cache.put(request, networkResponse.clone());
            }
            
            return networkResponse;
        } catch (error) {
            // Network failed, try cache
            const cachedResponse = await caches.match(request);
            if (cachedResponse) {
                return cachedResponse;
            }
            
            // Return offline error
            return new Response(JSON.stringify({
                error: 'offline',
                message: 'You are offline and no cached data is available'
            }), {
                status: 503,
                headers: { 'Content-Type': 'application/json' }
            });
        }
    }
    
    // For POST requests (scoring), try network, queue if offline
    if (request.method === 'POST') {
        try {
            return await fetch(request);
        } catch (error) {
            // Store in IndexedDB via the client
            // The main JS will handle queuing
            return new Response(JSON.stringify({
                queued: true,
                message: 'Score saved offline, will sync when online'
            }), {
                status: 202,
                headers: { 'Content-Type': 'application/json' }
            });
        }
    }
    
    // Default: pass through
    return fetch(request);
}

// ==========================================================================
// Background Sync
// ==========================================================================

self.addEventListener('sync', (event) => {
    console.log('Service Worker: Background sync triggered');
    
    if (event.tag === 'sync-scores') {
        event.waitUntil(syncScores());
    }
});

async function syncScores() {
    // Notify all clients to sync their IndexedDB data
    const clients = await self.clients.matchAll();
    clients.forEach(client => {
        client.postMessage({
            type: 'SYNC_REQUEST',
            timestamp: Date.now()
        });
    });
}

// ==========================================================================
// Push Notifications (future feature)
// ==========================================================================

self.addEventListener('push', (event) => {
    if (!event.data) return;
    
    const data = event.data.json();
    
    const options = {
        body: data.body || 'New OSCE notification',
        icon: '/examiner/static/icons/icon-192.png',
        badge: '/examiner/static/icons/badge-72.png',
        vibrate: [200, 100, 200],
        data: data.data || {}
    };
    
    event.waitUntil(
        self.registration.showNotification(data.title || 'OSCE Examiner', options)
    );
});

self.addEventListener('notificationclick', (event) => {
    event.notification.close();
    
    // Navigate to the relevant page
    const data = event.notification.data;
    const url = data.url || '/examiner/';
    
    event.waitUntil(
        clients.matchAll({ type: 'window' })
            .then(windowClients => {
                // Focus existing window or open new
                for (const client of windowClients) {
                    if (client.url === url && 'focus' in client) {
                        return client.focus();
                    }
                }
                return clients.openWindow(url);
            })
    );
});

// ==========================================================================
// Message Handler
// ==========================================================================

self.addEventListener('message', (event) => {
    if (event.data.type === 'SKIP_WAITING') {
        self.skipWaiting();
    }
    
    if (event.data.type === 'CACHE_EXAM_DATA') {
        // Cache specific exam data for offline use
        cacheExamData(event.data.examId);
    }
});

async function cacheExamData(examId) {
    const cache = await caches.open(DATA_CACHE);
    
    // Cache exam-specific endpoints
    const urls = [
        `/examiner/api/exam/${examId}`,
        `/examiner/api/exam/${examId}/stations`,
        `/examiner/api/exam/${examId}/students`
    ];
    
    for (const url of urls) {
        try {
            const response = await fetch(url);
            if (response.ok) {
                cache.put(url, response);
            }
        } catch (error) {
            console.warn(`Failed to cache ${url}:`, error);
        }
    }
}

console.log('OSCE Examiner Service Worker loaded');
