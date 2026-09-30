import fs from 'node:fs'
import path from 'node:path'
import crypto from 'node:crypto'

const REPORTS = 'D:/代码/配音猜干员/语音复核'
const ROOT = process.argv[2] || 'D:/代码/配音猜干员/语音文件'
const BITRATES = [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320]
const RATES = [[44100, 48000, 32000], [24000, 16000, 22050], [11025, 12000, 8000]]

/** Frame-accurate duration; correct for VBR, which 99% of these files are. */
function secondsOf(buffer) {
  let offset = 0
  if (buffer.slice(0, 3).toString('latin1') === 'ID3') {
    offset = 10 + ((buffer[6] << 21) | (buffer[7] << 14) | (buffer[8] << 7) | buffer[9])
  }
  let seconds = 0
  let frames = 0
  while (offset + 4 <= buffer.length && frames < 400000) {
    if (buffer[offset] !== 0xff || (buffer[offset + 1] & 0xe0) !== 0xe0) {
      offset++
      continue
    }
    const header = buffer.readUInt32BE(offset)
    const versionBits = (header >>> 19) & 0x03
    const layerBits = (header >>> 17) & 0x03
    const bitrateIndex = (header >>> 12) & 0x0f
    const rateIndex = (header >>> 10) & 0x03
    const padding = (header >>> 9) & 0x01
    if (versionBits === 1 || layerBits === 0 || layerBits === 3 || bitrateIndex === 0 || bitrateIndex === 15 || rateIndex === 3) {
      offset++
      continue
    }
    const mpeg1 = versionBits === 3
    const bitrate = BITRATES[bitrateIndex] * 1000 * (mpeg1 ? 1 : 0.5)
    const rate = RATES[mpeg1 ? 0 : versionBits === 2 ? 1 : 2][rateIndex]
    const samples = mpeg1 ? 1152 : 576
    seconds += samples / rate
    frames++
    offset += 4 + Math.floor((samples / 8) * (bitrate / rate)) + padding
  }
  return frames ? seconds : null
}

const lines = fs.readFileSync(path.join(ROOT, 'manifest.tsv'), 'utf8').trim().split('\n').slice(1)
const rows = []
for (const line of lines) {
  const [name, language, category, text, file, url] = line.split('\t')
  const full = path.join(ROOT, file)
  if (!fs.existsSync(full)) {
    rows.push({ name, language, category, text, file, url, missing: true })
    continue
  }
  const buffer = fs.readFileSync(full)
  rows.push({
    name, language, category, text, file, url,
    seconds: secondsOf(buffer),
    bytes: buffer.length,
    md5: crypto.createHash('md5').update(buffer).digest('hex'),
  })
}

const chars = text => String(text || '').replace(/[^\p{L}\p{N}]/gu, '').length
const measured = rows.filter(row => row.seconds && !row.missing)
console.log(`清单 ${rows.length} 条；本地读到时长 ${measured.length} 条；文件缺失 ${rows.filter(r => r.missing).length} 条`)

const sorted = measured.map(row => row.seconds).sort((a, b) => a - b)
const q = p => sorted[Math.floor(p * (sorted.length - 1))].toFixed(2)
console.log(`时长分布（秒）：p05 ${q(0.05)}  p25 ${q(0.25)}  中位 ${q(0.5)}  p75 ${q(0.75)}  p95 ${q(0.95)}  最长 ${sorted[sorted.length - 1].toFixed(2)}`)

// 1) same bytes in both language folders => bwiki itself says this slot has a single track
const byHash = new Map()
for (const row of measured) (byHash.get(row.md5) || byHash.set(row.md5, []).get(row.md5)).push(row)
const sharedAcrossLanguages = [...byHash.values()].filter(list => new Set(list.map(r => `${r.name}|${r.language}`)).size > 1)
const sharedSameLanguage = [...byHash.values()].filter(list => new Set(list.map(r => `${r.name}|${r.language}`)).size === 1 && list.length > 1)
console.log(`\n跨语言字节相同的槽位 ${sharedAcrossLanguages.length} 个（bwiki 自证这些干员只有一条音轨）`)
console.log(`同一语言内字节重复 ${sharedSameLanguage.length} 组（我们侧疑似重复条目）`)

