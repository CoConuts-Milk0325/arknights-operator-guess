// Proxy audio on cache misses; cache only complete successful responses.
const CORS_HEADERS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, HEAD, OPTIONS',
  'Access-Control-Allow-Headers': 'Range, Content-Type',
  'Access-Control-Expose-Headers': 'Content-Length, Content-Range, Accept-Ranges',
};

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    if (request.method === 'OPTIONS') return new Response(null, { status: 204, headers: CORS_HEADERS });
    if (!['GET', 'HEAD'].includes(request.method)) return new Response('Method Not Allowed', { status: 405, headers: CORS_HEADERS });
    if (!url.pathname.startsWith('/audio/')) return new Response('Not Found', { status: 404, headers: CORS_HEADERS });
    const cleanUrl = new URL(url);
    cleanUrl.search = '';
    const cache = caches.default;
    const cacheKey = new Request(cleanUrl, { method: 'GET' });
    const range = request.headers.get('Range');
    const cached = range ? null : await cache.match(cacheKey);
    if (cached) {
      const headers = new Headers(cached.headers);
      for (const [key, value] of Object.entries(CORS_HEADERS)) headers.set(key, value);
      return new Response(request.method === 'HEAD' ? null : cached.body, { status: cached.status, headers });
    }
    const targetUrl = `https://torappu.prts.wiki/assets/audio/${url.pathname.slice('/audio/'.length)}`;
    try {
      const headers = { 'User-Agent': 'Mozilla/5.0' };
      if (range) headers.Range = range;
      const upstream = await fetch(targetUrl, { method: request.method, headers });
      const responseHeaders = new Headers(CORS_HEADERS);
      for (const key of ['Content-Type', 'Content-Length', 'Content-Range', 'Accept-Ranges', 'ETag', 'Last-Modified']) {
        const value = upstream.headers.get(key);
        if (value) responseHeaders.set(key, value);
      }
      responseHeaders.set('Cache-Control', upstream.ok ? 'public, max-age=604800' : 'no-store');
      const response = new Response(request.method === 'HEAD' ? null : upstream.body, { status: upstream.status, headers: responseHeaders });
      if (request.method === 'GET' && upstream.status === 200 && !range) {
        ctx.waitUntil(cache.put(cacheKey, response.clone()).catch(error => console.error('Audio cache write failed', error)));
      }
      return response;
    } catch {
      return new Response('Bad Gateway', { status: 502, headers: { ...CORS_HEADERS, 'Cache-Control': 'no-store' } });
    }
  },
};
