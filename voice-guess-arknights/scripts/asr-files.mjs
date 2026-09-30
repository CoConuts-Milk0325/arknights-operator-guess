import fs from 'node:fs'
import path from 'node:path'
import crypto from 'node:crypto'

const CACHE = path.join(process.cwd(), '.bwiki-cache', 'asr-local')
const KEY = fs.readFileSync(path.join(process.cwd(), '.env.local'), 'utf8').match(/SILICONFLOW_API_KEY=(.+)/)[1].trim()
const MODEL = process.env.ASR_MODEL || 'XingChenAGI/XingChenASR-V3.2-Ultra'

const ROOT = 'D:/代码/配音猜干员/语音文件'
const argv = process.argv.slice(2)
const listAt = argv.indexOf('--list')
const entries = listAt >= 0
  ? fs.readFileSync(argv[listAt + 1], 'utf8').trim().split('\n').map(line => {
      const [label, rest] = line.includes('\t') ? line.split('\t') : ['', line]
      const file = rest || label
      return { label: rest ? label : '', file: (rest || label).startsWith('D:') ? (rest || label) : path.join(argv[listAt + 2] || '.', rest || label) }
    })
  : argv.map(file => ({ label: '', file }))

for (const { label, file } of entries) {
  const buffer = fs.readFileSync(file)
  const hash = crypto.createHash('sha1').update(`${MODEL}|${file}|${fs.statSync(file).size}`).digest('hex').slice(0, 16)
  const cacheFile = path.join(CACHE, `${hash}.json`)
  let record
  if (fs.existsSync(cacheFile)) record = JSON.parse(fs.readFileSync(cacheFile, 'utf8'))
  else {
    const form = new FormData()
    form.append('file', new Blob([buffer], { type: 'audio/mpeg' }), 'clip.mp3')
    form.append('model', MODEL)
    const res = await fetch('https://api.siliconflow.cn/v1/audio/transcriptions', {
      method: 'POST', headers: { Authorization: `Bearer ${KEY}` }, body: form, signal: AbortSignal.timeout(60000)
    })
    const body = await res.text()
    if (!res.ok) { console.log(`${path.basename(file)}  ${res.status} ${body.slice(0, 60)}`); continue }
    const payload = JSON.parse(body)
    record = { text: payload.text || '', language: payload.language || '', seconds: payload.usage?.seconds ?? null }
    fs.writeFileSync(cacheFile, JSON.stringify(record))
  }
  console.log(`${String(record.language || '-').padEnd(9)} ${buffer.length}B ${label ? label + ' ' : ''}${path.basename(file).slice(0, 40)}\n          「${record.text}」`)
}
