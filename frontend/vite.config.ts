import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react(), {
    name: 'saeng-offline-shell',
    transformIndexHtml() { return [{ tag: 'link', attrs: { rel: 'manifest', href: '/manifest.webmanifest' }, injectTo: 'head' }]; },
    generateBundle(_, bundle) {
      const files = ['/', '/kun-icon-v2-64.png', '/kun-icon-v2-192.png', '/kun-icon-v2-512.png', '/kun-icon-v2-maskable-512.png', '/kun-global-logo-v2.png', '/kun-global-services-banner-v2.png', '/kun-global-pattern.svg', '/images/kun-global-concierge.webp', '/images/kun-global-documents.webp', '/images/kun-global-contact.webp', '/manifest.webmanifest', ...Object.keys(bundle).map(file => `/${file}`)];
      const version = Object.keys(bundle).join('|');
      this.emitFile({ type: 'asset', fileName: 'sw.js', source: `
const CACHE = 'saeng-' + ${JSON.stringify(version)};
const FILES = ${JSON.stringify(files)};
self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(FILES)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => key.startsWith('saeng-') && key !== CACHE).map(key => caches.delete(key)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  if (event.request.method !== 'GET' || url.origin !== self.location.origin || url.pathname.startsWith('/api/')) return;
  if (event.request.mode === 'navigate') {
    event.respondWith(fetch(event.request).catch(() => caches.open(CACHE).then(cache => cache.match('/'))));
  } else if (FILES.includes(url.pathname)) {
    event.respondWith(caches.open(CACHE).then(cache => cache.match(url.pathname)).then(cached => cached || fetch(event.request)));
  }
});
` });
    }
  }],
  server: { proxy: { '/api': 'http://127.0.0.1:8000' } }
});
