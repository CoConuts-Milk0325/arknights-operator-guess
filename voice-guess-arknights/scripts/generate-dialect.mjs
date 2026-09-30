import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { syncVoiceTexts } from './sync-voice-texts.mjs'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const VOICES_DIR = path.join(__dirname, '..', 'public', 'data', 'voices')

// 有方言语音的干员（prts.wiki 的 voice_custom 目录）
const DIALECT_OPERATORS = [
  '诗怀雅', '琳琅诗怀雅', '桑葚', '槐琥', '林', '乌有', '雪雉', '食铁兽',
  '赤刃明霄陈', '假日威龙陈', '陈', '夕', '阿', '星熊', '年', '令',
  '老鲤', '重岳', '黍', '左乐', '余', '望'
]

// 方言语音文件名（所有干员一致），cn_043/044 在标准中文里无对应句，自动跳过
const DIALECT_FILES = [
  '001', '002', '003', '004', '005', '006', '007', '008', '009', '010',
  '011', '012', '013', '014', '017', '018', '019', '020', '021', '022',
  '023', '024', '025', '026', '027', '028', '029', '030', '031', '032',
  '033', '034', '036', '037', '038', '042', '043', '044'
]

function main() {
  let totalAdded = 0
  for (const name of DIALECT_OPERATORS) {
    const file = path.join(VOICES_DIR, `${name}.json`)
    if (!fs.existsSync(file)) {
      console.warn(`[skip] no voice file: ${name}`)
      continue
    }
    const data = JSON.parse(fs.readFileSync(file, 'utf8'))
    const cn = data['中文']
    if (!cn) {
      console.warn(`[skip] no 中文 data: ${name}`)
      continue
    }

    // 从标准中文 URL 中取 char_id
    let charId = null
    for (const type of Object.keys(cn)) {
      if (type.includes('皮肤')) continue
      for (const e of cn[type]) {
        const u = typeof e === 'string' ? e : e.url
        const m = u.match(/\/(char_[^/]+)\//)
        if (m) { charId = m[1]; break }
      }
      if (charId) break
    }
    if (!charId) {
      console.warn(`[skip] no char id: ${name}`)
      continue
    }

    // 构建 标准中文 编号 -> {type, text} 映射
    const map = {}
    for (const type of Object.keys(cn)) {
      if (type.includes('皮肤')) continue
      for (const e of cn[type]) {
        const u = typeof e === 'string' ? e : e.url
        const m = u.match(/cn_(\d+)\.wav/)
        if (m && map[m[1]] === undefined) {
          map[m[1]] = { type, text: typeof e === 'string' ? '' : (e.text || '') }
        }
      }
    }

    // 幂等：先清掉已生成的方言条目，再重新生成
    for (const type of Object.keys(cn)) {
      cn[type] = cn[type].filter(e => {
        const u = typeof e === 'string' ? e : e.url
        return !u.includes('voice_custom')
      })
    }

    // 按同号标准句并入对应类型
    let added = 0
    for (const num of DIALECT_FILES) {
      const std = map[num]
      if (!std) continue
      cn[std.type].push({
        url: `voice_custom/${charId}_cn_topolect/cn_${num}.wav`,
        text: std.text
      })
      added++
    }

    fs.writeFileSync(file, JSON.stringify(data))
    totalAdded += added
    console.log(`${name} (+${added})`)
  }
  syncVoiceTexts(path.join(__dirname, '..'))
  console.log(`\ndone, total dialect entries added: ${totalAdded}`)
}

main()
