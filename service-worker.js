// accountRADAR - minimale service worker
// Cachet alleen de app-schil (index.html zelf) zodat de tool ook zonder
// internet opnieuw opent. Live data (Excel-inlezen, PDOK-geocoding,
// Google-prospecting) blijft uiteraard een internetverbinding vereisen.
const CACHE_NAME = 'accountradar-shell-v1';
const APP_SHELL = ['./', './index.html', './manifest.json', './icon-192.png', './icon-512.png'];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL)).catch(()=>{})
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  // alleen navigatie-verzoeken (het openen van de app zelf) uit cache serveren;
  // alles overig (API's, kaarttegels) gaat gewoon rechtstreeks over internet.
  if (event.request.mode === 'navigate') {
    event.respondWith(
      fetch(event.request).catch(() => caches.match('./index.html'))
    );
  }
});