// 2) Mandarin speech runs ~4.5 chars/s: flag clips far off the text they are labelled with
const cn = measured.filter(row => row.language === '中文' && chars(row.text) >= 12)
const rate = cn.map(row => chars(row.text) / row.seconds).sort((a, b) => a - b)
const medRate = rate[Math.floor(rate.length / 2)]
console.log(`\n中文条目 字数/秒 中位数 ${medRate.toFixed(2)}（样本 ${cn.length}）`)
const tooLong = cn.filter(row => row.seconds > chars(row.text) / (medRate * 0.55)).map(row => ({ ...row, cps: chars(row.text) / row.seconds }))
const tooShort = cn.filter(row => row.seconds < chars(row.text) / (medRate * 1.9)).map(row => ({ ...row, cps: chars(row.text) / row.seconds }))
console.log(`明显偏长（疑似非国语演绎）${tooLong.length} 条；明显偏短（疑似配错台词）${tooShort.length} 条`)
const show = (title, list) => {
  console.log(`\n${title}（前 8 条）:`)
  for (const row of list.sort((a, b) => a.cps - b.cps).slice(0, 8)) console.log(`  ${(row.name + ' ' + row.category).padEnd(22)} ${row.seconds.toFixed(2)}s / ${chars(row.text)}字 = ${row.cps.toFixed(2)} 字/秒  ${String(row.text).slice(0, 18)}`)
}
show('偏长', tooLong)
show('偏短', tooShort)

// Per-category baselines: 闲置/戳一下 are panting or onomatopoeia (few chars, long audio),
// so a single global chars-per-second cutoff misflags them. Judge each category against itself.
const byCategory = new Map()
for (const row of cn) (byCategory.get(row.category) || byCategory.set(row.category, []).get(row.category)).push(row)
const baselines = []
const flagged = []
for (const [category, list] of [...byCategory].sort((a, b) => b[1].length - a[1].length)) {
  const rates = list.map(row => chars(row.text) / row.seconds).sort((a, b) => a - b)
  const base = rates[Math.floor(rates.length / 2)]
  baselines.push(`${category} ${base.toFixed(1)}字/s(n=${list.length})`)
  if (list.length < 8) continue
  for (const row of list) {
    const cps = chars(row.text) / row.seconds
    const ratio = cps / base
    if (ratio < 0.45 || ratio > 2.2) flagged.push({ ...row, category, cps, ratio, base })
  }
}
console.log(`\n各类别基线（中位字/秒）：${baselines.slice(0, 14).join('  ')}`)
console.log(`按类别基线判定后仍离群的只剩 ${flagged.length} 条（全局一刀切时是 254 条）`)

const report = flagged.sort((a, b) => a.ratio - b.ratio)
  .map(row => [row.name, row.language, row.category, row.seconds.toFixed(2), chars(row.text), row.base.toFixed(2), row.cps.toFixed(2), row.ratio.toFixed(2), row.file].join('\t'))
fs.writeFileSync(path.join(REPORTS, 'suspicious.tsv'), ['operator\tlanguage\tcategory\tseconds\tchars\tcategoryBase\tcharsPerSecond\tratio\tfile', ...report].join('\n') + '\n')
console.log(`可疑名单已写出 ${path.join(REPORTS, 'suspicious.tsv')}`)
for (const row of report.slice(0, 6)) console.log('  ' + row.split('\t').slice(0, 8).join('  '))
for (const row of report.slice(-4)) console.log('  ' + row.split('\t').slice(0, 8).join('  '))

fs.writeFileSync(path.join(ROOT, 'audit.json'), JSON.stringify(rows.map(({ name, language, category, text, file, url, seconds, bytes, missing }) => ({ name, language, category, text, file, url, seconds, bytes, missing })), null, 1))
console.log(`\n逐条时长与哈希已写出 ${path.join(ROOT, 'audit.json')}`)
