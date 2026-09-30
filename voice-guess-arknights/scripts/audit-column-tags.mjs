import fs from 'node:fs'
import path from 'node:path'

// Join every downloaded clip with the bwiki column tag its URL appeared under.
// A 中文-pool clip whose only tag is 日/联 is a column error waiting to be heard,
// and a clip whose hash appears under several tags is the single-take case.
const REPORTS = 'D:/代码/配音猜干员/语音复核'
const CACHE = path.join(process.cwd(), '.bwiki-cache', 'pages')
const ROOT = 'D:/代码/配音猜干员/语音文件'

const tagByHash = new Map()
for (const file of fs.readdirSync(CACHE)) {
  const page = JSON.parse(fs.readFileSync(path.join(CACHE, file), 'utf8'))
  for (const row of page.rows || []) {
    for (const [tag, url] of Object.entries(row.clips || {})) {
      if (!url) continue
      const hash = url.split('/').pop().replace('.mp3', '')
      const set = tagByHash.get(hash) || tagByHash.set(hash, new Set()).get(hash)
      set.add(tag)
    }
  }
}

const lines = fs.readFileSync(path.join(ROOT, 'manifest.tsv'), 'utf8').trim().split('\n').slice(1)
const rows = lines.map(line => {
  const [name, language, category, text, file, url] = line.split('\t')
  return { name, language, category, text, file, url, hash: url.split('/').pop().replace('.mp3', '') }
})

const stats = {}
const unknown = []
const risky = []
for (const row of rows) {
  const tags = tagByHash.get(row.hash)
  const key = `${row.language}|${tags ? [...tags].sort().join('+') : '未找到'}`
  stats[key] = (stats[key] || 0) + 1
  if (!tags) { unknown.push(row); continue }
  const list = [...tags]
  const mandarin = list.some(t => t === '中' || t === '方')
  const japanese = list.includes('日')
  if (row.language === '中文' && !mandarin) risky.push({ row, tags: list })
  if (row.language === '日文' && !japanese && !list.includes('联')) risky.push({ row, tags: list })
}

console.log('按池 / bwiki 列标签统计：')
for (const [key, count] of Object.entries(stats).sort((a, b) => b[1] - a[1])) console.log(`  ${key.padEnd(18)} ${count}`)

const grouped = new Map()
for (const item of risky) (grouped.get(item.row.name) || grouped.set(item.row.name, []).get(item.row.name)).push(item)
console.log(`\n池与列标签不符的干员 ${grouped.size} 名，共 ${risky.length} 条：`)
for (const [name, list] of grouped) console.log(`  ${name.padEnd(14)} ${list[0].row.language} ${list.length} 条 标签=${[...new Set(list.flatMap(i => i.tags))].join('/')}`)

console.log(`\n缓存里找不到该哈希的 ${unknown.length} 条`)
const out = ['operator\tlanguage\tcategory\ttext\ttags\turl']
for (const { row, tags } of risky) out.push([row.name, row.language, row.category, row.text, tags.join('+'), row.url].join('\t'))
fs.writeFileSync(path.join(REPORTS, 'column-tag-mismatch.tsv'), out.join('\n') + '\n')
console.log(`明细写出 ${path.join(REPORTS, 'column-tag-mismatch.tsv')}`)
