import fs from 'node:fs'
import path from 'node:path'
import crypto from 'node:crypto'

const REPORTS = 'D:/代码/配音猜干员/语音复核'
const ROOT = 'D:/代码/配音猜干员/语音文件'
const lines = fs.readFileSync(path.join(ROOT, 'manifest.tsv'), 'utf8').trim().split('\n').slice(1)
const rows = lines.map(line => {
  const [name, language, category, text, file, url] = line.split('\t')
  return { name, language, category, text, file, url, seconds: null, md5: null }
})
const durations = new Map(JSON.parse(fs.readFileSync(path.join(ROOT, 'audit.json'), 'utf8')).map(r => [r.file, r.seconds]))

const started = Date.now()
for (const row of rows) {
  const buffer = fs.readFileSync(path.join(ROOT, row.file))
  row.md5 = crypto.createHash('md5').update(buffer).digest('hex')
  row.seconds = durations.get(row.file) ?? buffer.length * 8 / 287000
}
console.log(`读入 ${rows.length} 条（md5 耗时 ${((Date.now() - started) / 1000).toFixed(0)}s）`)

const flags = []
const add = (kind, row, detail) => flags.push({ kind, ...row, detail })

// A. one operator reusing the same audio for two different lines
const perOperator = new Map()
for (const row of rows) (perOperator.get(`${row.name}|${row.language}`) || perOperator.set(`${row.name}|${row.language}`, []).get(`${row.name}|${row.language}`)).push(row)
let sameFileAcrossLines = 0
for (const [, list] of perOperator) {
  const byHash = new Map()
  for (const row of list) (byHash.get(row.md5) || byHash.set(row.md5, []).get(row.md5)).push(row)
  for (const [, dup] of byHash) {
    const distinctSlots = new Set(dup.map(row => `${row.category}|${row.text}`)).size
    if (dup.length > 1 && distinctSlots > 1) {
      sameFileAcrossLines++
      add('同一角色两行共用一个音频', dup[0], dup.map(r => `${r.category}:${r.text.slice(0, 12)}`).join(' / '))
    }
  }
}

// B. audio shared between two different operators (worst kind of misassignment)
const globalHash = new Map()
for (const row of rows) (globalHash.get(row.md5) || globalHash.set(row.md5, []).get(row.md5)).push(row)
let crossOperator = 0
for (const [, list] of globalHash) {
  const operators = new Set(list.map(row => row.name))
  if (operators.size > 1) {
    crossOperator++
    add('跨角色共用音频', list[0], [...new Set(list.map(r => `${r.name}/${r.category}`))].slice(0, 6).join(' , '))
  }
}

// C. same bwiki file used for both the 中文 and 日文 slot of one operator/row
//    => that operator only has a single take, which is the documented expectation.
const hashOf = row => row.url.split('/').pop().replace('.mp3', '')
const byTrack = new Map()
for (const row of rows) (byTrack.get(`${row.name}|${hashOf(row)}`) || byTrack.set(`${row.name}|${hashOf(row)}`, []).get(`${row.name}|${hashOf(row)}`)).push(row)
let sharedTrackSlots = 0
let sharedTrackOperators = new Set()
for (const [, list] of byTrack) {
  const langs = new Set(list.map(row => row.language))
  if (langs.size > 1 && list.length > 1) {
    sharedTrackSlots += list.length
    sharedTrackOperators.add(list[0].name)
  }
}

// D. 台词字数 / 音频秒数 ratio. Category-wide duration IQR just reflects that 闲置 and
//    失败 lines are long, so compare each clip against the corpus speech rate instead:
//    a line twice as long as the audio can carry (or vice versa) is a row mismatch.
const norm = text => String(text || '').replace(/[^\p{L}\p{N}]/gu, '')
const rates = new Map()
for (const row of rows) {
  row.chars = norm(row.text).length
  if (row.chars >= 4 && row.seconds >= 0.6) (rates.get(row.language) || rates.set(row.language, []).get(row.language)).push(row.chars / row.seconds)
}
for (const list of rates.values()) list.sort((a, b) => a - b)
const medianOf = language => rates.get(language)?.[Math.floor((rates.get(language)?.length || 1) / 2)] || 5.7
console.log(`\n语速中位数 ${[...rates].map(([language, list]) => `${language} ${medianOf(language).toFixed(2)} 字/秒（${list.length} 条）`).join('，')}`)
for (const row of rows) {
  if (!row.chars || !row.seconds) continue
  const median = medianOf(row.language)
  const rate = row.chars / row.seconds
  if (rate > median * 3.2 || rate < median / 3.2) {
    add('台词与音频长度不符', row, `${row.chars}字 / ${row.seconds.toFixed(2)}s = ${rate.toFixed(2)} 字/秒`)
  }
}

const perCategory = new Map()
for (const row of rows) (perCategory.get(row.category) || perCategory.set(row.category, []).get(row.category)).push(row)
for (const [, list] of perCategory) {
  if (list.length < 30) continue
  const sorted = list.map(r => r.seconds).sort((a, b) => a - b)
  const lo = sorted[Math.floor(sorted.length * 0.25)]
  const hi = sorted[Math.floor(sorted.length * 0.75)]
  const iqr = hi - lo
  for (const row of list) {
    if (row.seconds > hi + 4 * iqr || (row.seconds < Math.max(0.1, lo - 4 * iqr) && row.seconds < 0.35)) {
      add('时长离群', row, `${row.seconds.toFixed(2)}s (该类 IQR ${lo.toFixed(1)}-${hi.toFixed(1)})`)
    }
  }
}

// E. an operator whose 中文/日文 clip counts differ per category: one column was
//    read for one language but not the other, so a slot exists in only one pool.
const perOpCat = new Map()
for (const row of rows) {
  const key = `${row.name}|${row.category}`
  const slot = perOpCat.get(key) || perOpCat.set(key, { 中文: 0, 日文: 0 }).get(key)
  slot[row.language] = (slot[row.language] || 0) + 1
}
for (const [key, slot] of perOpCat) {
  if ((slot['中文'] || 0) !== (slot['日文'] || 0)) {
    const [name, category] = key.split('|')
    add('中日条数不等', { name, language: '中/日', category, seconds: null }, `中文 ${slot['中文'] || 0} 条 / 日文 ${slot['日文'] || 0} 条`)
  }
}

const counts = {}
for (const flag of flags) counts[flag.kind] = (counts[flag.kind] || 0) + 1
console.log(`\n中日共用同一音轨：${sharedTrackSlots} 条，涉及 ${sharedTrackOperators.size} 名干员`)
console.log(`同一角色两行共用一个音频 ${sameFileAcrossLines} 组`)
console.log(`跨角色共用音频 ${crossOperator} 组`)
console.log(`判定分布：${JSON.stringify(counts, null, 0)}`)

const out = ['kind\toperator\tlanguage\tcategory\tchars\tseconds\tdetail']
for (const flag of flags.sort((a, b) => a.kind.localeCompare(b.kind))) out.push([flag.kind, flag.name, flag.language, flag.category, flag.chars ?? '', flag.seconds?.toFixed(2), flag.detail].join('\t'))
fs.writeFileSync(path.join(REPORTS, 'structural-flags.tsv'), out.join('\n') + '\n')
console.log(`明细写出 ${path.join(REPORTS, 'structural-flags.tsv')}（${flags.length} 条）`)
for (const flag of flags.slice(0, 12)) console.log(`  ${flag.kind}  ${(flag.name + ' ' + flag.category).padEnd(20)} ${String(flag.detail).slice(0, 52)}`)
