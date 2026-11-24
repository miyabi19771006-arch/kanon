/* kanon — 圏外でも開けるようにするための仕組み
   バージョンを変えると、古い保存ぶんを捨てて入れ直します。
   ※ ここが預かるのは「アプリ本体」だけです。記録は端末の中にあり、ここには入りません。 */
const V = 'kanon-2026-11-24-6';
const CORE = [
  './',
  './index.html',
  './manifest.webmanifest',
  './icon-192.png',
  './icon-512.png',
  './apple-touch-icon.png'
];

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(V)
      .then(c => c.addAll(CORE))
      .then(() => self.skipWaiting())
      .catch(() => self.skipWaiting())
  );
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(ks => Promise.all(ks.filter(k => k !== V).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

// まず手元のぶんを返して画面を出し、裏で新しいものを取ってくる
self.addEventListener('fetch', e => {
  const r = e.request;
  if (r.method !== 'GET') return;
  if (new URL(r.url).origin !== self.location.origin) return;
  e.respondWith((async () => {
    const c = await caches.open(V);
    const hit = await c.match(r, { ignoreSearch: true });
    const net = fetch(r).then(res => {
      if (res && res.ok && res.type === 'basic') c.put(r, res.clone());
      return res;
    }).catch(() => null);
    if (hit) { e.waitUntil(net); return hit; }
    const res = await net;
    return res || new Response('offline', { status: 503, statusText: 'offline' });
  })());
});
