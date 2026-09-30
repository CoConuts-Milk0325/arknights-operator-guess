import fs from 'node:fs'
import path from 'node:path'
import crypto from 'node:crypto'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT = path.join(__dirname, '..')
const CACHE_DIR = path.join(ROOT, '.bwiki-cache')
const PAGE_DIR = path.join(CACHE_DIR, 'pages')
const OUT_FILE = path.join(CACHE_DIR, 'bwiki-voices.json')
const OPERATORS_FILE = path.join(ROOT, 'public', 'data', 'operators.json')

const WIKI = 'https://wiki.biligame.com/arknights'
const LANGS = ['日', '中', '韩', '英', '方', '联']

const HEADERS = {
  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36',
  accept: 'application/json,*/*',
  'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8',
  'sec-ch-ua': '"Chromium";v="141", "Not:A-Brand";v="";v="99"',
  'sec-ch-ua-mobile': '?0',
  'sec-ch-ua-platform': '"Windows"',
  'sec-fetch-dest': 'empty',
  'sec-fetch-mode': 'cors',
  'sec-fetch-site': 'same-origin',
  referer: `${WIKI}/index.php`,
}

const args = process.argv.slice(2)
const flag = name => {
  const i = args.indexOf(name)
  return i < 0 ? null : args[i + 1]
}
const LIMIT = Number(flag('--limit') || 0)
const ONLY = flag('--only') ? flag('--only').split(',') : null
const REFETCH = flag('--refetch') ? flag('--refetch').split(',') : []
const THROTTLE = Number(flag('--throttle') || 1500)

const sleep = ms => new Promise(r => setTimeout(r, ms))
const slug = title => crypto.createHash('sha1').update(title).digest('hex').slice(0, 16)

async function request(url) {
  for (let attempt = 0; attempt < 4; attempt++) {
    try {
      const res = await fetch(url, { headers: HEADERS, signal: AbortSignal.timeout(25000) })
      if (res.status === 200) return JSON.parse(await res.text())
      if (res.status !== 567) throw new Error(`HTTP ${res.status}`)
    } catch (error) {
      if (attempt === 3) throw error
    }
    const wait = [10000, 30000, 60000][attempt]
    console.log(`  retry in ${wait / 1000}s`)
    await sleep(wait)
  }
}

async function listVoicePages() {
  const url = `${WIKI}/api.php?action=query&list=search&srlimit=500&format=json&formatversion=2&srsearch=${encodeURIComponent('intitle:中文-普通话')}`
  const json = await request(url)
  return json.query.search.map(entry => entry.title).filter(title => title !== '声优一览/中文-普通话').sort()
}

function unescape(html) {
  return html.split(String.fromCharCode(92) + '"').join('"').replace(/&#58;/g, ':').replace(/&quot;/g, '"')
}

function parsePage(title, text) {
  const html = unescape(text)
  const marker = /<div class="operator-page-label-cell flex-container center-on-y-axis" style="width: auto;">([^<]{1,16})<\/div>/g
  const marks = [...html.matchAll(marker)]
  const rows = marks.map((mark, index) => {
    const chunk = html.slice(mark.index + mark[0].length, marks[index + 1] ? marks[index + 1].index : undefined)
    const clips = {}
    for (const match of chunk.matchAll(/<div class="bikit-audio" data-src="([^"]*)"[^>]*><\/div>([^<]{0,4})/g)) {
      // 联动干员的音频在主页面，单列且没有语言标记
      const tag = (match[2].match(/[日中韩英方]/) || [])[0] || '联'
      if (clips[tag]) continue
      clips[tag] = match[1] || null
    }
    const start = chunk.indexOf('operator-page-value-cell')
    const body = start < 0 ? '' : chunk.slice(chunk.indexOf('>', start) + 1)
    return { label: mark[1].trim(), clips, text: body.replace(/<[^>]+>/g, '\n').split('\n').map(s => s.trim()).filter(Boolean).join('\n') }
  })
  const [, skin = '默认'] = title.split('/')
  return { title, skin, rows }
}

async function fetchPage(title) {
  const file = path.join(PAGE_DIR, `${slug(title)}.json`)
  // Cached pages predating the raw-count self-check are untrustworthy: a parser that silently
  // dropped whole columns used to be indistinguishable from a wiki page that had no audio.
  if (fs.existsSync(file)) {
    const cached = JSON.parse(fs.readFileSync(file, 'utf8'))
    if (cached.audioElements !== undefined && !REFETCH.includes(title)) return cached
  }
  const url = `${WIKI}/api.php?action=parse&format=json&formatversion=2&prop=text&page=${encodeURIComponent(title)}`
  const json = await request(url)
  if (!json.parse) throw new Error(json.error ? json.error.code : 'no parse payload')
  const raw = json.parse.text
  const parsed = parsePage(title, raw)
  parsed.audioElements = (raw.match(/bikit-audio/g) || []).length
  parsed.rawMp3 = (raw.match(/\.mp3/g) || []).length
  fs.writeFileSync(file, JSON.stringify(parsed))
  await sleep(THROTTLE + Math.random() * 500)
  return parsed
}

