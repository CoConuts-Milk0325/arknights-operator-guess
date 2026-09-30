import http from 'node:http';
import https from 'node:https';
import fs from 'node:fs';
import path from 'node:path';
import zlib from 'node:zlib';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const PORT = 5173;
const DIST = path.join(__dirname, 'dist');
const CACHE_DIR = path.join(__dirname, '.audio-cache');

// Create cache directory
if (!fs.existsSync(CACHE_DIR)) {
  fs.mkdirSync(CACHE_DIR, { recursive: true });
}

// MIME types
const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.ico': 'image/x-icon',
  '.wav': 'audio/wav',
  '.mp3': 'audio/mpeg',
  '.ogg': 'audio/ogg'
};

// Audio memory cache (cap entries to avoid unbounded memory growth)
const audioCache = new Map();
const AUDIO_CACHE_MAX = 200;

function cacheAudio(key, value) {
  if (audioCache.size >= AUDIO_CACHE_MAX && !audioCache.has(key)) {
    const oldestKey = audioCache.keys().next().value;
    audioCache.delete(oldestKey);
  }
  audioCache.set(key, value);
}

// Check if client accepts gzip
function acceptsGzip(req) {
  const accept = req.headers['accept-encoding'] || '';
  return accept.includes('gzip');
}

// Compress data with gzip
function gzipCompress(data) {
  return new Promise((resolve, reject) => {
    zlib.gzip(data, { level: 6 }, (err, result) => {
      if (err) reject(err);
      else resolve(result);
    });
  });
}

// Serve static file with gzip and caching
async function serveStatic(req, res) {
  let pathname;
  try {
    pathname = decodeURIComponent(req.url.split('?')[0]);
  } catch {
    res.writeHead(400);
    res.end('Bad Request');
    return;
  }
  let filePath = path.resolve(DIST, pathname === '/' ? 'index.html' : pathname.replace(/^[/\\]+/, ''));
  const relative = path.relative(DIST, filePath);
  if (relative === '..' || relative.startsWith(`..${path.sep}`) || path.isAbsolute(relative)) {
    res.writeHead(403);
    res.end('Forbidden');
    return;
  }

  if (!fs.existsSync(filePath) || fs.statSync(filePath).isDirectory()) {
    filePath = path.join(DIST, 'index.html');
  }

  const ext = path.extname(filePath);
  const contentType = MIME[ext] || 'application/octet-stream';

  try {
    const data = fs.readFileSync(filePath);
    const canGzip = acceptsGzip(req) && data.length > 1024; // Only gzip files > 1KB

    const headers = {
      'Content-Type': contentType,
      'Access-Control-Allow-Origin': '*',
    };

    if (ext === '.html') {
      headers['Cache-Control'] = 'no-cache';
    } else if (ext === '.json') {
      // JSON files: no-cache to avoid serving stale data during development/updates
      headers['Cache-Control'] = 'no-cache';
    } else {
      // JS, CSS, images: cache for 7 days
      headers['Cache-Control'] = 'public, max-age=604800, immutable';
    }

    if (canGzip) {
      const compressed = await gzipCompress(data);
      headers['Content-Encoding'] = 'gzip';
      headers['Content-Length'] = compressed.length;
      res.writeHead(200, headers);
      res.end(compressed);
    } else {
      headers['Content-Length'] = data.length;
      res.writeHead(200, headers);
      res.end(data);
    }
  } catch (err) {
    res.writeHead(404);
    res.end('Not Found');
  }
}

// Proxy audio requests with caching
async function proxyAudio(req, res) {
  const urlPath = req.url;

  // Check memory cache
  if (audioCache.has(urlPath)) {
    const cached = audioCache.get(urlPath);
    res.writeHead(200, {
      'Content-Type': cached.contentType,
      'Cache-Control': 'public, max-age=604800',
      'Access-Control-Allow-Origin': '*',
      'Content-Length': cached.data.length
    });
    res.end(cached.data);
    return;
  }

  // Check disk cache
  const cacheFile = path.join(CACHE_DIR, Buffer.from(urlPath).toString('base64').replace(/\//g, '_'));
  if (fs.existsSync(cacheFile)) {
    const data = fs.readFileSync(cacheFile);
    const contentType = MIME[path.extname(urlPath)] || 'audio/wav';
    cacheAudio(urlPath, { data, contentType });
    res.writeHead(200, {
      'Content-Type': contentType,
      'Cache-Control': 'public, max-age=604800',
      'Access-Control-Allow-Origin': '*',
      'Content-Length': data.length
    });
    res.end(data);
    return;
  }

  // Fetch from CDN
  const cdnUrl = `https://torappu.prts.wiki/assets/audio${urlPath.replace(/^\/audio/, '')}`;

  https.get(cdnUrl, {
    headers: { 'User-Agent': 'Mozilla/5.0' }
  }, (proxyRes) => {
    if (proxyRes.statusCode !== 200) {
      res.writeHead(proxyRes.statusCode);
      res.end();
      return;
    }

    const chunks = [];
    proxyRes.on('data', chunk => chunks.push(chunk));
    proxyRes.on('end', () => {
      const data = Buffer.concat(chunks);
      const contentType = proxyRes.headers['content-type'] || 'audio/wav';

      // Cache
      cacheAudio(urlPath, { data, contentType });
      fs.writeFileSync(cacheFile, data);

      res.writeHead(200, {
        'Content-Type': contentType,
        'Cache-Control': 'public, max-age=604800',
        'Access-Control-Allow-Origin': '*',
        'Content-Length': data.length
      });
      res.end(data);
    });
  }).on('error', (err) => {
    console.error('Proxy error:', err.message);
    res.writeHead(502);
    res.end('Bad Gateway');
  });
}

// Main server
function startServer(port) {
  const server = http.createServer(async (req, res) => {
    // CORS preflight
    if (req.method === 'OPTIONS') {
      res.writeHead(204, {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type'
      });
      res.end();
      return;
    }

    // Audio proxy
    if (req.url.startsWith('/audio/')) {
      await proxyAudio(req, res);
      return;
    }

    // Static files with gzip
    await serveStatic(req, res);
  });

  server.on('error', (e) => {
    if (e.code === 'EADDRINUSE') {
      console.log(`Port ${port} in use, trying ${port + 1}...`);
      startServer(port + 1);
    } else {
      console.error(e);
    }
  });

  server.listen(port, '127.0.0.1', () => {
    console.log(`Server: http://localhost:${port}`);
    console.log('Gzip compression: enabled');
    console.log('JSON cache: 1 hour');
    console.log('Static cache: 7 days');
  });
}

startServer(PORT);
