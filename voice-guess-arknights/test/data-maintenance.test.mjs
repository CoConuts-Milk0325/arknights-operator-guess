import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { spawnSync } from 'node:child_process'

const scripts = fileURLToPath(new URL('../scripts/', import.meta.url))
function fixture(t, rarity = '0') {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'voice-data-test-'))
  t.after(() => {
    assert.equal(path.dirname(path.resolve(root)), path.resolve(os.tmpdir()))
    assert.ok(path.basename(root).startsWith('voice-data-test-'))
    fs.rmSync(root, { recursive: true, force: true })
  })
  const project = path.join(root, 'voice-guess')
  const data = path.join(project, 'public', 'data')
  fs.mkdirSync(path.join(data, 'voices'), { recursive: true })
  fs.writeFileSync(path.join(data, 'operators.json'), JSON.stringify([{ 干员: '诗怀雅', 稀有度: rarity }]))
  fs.writeFileSync(path.join(data, 'voice-index.json'), JSON.stringify({ 诗怀雅: ['中文'] }))
  fs.writeFileSync(path.join(data, 'voices', '诗怀雅.json'), JSON.stringify({ 中文: { 登录: [{ url: 'voice_cn/char_test/cn_001.wav', text: '你好' }] } }))
  return { root, project, data }
}

test('invalid rarity makes data verification exit nonzero', t => {
  const { project, data } = fixture(t, '6')
  const result = spawnSync(process.execPath, [path.join(scripts, 'verify-updates.mjs'), '--data-dir', data], { cwd: project, encoding: 'utf8' })
  assert.notEqual(result.status, 0, result.stdout + result.stderr)
})

test('standalone valid data verifies without sibling repositories or network', t => {
  const { project, data } = fixture(t)
  const result = spawnSync(process.execPath, [path.join(scripts, 'verify-updates.mjs'), '--data-dir', data], { cwd: project, encoding: 'utf8' })
  assert.equal(result.status, 0, result.stdout + result.stderr)
  assert.match(result.stdout, /Validated 1 operators/)
})

test('audio paths resolve through their source prefix, untagged paths fall back to PRTS', async () => {
  const { getAudioUrl, getFallbackUrl } = await import('../src/config.js')
  assert.equal(getAudioUrl('bwiki:e/e6/x.mp3'), 'https://patchwiki.biligame.com/images/arknights/e/e6/x.mp3')
  assert.equal(getAudioUrl('prts:voice_cn/char_x/cn_001.wav'), 'https://torappu.prts.wiki/assets/audio/voice_cn/char_x/cn_001.mp3')
  assert.equal(getAudioUrl('voice_cn/char_x/cn_001.wav'), 'https://torappu.prts.wiki/assets/audio/voice_cn/char_x/cn_001.mp3')
  assert.equal(getAudioUrl('voice_cn/char_x/cn_001.mp3'), 'https://torappu.prts.wiki/assets/audio/voice_cn/char_x/cn_001.mp3')
  assert.equal(getFallbackUrl({ url: 'bwiki:e/e6/x.mp3', alt: 'voice_cn/char_x/cn_001.mp3' }), 'https://torappu.prts.wiki/assets/audio/voice_cn/char_x/cn_001.mp3')
  assert.equal(getFallbackUrl({ url: 'bwiki:e/e6/x.mp3', alt: 'voice_cn/char_x/cn_001.wav' }), 'https://torappu.prts.wiki/assets/audio/voice_cn/char_x/cn_001.mp3')
  assert.equal(getFallbackUrl({ url: 'bwiki:e/e6/x.mp3' }), null)
})

test('shipped shards pair a bwiki primary with a playable prts fallback', async () => {
  const fs = await import('node:fs')
  const path = await import('node:path')
  const { getAudioUrl, getFallbackUrl } = await import('../src/config.js')
  const dir = path.default.resolve(process.cwd(), 'public/data/voices')
  let bwikiWithAlt = 0
  for (const file of fs.default.readdirSync(dir)) {
    const shard = JSON.parse(fs.default.readFileSync(path.default.join(dir, file), 'utf8'))
    for (const categories of Object.values(shard)) {
      for (const entries of Object.values(categories)) {
        for (const entry of entries) {
          if (entry?.url?.startsWith('bwiki:')) {
            assert.ok(entry.alt, `${file}: bwiki 主源缺备用链接`)
            assert.match(getFallbackUrl(entry), /^https:\/\/torappu\.prts\.wiki\/.+\.mp3$/)
            bwikiWithAlt++
          }
        }
      }
    }
  }
  assert.ok(bwikiWithAlt > 25000, `只找到 ${bwikiWithAlt} 条双源条目`)
})

test('dialect generation synchronizes both existing text exports and stays idempotent', t => {
  const { root, project, data } = fixture(t)
  fs.cpSync(scripts, path.join(project, 'scripts'), { recursive: true })
  fs.mkdirSync(path.join(root, 'voice-line-search'))
  const outputs = [path.join(root, 'voice-texts.json'), path.join(root, 'voice-line-search', 'voice-texts.json')]
  for (const dest of outputs) fs.writeFileSync(dest, '{}')
  const run = () => spawnSync(process.execPath, [path.join(project, 'scripts', 'generate-dialect.mjs')], { encoding: 'utf8' })
  let result = run()
  assert.equal(result.status, 0, result.stderr)
  const voice = JSON.parse(fs.readFileSync(path.join(data, 'voices', '诗怀雅.json')))
  assert.equal(voice.中文.登录.length, 2)
  for (const dest of outputs) assert.deepEqual(JSON.parse(fs.readFileSync(dest)), { 诗怀雅: voice })
  result = run()
  assert.equal(result.status, 0, result.stderr)
  assert.deepEqual(JSON.parse(fs.readFileSync(path.join(data, 'voices', '诗怀雅.json'))), voice)
})
