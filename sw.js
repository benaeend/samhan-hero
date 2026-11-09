/* 삼한 용사 키우기 — 오프라인 도우미(서비스 워커)
   인터넷이 되면 언제나 새 파일을 받아 쓰고(그래서 업데이트가 바로 반영됨), 안 되면 마지막으로 받아 둔 파일을 쓴다.
   이 파일의 동작을 바꿨을 때만 CACHE 이름의 숫자를 올린다. index.html만 바뀐 경우엔 그대로 둔다. */
const CACHE = 'samhan-v2';
const CORE = ['./', './index.html', './manifest.webmanifest', './icons/icon-192.png', './icons/icon-512.png', './icons/icon-maskable-512.png'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(CORE)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys()
    .then(keys => Promise.all(keys.filter(k => k.startsWith('samhan-') && k !== CACHE).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});
self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET' || new URL(req.url).origin !== self.location.origin) return;
  e.respondWith(
    fetch(req).then(res => {
      if (res.ok && res.type === 'basic'){
        const copy = res.clone();
        const key = req.mode === 'navigate' ? './index.html' : req;
        caches.open(CACHE).then(c => c.put(key, copy));
      }
      return res;
    }).catch(() => caches.match(req, {ignoreSearch:true})
      .then(r => r || (req.mode === 'navigate' ? caches.match('./index.html') : undefined))
      .then(r => r || new Response('', {status:504, statusText:'offline'})))
  );
});
