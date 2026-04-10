// Minimal Service Worker to satisfy Chrome's PWA URL-Bar requirements
self.addEventListener('install', (e) => {
    self.skipWaiting();
});

self.addEventListener('activate', (e) => {
    e.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', (e) => {
    // Allows the app to work normally
    e.respondWith(fetch(e.request).catch(() => new Response("Offline")));
});
