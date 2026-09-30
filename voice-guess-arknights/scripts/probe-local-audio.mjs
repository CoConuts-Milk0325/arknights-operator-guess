import fs from 'node:fs'
import path from 'node:path'

const ROOT = process.argv[2] || 'D:/代码/配音猜干员/语音文件'
const SAMPLE = Number(process.argv[3] || 3000)

const BITRATES = [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320]
const RATES = [[44100, 48000, 32000], [24000, 16000, 22050], [11025, 12000, 8000]]

/** Walk every MPEG frame header: exact for CBR and VBR, no decoder needed. */
function mp3Frames(buffer) {
  let offset = 0
  if (buffer.slice(0, 3).toString('latin1') === 'ID3') {
    offset = 10 + ((buffer[6] << 21) | (buffer[7] << 14) | (buffer[8] << 7) | buffer[9])
  }
  let seconds = 0
  let frames = 0
  const bitrates = new Set()
  let sampleRate = 0
  let channels = 0
  while (offset + 4 <= buffer.length) {
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
    bitrates.add(BITRATES[bitrateIndex])
    sampleRate = rate
    channels = ((header >>> 6) & 0x03) === 3 ? 1 : 2
    seconds += samples / rate
    frames++
    offset += 4 + Math.floor((samples / 8) * (bitrate / rate)) + padding
  }
  return { seconds, frames, bitrates: [...bitrates], sampleRate, channels }
}

function* walk(dir) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) yield* walk(full)
    else if (entry.name.endsWith('.mp3')) yield full
  }
}

const sizes = []
const vbr = []
let counted = 0
let mismatch = 0
for (const file of walk(ROOT)) {
  if (file.includes('prts-cn_038')) continue
  if (counted >= SAMPLE) break
  const buffer = fs.readFileSync(file)
  const parsed = mp3Frames(buffer)
  counted++
  if (!parsed.frames) continue
  if (parsed.bitrates.length > 1) vbr.push(`${path.basename(file).slice(0, 24)}… ${parsed.bitrates.join('/')}`)
  sizes.push(parsed.seconds)
  // CBR 假设下 bytes*8/码率 应当等于逐帧时长；偏差大就说明该文件不是 CBR
  const assumed = buffer.length * 8 / (192 * 1000)
  if (Math.abs(assumed - parsed.seconds) > Math.max(0.15, parsed.seconds * 0.03)) mismatch++
}
const sorted = sizes.slice().sort((a, b) => a - b)
const q = p => sorted[Math.floor(p * (sorted.length - 1))].toFixed(2)
console.log(`本地 bwiki 文件抽样 ${counted} 个`)
console.log(`时长分布（秒）：p10 ${q(0.1)}  中位 ${q(0.5)}  p90 ${q(0.9)}  最长 ${sorted[sorted.length - 1].toFixed(2)}`)
console.log(`非 CBR（变码率）文件 ${vbr.length} 个${vbr.length ? '：' + vbr.slice(0, 3).join(' | ') : ''}`)
console.log(`用「字节/192kbps」估算会与逐帧真值明显偏差的 ${mismatch} 个 —— 这些就是我之前时长判据误差的来源`)