function relative(url) {
  if (!url) return null
  const marker = '/images/arknights/'
  const i = url.indexOf(marker)
  return i < 0 ? url : url.slice(i + marker.length)
}

async function main() {
  fs.mkdirSync(PAGE_DIR, { recursive: true })
  const names = JSON.parse(fs.readFileSync(OPERATORS_FILE, 'utf8')).map(op => op.干员)
  let titles = await listVoicePages()
  console.log(`voice pages: ${titles.length}`)

  const byName = new Map()
  for (const title of titles) {
    const name = title.split('/')[0]
    if (!byName.has(name)) byName.set(name, [])
    byName.get(name).push(title)
  }

  const wanted = []
  const orphanPages = []
  for (const name of names) {
    const wide = name.replace(/\(([^)]*)\)/g, '（$1）')
    const pages = byName.get(name) || byName.get(wide) || []
    if (!pages.length) orphanPages.push(name)
    wanted.push(...pages)
  }

  let queue = ONLY ? wanted.filter(t => ONLY.some(o => t.startsWith(o + '/'))) : wanted
  if (LIMIT) queue = queue.slice(0, LIMIT)
  console.log(`pages queued for dataset: ${queue.length}; operators without any page: ${orphanPages.length}`)
  if (orphanPages.length) console.log(`  unmatched: ${orphanPages.join(', ')}`)

  const result = {}
  const failures = []
  for (let i = 0; i < queue.length; i++) {
    const title = queue[i]
    const name = title.split('/')[0]
    try {
      const parsed = await fetchPage(title)
      const entry = (result[name] ||= {})[parsed.skin] = {}
      for (const row of parsed.rows) {
        const clip = {}
        for (const lang of LANGS) if (row.clips[lang]) clip[lang] = relative(row.clips[lang])
        entry[row.label] = { ...clip, text: row.text }
      }
      if ((i + 1) % 25 === 0 || i === queue.length - 1) console.log(`  ${i + 1}/${queue.length} ${title}`)
    } catch (error) {
      failures.push(`${title}: ${error.message}`)
      console.log(`  FAILED ${title}: ${error.message}`)
    }
  }

  const hasClip = skins => Object.values(skins).some(skin => Object.values(skin).some(row => LANGS.some(lang => row[lang])))
  const empty = Object.entries(result).filter(([, skins]) => !hasClip(skins)).map(([name]) => name)
  if (empty.length) {
    console.log(`\n语音子页整页空 src 的干员 ${empty.length} 个，改抓主页面单列`)
    for (const name of empty) {
      try {
        const parsed = await fetchPage(name)
        const entry = (result[name] ||= {})['主页面'] = {}
        for (const row of parsed.rows) {
          const clip = {}
          for (const lang of LANGS) if (row.clips[lang]) clip[lang] = relative(row.clips[lang])
          if (Object.keys(clip).length) entry[row.label] = { ...clip, text: row.text }
        }
        console.log(`  ${name}: ${Object.keys(entry).length} 行`)
      } catch (error) {
        failures.push(`${name} (主页面): ${error.message}`)
        console.log(`  FAILED ${name} 主页面: ${error.message}`)
      }
    }
  }

  fs.writeFileSync(OUT_FILE, JSON.stringify(result))
  const rows = Object.values(result).flatMap(bySkin => Object.values(bySkin).flatMap(skin => Object.values(skin)))
  const filled = {}
  for (const lang of LANGS) filled[lang] = rows.filter(row => row[lang]).length
  console.log(`\nwrote ${OUT_FILE}`)
  console.log(`skins: ${Object.values(result).reduce((n, bySkin) => n + Object.keys(bySkin).length, 0)}; rows: ${rows.length}; non-empty clips: ${JSON.stringify(filled)}`)
  // Self-check: a page whose raw HTML mentions more .mp3 links than we kept means the parser lost audio.
  const loss = []
  for (const cachedFile of fs.readdirSync(PAGE_DIR)) {
    const page = JSON.parse(fs.readFileSync(path.join(PAGE_DIR, cachedFile), 'utf8'))
    if (page.rawMp3 === undefined) continue
    const kept = page.rows.reduce((n, row) => n + Object.values(row.clips || {}).filter(Boolean).length, 0)
    if (page.rawMp3 > kept) loss.push(`${page.title}: 原文 ${page.rawMp3} 条 mp3，解析保留 ${kept} 条`)
  }
  if (loss.length) console.log(`\n解析丢失 ${loss.length} 页:\n${loss.slice(0, 20).join('\n')}`)
  else console.log('\n解析自检: 所有页面保留条数与原文 mp3 数一致')

  if (failures.length) console.log(`failures (${failures.length}):\n${failures.join('\n')}`)
}

main().catch(error => {
  console.error('bwiki fetch failed:', error.message)
  process.exitCode = 1
})
