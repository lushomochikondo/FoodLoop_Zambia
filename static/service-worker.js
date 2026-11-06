const CACHE = 'foodloop-public-v5';
const OFFLINE = '/static/offline.html';
// Only non-personal, bundled app assets. Never cache account pages, API responses or food photos.
const ASSETS = [OFFLINE, '/static/fonts/Inter.woff2', '/static/icons/icon-192.png', '/static/icons/icon-512.png'];
self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(ASSETS)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => key.startsWith('foodloop-public-') && key !== CACHE).map(key => caches.delete(key)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin || event.request.method !== 'GET') return;
  if (event.request.mode === 'navigate') {
    event.respondWith(fetch(event.request).catch(() => caches.match(OFFLINE)));
  } else if (ASSETS.includes(url.pathname)) {
    event.respondWith(caches.match(event.request).then(cached => cached || fetch(event.request)));
  }
});

self.addEventListener('push', event => {
  let data={};
  try { data=event.data ? event.data.json() : {}; } catch (_) { data={body:event.data?.text()||'You have a new update.'}; }
  const target=(typeof data.url==='string' && data.url.startsWith('/') && !data.url.startsWith('//')) ? data.url : '/notifications/';
  event.waitUntil(self.registration.showNotification(data.title||'FoodLoop Zambia',{body:data.body||'You have a new update.',icon:'/static/icons/icon-192.png',badge:'/static/icons/icon-192.png',tag:'foodloop-update',data:{url:target}}));
});
self.addEventListener('notificationclick', event => {
  event.notification.close();
  const target=new URL(event.notification.data?.url||'/notifications/',self.location.origin).href;
  event.waitUntil(clients.matchAll({type:'window',includeUncontrolled:true}).then(list=>{for(const client of list){if(new URL(client.url).origin===self.location.origin)return client.navigate(target).then(()=>client.focus());}return clients.openWindow(target);}));
});
