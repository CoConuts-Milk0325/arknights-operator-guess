import fs from 'node:fs'
import path from 'node:path'
import assert from 'node:assert/strict'
import { fileURLToPath } from 'node:url'
import { getAvatarUrl } from '../src/logic/gameEngine.js'
import { getAudioUrl } from '../src/config.js'
import { AUDIO_BASES } from '../src/utils/constants.js'
import { loadOperators, searchOperators } from '../src/logic/operatorSearch.js'

const project = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const args = process.argv.slice(2)
const dirArg = args.indexOf('--data-dir')
const dataDir = dirArg >= 0 ? path.resolve(args[dirArg + 1]) : path.join(project, 'public', 'data')
const read = file => JSON.parse(fs.readFileSync(file, 'utf8'))
const sorted = keys => [...keys].sort()

async function verify() {
  const operators = read(path.join(dataDir, 'operators.json'))
  const index = read(path.join(dataDir, 'voice-index.json'))
  assert.ok(Array.isArray(operators) && operators.length > 0, 'operators must be a nonempty array')
  const names = operators.map(op => op.干员)
  assert.equal(new Set(names).size, names.length, 'duplicate operator names')
  assert.deepEqual(sorted(Object.keys(index)), sorted(names), 'index/operator names differ')
  assert.deepEqual(sorted(fs.readdirSync(path.join(dataDir, 'voices')).filter(x => x.endsWith('.json')).map(x => x.slice(0, -5))), sorted(names), 'shard/operator names differ')
  const allVoices = {}
  let clips = 0
  for (const op of operators) {
    assert.ok(typeof op.干员 === 'string' && op.干员.trim() && !/[\\/]/.test(op.干员), 'invalid operator name')
    assert.match(String(op.稀有度), /^[0-5]$/, `${op.干员}: rarity must be 0-5`)
    const voices = read(path.join(dataDir, 'voices', `${op.干员}.json`))
    assert.ok(voices && typeof voices === 'object' && !Array.isArray(voices), `${op.干员}: invalid voice shard`)
    assert.deepEqual(sorted(Object.keys(voices)), sorted(index[op.干员]), `${op.干员}: index languages differ`)
    let count = 0
    for (const [language, categories] of Object.entries(voices)) {
      assert.ok(categories && typeof categories === 'object' && !Array.isArray(categories), `${op.干员}/${language}: invalid categories`)
      for (const entries of Object.values(categories)) {
        assert.ok(Array.isArray(entries), `${op.干员}: clips must be arrays`)
        for (const entry of entries) {
          const url = typeof entry === 'string' ? entry : entry?.url
          assert.ok(typeof url === 'string' && url.trim() && !url.startsWith('/') && !url.includes('..') && !url.includes('://'), `${op.干员}: invalid audio URL`)
          const scheme = /^(\w+):/.exec(url)
          if (scheme) assert.ok(AUDIO_BASES[scheme[1]], `${op.干员}: unknown audio source "${scheme[1]}"`)
          count++
        }
      }
    }
    assert.ok(count > 0, `${op.干员}: no audio clips`)
    clips += count
    allVoices[op.干员] = voices
  }
  // Full workspaces keep optional exports; a standalone checkout does not require them.
  const workspace = path.resolve(dataDir, '../../..')
  for (const file of [path.join(workspace, 'voice-texts.json'), path.join(workspace, 'voice-line-search', 'voice-texts.json')]) {
    if (!fs.existsSync(file)) continue
    const export_ = read(file)
    // deepEqual on ~32k entries builds a diff large enough to exhaust the heap, so report by hand.
    const mismatches = []
    for (const [name, voices] of Object.entries(allVoices)) {
      if (mismatches.length >= 3) break
      if (export_[name] === undefined) { mismatches.push(`${name}: 总表缺失`); continue }
      if (JSON.stringify(export_[name]) !== JSON.stringify(voices)) mismatches.push(`${name}: 与分片不一致`)
    }
    for (const name of Object.keys(export_)) if (!allVoices[name] && mismatches.length < 3) mismatches.push(`${name}: 分片中不存在`)
    assert.equal(mismatches.length, 0, `stale text export: ${file}（前 3 处：${mismatches.join('；')}；可执行 node scripts/sync-voice-texts.mjs 刷新）`)
  }
  const originalFetch = globalThis.fetch
  try {
    globalThis.fetch = async () => ({ ok: true, json: async () => operators })
    const searchable = await loadOperators()
    for (const op of searchable) assert.ok(searchOperators(op.name, searchable).some(result => result.name === op.name), `name not searchable: ${op.name}`)
  } finally {
    globalThis.fetch = originalFetch
  }
  console.log(`Validated ${operators.length} operators, ${clips} clips; index, shards, rarity, search and existing exports agree.`)
  if (args.includes('--online')) {
    // Optional network smoke test; deterministic local validation remains the CI gate.
    for (const op of operators.slice(-4)) {
      const voices = allVoices[op.干员]
      const urls = [getAvatarUrl({ name: op.干员, rarity: op.稀有度 })]
      for (const categories of Object.values(voices)) {
        const entry = Object.values(categories).flat()[0]
        if (entry) urls.push(getAudioUrl(typeof entry === 'string' ? entry : entry.url))
      }
      for (const url of urls) {
        const response = await fetch(url, { method: 'HEAD', signal: AbortSignal.timeout(15000) })
        assert.ok(response.ok, `HTTP ${response.status}: ${url}`)
      }
    }
    console.log('Online smoke checks passed.')
  }
}

verify().catch(error => {
  console.error('Data validation failed:', error.message)
  process.exitCode = 1
})
