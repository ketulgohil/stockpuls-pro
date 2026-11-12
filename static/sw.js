// Self-destructing service worker.
//
// Earlier versions of this app registered a cache-first service worker under
// the fixed cache name "stockpulse-v5". That meant browsers kept serving an
// old index.html / app.js forever, so live-price UI fixes never appeared.
//
// This worker removes every cache, unregisters itself, and reloads open tabs
// so they load fresh files straight from the server. The app no longer
// registers a service worker.

self.addEventListener('install', () => {
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    event.waitUntil((async () => {
        try {
            const keys = await caches.keys();
            await Promise.all(keys.map((key) => caches.delete(key)));
        } catch (err) {
            // Ignore cache cleanup failures.
        }

        try {
            await self.registration.unregister();
        } catch (err) {
            // Ignore unregister failures.
        }

        try {
            const clients = await self.clients.matchAll({ type: 'window' });
            clients.forEach((client) => {
                try {
                    client.navigate(client.url);
                } catch (err) {
                    // Ignore navigation failures.
                }
            });
        } catch (err) {
            // Ignore client enumeration failures.
        }
    })());
});

// Pass everything straight to the network while this worker is still alive.
self.addEventListener('fetch', () => {});
