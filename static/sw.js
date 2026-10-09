// Service Worker - Jutia PWA
const CACHE = "jutia-v1";
const ASSETS = [
  "/",
  "/shop",
  "/games",
  "/cart",
  "/static/style.css",
  "/static/app.js",
  "/static/manifest.json"
];

self.addEventListener("install", e => {
  e.waitUntil(
    caches.open(CACHE).then(c => 
      Promise.allSettled(ASSETS.map(a => c.add(a).catch(()=>null)))
    )
  );
  self.skipWaiting();
});

self.addEventListener("activate", e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", e => {
  const url = new URL(e.request.url);
  
  // API: network first
  if (url.pathname.startsWith("/api/")) {
    e.respondWith(
      fetch(e.request).catch(() => caches.match(e.request))
    );
    return;
  }
  
  // Everything else: cache first
  e.respondWith(
    caches.match(e.request).then(r => r || fetch(e.request).catch(() => caches.match("/")))
  );
});
