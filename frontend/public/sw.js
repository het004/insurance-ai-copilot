/* Insurance AI Copilot — service worker (PWA install + offline shell).
   Strategy: network-first for pages, cache-first for static assets, never cache /api. */
const CACHE = "copilot-v1";
const SHELL = ["/", "/chat", "/offline.html", "/icons/icon-192.png"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  const url = new URL(req.url);
  if (req.method !== "GET" || url.origin !== location.origin || url.pathname.startsWith("/api/")) return;

  if (req.mode === "navigate") {
    e.respondWith(
      fetch(req)
        .then((res) => {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(req, copy));
          return res;
        })
        .catch(() => caches.match(req).then((r) => r || caches.match("/offline.html"))),
    );
    return;
  }

  if (url.pathname.startsWith("/_next/static/") || url.pathname.startsWith("/icons/")) {
    e.respondWith(
      caches.match(req).then((hit) => hit || fetch(req).then((res) => {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(req, copy));
        return res;
      })),
    );
  }
});
