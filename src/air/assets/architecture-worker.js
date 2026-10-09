'use strict';
// Generated exact resource set. Never discover or cache arbitrary URLs.
const resources = __AIR_RESOURCE_LIST__;
const version = __AIR_VERSION__;
const scope = new URL(self.registration.scope);
const prefix = 'air-site:' + encodeURIComponent(scope.pathname) + ':';
const cacheName = prefix + version;
const urls = new Set(resources.map(item => new URL(item.path, scope).href));

self.addEventListener('install', event => event.waitUntil((async () => {
  // Each generation has a separate cache. A partial copy never becomes active.
  await caches.delete(cacheName);
  const cache = await caches.open(cacheName);
  try {
    for (let i = 0; i < resources.length; i += 8) {
      const outcomes = await Promise.allSettled(resources.slice(i, i + 8).map(async item => {
        const url = new URL(item.path, scope);
        const response = await fetch(url, {cache:'no-store', credentials:'omit', redirect:'error'});
        if (!response.ok || response.type === 'opaque') throw new Error('Resource unavailable');
        const bytes = await response.clone().arrayBuffer();
        const hash = 'sha256:' + [...new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))]
          .map(x => x.toString(16).padStart(2, '0')).join('');
        if (hash !== item.digest) throw new Error('Resource changed');
        await cache.put(url, response);
      }));
      if (outcomes.some(item => item.status === 'rejected')) throw new Error('Resource unavailable or changed');
    }
  } catch (error) {
    await caches.delete(cacheName);
    throw error;
  }
})()));
self.addEventListener('activate', event => event.waitUntil((async () => {
  await self.clients.claim();
  for (const name of await caches.keys()) {
    if (name.startsWith(prefix) && name !== cacheName) await caches.delete(name);
  }
})()));
self.addEventListener('message', event => {
  if (event.data === 'AIR_APPLY_VERSION') self.skipWaiting();
});
self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;
  const url = new URL(event.request.url);
  if (url.origin !== scope.origin) return;
  if (url.search) {
    // Only the inert question preselection varies client-side. The page bytes
    // stay pinned; never apply this alias to APIs, other pages or unknown keys.
    if (!url.pathname.endsWith('/cooperate.html') ||
        [...url.searchParams.keys()].some(key => !['topic', 'audience'].includes(key))) return;
    url.search = '';
  }
  // Scope root is an alias of the immutable entry point.
  const target = url.href === scope.href ? new URL('index.html', scope).href : url.href;
  if (!urls.has(target)) return;
  event.respondWith((async () => {
    const cached = await (await caches.open(cacheName)).match(target);
    // Never mix an uncached newer page with this generation's assets.
    return cached || new Response('Copie hors ligne incomplète. Effacez-la puis conservez de nouveau le site.',
      {status:503, headers:{'Content-Type':'text/plain; charset=utf-8'}});
  })());
});
