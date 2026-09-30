import fs from 'node:fs'
import path from 'node:path'

const { getAudioUrl, getFallbackUrl } = await import('../src/config.js')
const VOICES = path.join(process.cwd(), 'public', 'data', 'voices')
const H = { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36' }

const pairs = []
for (const file of fs.readdirSync(VOICES)) {
  const shard = JSON.parse(fs.readFileSync(path.join(VOICES, file), 'utf8'))
  for (const categories of Object.values(shard)) {
    for (const entries of Object.values(categories)) {
      for (const entry of entries) {
        if (entry?.url?.startsWith('bwiki:') && entry.alt) pairs.push(entry)
      }
    }
  }
}
// deterministic spread across the corpus
const step = Math.floor(pairs.length / 40) || 1
const sample = Array.from({ length: 40 }, (_, i) => pairs[i * step])

async function probe(url) {
  const started = Date.now()
  try {
    const res = await fetch(url, { headers: H, signal: AbortSignal.timeout(60000) })
    const buf = Buffer.from(await res.arrayBuffer())
    const total = Date.now() - started
    return {
      ok: res.ok && buf.length > 512, status: res.status, bytes: buf.length, total,
      kbps: total ? (buf.length * 8) / total / 1000 : 0,
      server: res.headers.get('server'), cdn: res.headers.get('via') || res.headers.get('x-swift-cachetime') || res.headers.get('x-cache') || res.headers.get('timing-allow-origin'),
    }
  } catch (error) {
    return { ok: false, status: 0, bytes: 0, total: Date.now() - started, err: error.message }
  }
}

const sum = list => ({
  ok: list.filter(r => r.ok).length,
  fail: list.filter(r => !r.ok).length,
  med: Math.round(list.map(r => r.total).sort((a, b) => a - b)[Math.floor(list.length / 2)]),
  p90: Math.round(list.map(r => r.total).sort((a, b) => a - b)[Math.floor(list.length * 0.9)]),
  max: Math.max(...list.map(r => r.total)),
  mb: (list.reduce((n, r) => n + r.bytes, 0) / 1024 / 1024).toFixed(1),
})

for (const side of ['bwiki', 'prts']) {
  const results = []
  for (const entry of sample) {
    const url = side === 'bwiki' ? getAudioUrl(entry.url) : getFallbackUrl(entry)
    const r = await probe(url)
    results.push({ ...r, server: r.server, cdn: r.cdn })
    await new Promise(resolve => setTimeout(resolve, 120))
  }
  const s = sum(results)
  console.log(`${side}: 成功 ${s.ok}/40 失败 ${s.fail}  中位 ${s.med}ms  p90 ${s.p90}ms  最慢 ${s.max}ms  共 ${s.mb}MB`)
  const heads = results.filter(r => r.ok).slice(0, 3).map(r => `  server=${r.server} cdn=${r.cdn}`)
  console.log(heads.join('\n'))
}
