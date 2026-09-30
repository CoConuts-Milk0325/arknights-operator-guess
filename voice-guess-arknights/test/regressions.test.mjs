import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import http from 'node:http'
import { spawn } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { createChallenge, recordQuestion, generateSummary } from '../src/logic/challenge.js'
import { selectRandomOperator } from '../src/logic/gameEngine.js'
import worker from '../cf-worker.js'
import { parse, compileScript } from '@vue/compiler-sfc'
import * as vue from 'vue'
import * as engine from '../src/logic/gameEngine.js'
import * as challengeLogic from '../src/logic/challenge.js'
import * as constants from '../src/utils/constants.js'
import { DATA_VERSION } from '../src/dataVersion.js'
import { buildVoiceUrl } from '../src/logic/audioLoader.js'
import { getFallbackUrl } from '../src/config.js'

// Execute the real SFC setup with browser I/O replaced; Vue reactivity stays real.
function board(voiceData, load = async () => [], io = {}) {
  const source = fs.readFileSync(new URL('../src/components/GameBoard.vue', import.meta.url), 'utf8')
  const { descriptor } = parse(source)
  const script = compileScript(descriptor, { id: 'test-board', genDefaultAs: 'component' })
  const scope = { ...vue, ...engine, ...challengeLogic, ...constants, DATA_VERSION,
    onMounted: () => {}, loadOperators: load, searchOperators: () => [], window: { location: { search: '' } },
    getCached: () => null, setCache: () => {}, buildVoiceUrl: x => x, preloadAudio: () => {},
    fetch: async url => ({ ok: true, json: async () => {
      const value = voiceData[decodeURIComponent(url.split('/').pop().split('.json')[0])]
      return typeof value === 'function' ? value() : value
    } }),
    GameBoard: {}, AudioPlayer: {}, GuessInput: {}, ChoiceMode: {}, ResultCard: {}, SettingsDrawer: {}, ChallengeBar: {}, SummaryReport: {},
    ...io,
  }
  delete scope['default']
  delete scope['module.exports']
  const executable = script.content.replace(/^import .*$/gm, '')
  return new Function(...Object.keys(scope), `${executable}; return component.setup({}, { expose() {} })`)(...Object.values(scope))
}

function audioPlayer(props, Audio, timers = {}, emit = () => {}) {
  const source = fs.readFileSync(new URL('../src/components/AudioPlayer.vue', import.meta.url), 'utf8')
  const { descriptor } = parse(source)
  const script = compileScript(descriptor, { id: 'test-audio', genDefaultAs: 'component' })
  const scope = { ...vue, onUnmounted: () => {}, buildVoiceUrl, getFallbackUrl, Audio, props, emit, ...timers }
  delete scope.default
  delete scope['module.exports']
  const executable = script.content.replace(/^import .*$/gm, '')
  return new Function(...Object.keys(scope), `${executable}; return component.setup(props, { expose() {}, emit })`)(...Object.values(scope))
}

test('blocked storage never discards a successfully downloaded question', async t => {
  const previous = Object.getOwnPropertyDescriptor(globalThis, 'localStorage')
  t.after(() => {
    if (previous) Object.defineProperty(globalThis, 'localStorage', previous)
    else delete globalThis.localStorage
  })
  Object.defineProperty(globalThis, 'localStorage', {
    configurable: true,
    get() { throw new Error('SecurityError: storage blocked') }
  })
  const cache = await import('../src/cache.js')
  const state = board({ A: { 中文: { 登录: [{ url: 'voice/a.wav' }] } } }, async () => [], cache)
  state.operators.value = [{ name: 'A', rarity: '0' }]
  await state.startNewQuestion()
  assert.equal(state.currentQuestion.value?.operator.name, 'A')
  assert.equal(state.questionError.value, '')
  assert.doesNotThrow(() => cache.clearCache())
})

test('old and completed question audio errors cannot skip the current clip', async () => {
  const state = board({ A: { 中文: { 登录: ['a.wav', 'b.wav', 'c.wav'] } } })
  state.operators.value = [{ name: 'A', rarity: '0' }]
  await state.startNewQuestion()
  state.currentClipIndex.value = 2
  state.onAudioSkip(0)
  assert.equal(state.currentClipIndex.value, 2)
  state.onAudioSkip(1)
  assert.equal(state.currentClipIndex.value, 3)
  state.onAudioSkip(1)
  assert.equal(state.currentClipIndex.value, 3)
  state.currentClipIndex.value = 2
  state.onGuess('A')
  state.onAudioSkip(1)
  assert.equal(state.currentClipIndex.value, 2)
})

test('inactive players never emit skip after primary and alternate source failure', () => {
  const instances = []
  class FakeAudio {
    constructor() { this.listeners = {}; instances.push(this) }
    addEventListener(name, handler) { this.listeners[name] = handler }
    load() {}
    pause() {}
    removeAttribute() {}
  }
  const events = []
  const player = audioPlayer({ url: 'bwiki:a/a.mp3', alt: 'voice/a.mp3', active: false }, FakeAudio, {}, e => events.push(e))
  const audio = instances[0]
  audio.error = { code: 4 }
  audio.listeners.error()
  audio.listeners.error()
  assert.equal(events.filter(e => e === 'skip').length, 0)
  player.stopMyAudio()
})

test('terminal alternate audio errors clear playing state and progress', async () => {
  for (const code of [2, 3, 4]) {
    const instances = []
    const timers = new Set()
    const events = []
    class FakeAudio {
      constructor() { this.listeners = {}; instances.push(this) }
      addEventListener(name, handler) { this.listeners[name] = handler }
      load() {}
      pause() {}
      removeAttribute() {}
      play() { return Promise.resolve() }
    }
    const player = audioPlayer({ url: 'bwiki:a/a.mp3', alt: 'voice/a.mp3', active: true }, FakeAudio, {
      setInterval: () => { timers.add(1); return 1 },
      clearInterval: id => timers.delete(id)
    }, e => events.push(e))
    try {
      player.togglePlay()
      await new Promise(resolve => setImmediate(resolve))
      const audio = instances[0]
      audio.error = { code: 2 }
      audio.listeners.error()
      await new Promise(resolve => setImmediate(resolve))
      audio.error = { code }
      audio.listeners.error()
      audio.listeners.error()
      assert.equal(player.isPlaying.value, false, `code ${code}`)
      assert.equal(player.isLoaded.value, false)
      assert.equal(timers.size, 0)
      assert.ok(player.loadError.value)
      assert.equal(events.filter(e => e === 'skip').length, 1)
    } finally {
      player.stopMyAudio()
    }
  }
})

test('retrying the failed final clip reloads primary audio without changing the question', async () => {
  const instances = []
  const events = []
  class FakeAudio {
    constructor() { this.listeners = {}; this.playedUrls = []; instances.push(this) }
    addEventListener(name, handler) { this.listeners[name] = handler }
    load() {}
    pause() {}
    removeAttribute() {}
    play() { this.playedUrls.push(this.src); return Promise.resolve() }
  }
  const props = { url: 'bwiki:a/a.mp3', alt: 'voice/a.mp3', active: true }
  const state = board({ A: { 中文: { 登录: [props] } } })
  state.operators.value = [{ name: 'A', rarity: '0' }]
  state.inChallenge.value = true
  state.challenge.value = createChallenge(3)
  await state.startNewQuestion()
  const player = audioPlayer(props, FakeAudio, {}, e => {
    events.push(e)
    if (e === 'skip') state.onAudioSkip(0)
  })
  try {
    instances[0].error = { code: 4 }
    instances[0].listeners.error()
    instances[0].listeners.error()
    assert.ok(player.loadError.value)
    player.retryAudio()
    await new Promise(resolve => setImmediate(resolve))
    assert.equal(instances.length, 2)
    assert.deepEqual(instances[1].playedUrls, ['https://patchwiki.biligame.com/images/arknights/a/a.mp3'])
    assert.equal(player.loadError.value, '')
    assert.equal(player.isPlaying.value, true)
    assert.equal(events.filter(e => e === 'skip').length, 1)
    assert.equal(state.currentQuestion.value.operator.name, 'A')
    assert.equal(state.currentClipIndex.value, 1)
    assert.equal(state.questionGuessCount.value, 0)
    assert.equal(state.showResult.value, false)
    assert.deepEqual(state.challenge.value.usedOperators, ['A'])
    assert.equal(state.challenge.value.history.length, 0)
  } finally {
    player.stopMyAudio()
  }
})

test('challenge choice count follows a changed guess limit without consuming another operator', async () => {
  const state = board({ A: { 中文: { 登录: ['a.wav'] } } })
  state.operators.value = Array.from({ length: 12 }, (_, i) => ({ name: i ? `B${i}` : 'A', rarity: '0' }))
  state.targetOperator.value = state.operators.value[0]
  state.inChallenge.value = true
  state.challenge.value = createChallenge(3)
  await state.startNewQuestion()
  assert.equal(state.currentChoices.value.length, 10)
  state.settings.maxGuesses = 3
  state.onSettingsConfirm()
  await vue.nextTick()
  assert.equal(state.currentChoices.value.length, 3)
  assert.ok(state.currentChoices.value.some(op => op.name === 'A'))
  assert.deepEqual(state.challenge.value.usedOperators, ['A'])
  assert.equal(state.challenge.value.currentQuestion, 0)
})

test('lowering the limit to guesses already used records exactly one failure', async () => {
  const state = board({ A: { 中文: { 登录: ['a.wav', 'b.wav', 'c.wav'] } } })
  state.operators.value = [{ name: 'A', rarity: '0' }]
  state.inChallenge.value = true
  state.challenge.value = createChallenge(3)
  await state.startNewQuestion()
  for (const name of ['B', 'C', 'D']) state.onGuess(name)
  const clipIndex = state.currentClipIndex.value
  state.settings.maxGuesses = 3
  await vue.nextTick()
  assert.equal(state.showResult.value, true)
  assert.equal(state.challenge.value.history.length, 1)
  assert.equal(state.challenge.value.history[0].correct, false)
  assert.equal(state.challenge.value.history[0].guessed, 'D')
  assert.equal(state.currentClipIndex.value, clipIndex)
  state.onGuess('A')
  state.onSettingsConfirm()
  await vue.nextTick()
  assert.equal(state.challenge.value.history.length, 1)
})

test('base voice filters include skin clips while retaining their display type', () => {
  const voices = { A: { 中文: { 登录: ['a.wav'], '登录（皮肤）': ['skin.wav'], '交谈（皮肤）': ['talk.wav'] } } }
  const clips = engine.getVoiceClips('A', voices, { languages: ['中文'], voiceTypes: ['登录'] })
  assert.equal(clips.length, 2)
  assert.ok(clips.some(c => c.type === '登录（皮肤）' && c.url === 'skin.wav'))
  assert.ok(!clips.some(c => c.type === '交谈（皮肤）'))
})

test('empty voice selections never become playable questions', async () => {
  const state = board({ A: { 中文: { 登录: [{ url: 'voice/a.wav' }] } } })
  state.settings.voiceTypes = ['精英化2']
  assert.equal(await state.prepareQuestion({ name: 'A', rarity: '0' }), null)
})

test('challenge does not start when the selected voice type has too few playable operators', async () => {
  const voice = { 中文: { 登录: [{ url: 'voice/test.wav' }] } }
  const state = board({ A: voice, B: voice, C: voice })
  state.operators.value = ['A', 'B', 'C'].map(name => ({ name, rarity: '0' }))
  state.settings.questionCount = 3
  state.settings.selectedStars = [1]
  state.settings.voiceTypes = ['精英化2']
  state.showChallengeSetup.value = true

  await state.startChallenge()

  assert.equal(state.inChallenge.value, false)
  assert.equal(state.showChallengeSetup.value, true)
  assert.match(state.setupError.value, /可用干员不足/)
})

test('challenge availability check can be retried after a temporary shard failure', async () => {
  let available = false
  const voice = () => available
    ? { 中文: { 登录: [{ url: 'voice/test.wav' }] } }
    : { 中文: {} }
  const state = board({ A: voice, B: voice, C: voice })
  state.operators.value = ['A', 'B', 'C'].map(name => ({ name, rarity: '0' }))
  state.settings.questionCount = 3
  state.showChallengeSetup.value = true

  await state.startChallenge()
  assert.equal(state.inChallenge.value, false)
  available = true
  await state.startChallenge()

  assert.equal(state.inChallenge.value, true)
})

test('confirming settings during a challenge keeps the current question and its slot', async () => {
  const voice = { 中文: { 登录: [{ url: 'voice/test.wav' }] } }
  const state = board({ A: voice, B: voice, C: voice })
  state.operators.value = ['A', 'B', 'C'].map(name => ({ name, rarity: '0' }))
  state.inChallenge.value = true
  state.challenge.value = createChallenge(3)
  await state.startNewQuestion()
  const first = state.currentQuestion.value.operator.name

  state.onSettingsConfirm()
  await new Promise(resolve => setImmediate(resolve))

  assert.equal(state.currentQuestion.value.operator.name, first)
  assert.deepEqual(state.challenge.value.usedOperators, [first])
  assert.equal(state.challenge.value.currentQuestion, 0)
})

test('audio network failure switches to the alternate source', () => {
  const instances = []
  class FakeAudio {
    constructor() { this.listeners = {}; instances.push(this) }
    addEventListener(name, handler) { this.listeners[name] = handler }
    load() { this.loads = (this.loads || 0) + 1 }
  }
  audioPlayer({ url: 'bwiki:e/e6/x.mp3', alt: 'voice_cn/char_x/cn_001.mp3', language: '中文' }, FakeAudio)
  const audio = instances[0]
  audio.error = { code: 2 }
  audio.listeners.error()

  assert.equal(audio.src, 'https://torappu.prts.wiki/assets/audio/voice_cn/char_x/cn_001.mp3')
  assert.equal(audio.loads, 1)
})

test('audio playback resumes on the alternate source after a network failure', async () => {
  const instances = []
  class FakeAudio {
    constructor() { this.listeners = {}; this.playedUrls = []; instances.push(this) }
    addEventListener(name, handler) { this.listeners[name] = handler }
    load() {}
    pause() {}
    removeAttribute() {}
    play() {
      this.playedUrls.push(this.src)
      return this.src.includes('patchwiki') ? Promise.reject(new Error('network')) : Promise.resolve()
    }
  }
  const player = audioPlayer({ url: 'bwiki:e/e6/x.mp3', alt: 'voice_cn/char_x/cn_001.mp3', language: '中文' }, FakeAudio)
  const audio = instances[0]
  player.togglePlay()
  audio.error = { code: 2 }
  audio.listeners.error()
  await new Promise(resolve => setImmediate(resolve))

  assert.deepEqual(audio.playedUrls, [
    'https://patchwiki.biligame.com/images/arknights/e/e6/x.mp3',
    'https://torappu.prts.wiki/assets/audio/voice_cn/char_x/cn_001.mp3'
  ])
  assert.equal(player.loadError.value, '')
  player.stopMyAudio()
})

test('audio playback resumes when play rejects before the network error event', async () => {
  const instances = []
  class FakeAudio {
    constructor() { this.listeners = {}; this.playedUrls = []; instances.push(this) }
    addEventListener(name, handler) { this.listeners[name] = handler }
    load() {}
    pause() {}
    removeAttribute() {}
    play() {
      this.playedUrls.push(this.src)
      return this.src.includes('patchwiki') ? Promise.reject(new Error('network')) : Promise.resolve()
    }
  }
  const player = audioPlayer({ url: 'bwiki:e/e6/x.mp3', alt: 'voice_cn/char_x/cn_001.mp3', language: '中文' }, FakeAudio)
  const audio = instances[0]
  player.togglePlay()
  await new Promise(resolve => setImmediate(resolve))
  audio.error = { code: 2 }
  audio.listeners.error()
  await new Promise(resolve => setImmediate(resolve))

  assert.deepEqual(audio.playedUrls, [
    'https://patchwiki.biligame.com/images/arknights/e/e6/x.mp3',
    'https://torappu.prts.wiki/assets/audio/voice_cn/char_x/cn_001.mp3'
  ])
  assert.equal(player.loadError.value, '')
  player.stopMyAudio()
})

test('failed alternate playback stops progress after the primary was playing', async () => {
  const instances = []
  const activeTimers = new Set()
  let nextTimer = 0
  class FakeAudio {
    constructor() { this.listeners = {}; instances.push(this) }
    addEventListener(name, handler) { this.listeners[name] = handler }
    load() {}
    pause() {}
    removeAttribute() {}
    play() {
      return this.src.includes('patchwiki') ? Promise.resolve() : Promise.reject(new Error('fallback failed'))
    }
  }
  const player = audioPlayer(
    { url: 'bwiki:e/e6/x.mp3', alt: 'voice_cn/char_x/cn_001.mp3', language: '中文' },
    FakeAudio,
    {
      setInterval: () => { const id = ++nextTimer; activeTimers.add(id); return id },
      clearInterval: id => activeTimers.delete(id)
    }
  )
  const audio = instances[0]
  player.togglePlay()
  await new Promise(resolve => setImmediate(resolve))
  assert.equal(activeTimers.size, 1)
  audio.error = { code: 2 }
  audio.listeners.error()
  await new Promise(resolve => setImmediate(resolve))

  assert.equal(player.isPlaying.value, false)
  assert.equal(activeTimers.size, 0)
  player.stopMyAudio()
})

test('a late audio error from the previous clip cannot replace the current clip', async () => {
  const instances = []
  class FakeAudio {
    constructor() { this.listeners = {}; instances.push(this) }
    addEventListener(name, handler) { this.listeners[name] = handler }
    load() {}
    pause() {}
    removeAttribute() {}
  }
  const props = vue.reactive({ url: 'bwiki:e/e6/old.mp3', alt: 'voice_cn/old.mp3', language: '中文' })
  audioPlayer(props, FakeAudio)
  const previous = instances[0]
  props.alt = 'voice_cn/new.mp3'
  props.url = 'bwiki:e/e6/new.mp3'
  await vue.nextTick()
  const current = instances[1]
  previous.error = { code: 2 }
  current.error = { code: 2 }
  previous.listeners.error()

  assert.equal(current.src, 'https://patchwiki.biligame.com/images/arknights/e/e6/new.mp3')
})

test('local static server rejects encoded paths outside dist', async t => {
  const child = spawn(process.execPath, ['server.js'], {
    cwd: fileURLToPath(new URL('../', import.meta.url)),
    stdio: ['ignore', 'pipe', 'pipe']
  })
  t.after(() => child.kill())
  const port = await new Promise((resolve, reject) => {
    let output = ''
    const timer = setTimeout(() => reject(new Error(`server did not start: ${output}`)), 5000)
    child.stdout.on('data', chunk => {
      output += chunk.toString()
      const match = output.match(/Server: http:\/\/localhost:(\d+)/)
      if (match) { clearTimeout(timer); resolve(Number(match[1])) }
    })
    child.once('exit', code => { clearTimeout(timer); reject(new Error(`server exited ${code}: ${output}`)) })
  })
  const response = await new Promise((resolve, reject) => {
    http.get({ hostname: '127.0.0.1', port, path: '/..%2Fserver.js' }, res => {
      res.resume()
      res.on('end', () => resolve(res.statusCode))
    }).on('error', reject)
  })
  assert.equal(response, 403)
})

test('retry reloads metadata when the initial load failed', async () => {
  const state = board({ A: { 中文: { 登录: [{ url: 'voice/a.wav' }] } } }, async () => [{ name: 'A', rarity: '0' }])
  await state.startNewQuestion()
  assert.equal(state.currentQuestion.value?.operator.name, 'A')
})

test('target URL cannot repeat operators during a challenge', async () => {
  const state = board({ A: { 中文: { 登录: [{ url: 'voice/a.wav' }] } }, B: { 中文: { 登录: [{ url: 'voice/b.wav' }] } } })
  state.operators.value = [{ name: 'A', rarity: '0' }, { name: 'B', rarity: '0' }]
  state.targetOperator.value = state.operators.value[0]
  state.inChallenge.value = true
  state.challenge.value.usedOperators = ['A']
  await state.startNewQuestion()
  assert.equal(state.currentQuestion.value.operator.name, 'B')
})

test('data release invalidates pre-release voice cache', async t => {
  const previous = globalThis.localStorage
  t.after(() => { globalThis.localStorage = previous })
  const entries = { 'voice-guess-v2-voice-A': JSON.stringify({ data: { stale: true }, timestamp: Date.now() }) }
  globalThis.localStorage = { ...entries, getItem: k => entries[k] ?? null, setItem: (k,v) => { entries[k] = v }, removeItem: k => { delete entries[k] } }
  const { getCached, setCache } = await import('../src/cache.js')
  assert.equal(getCached('voice-A'), null)
  setCache('voice-A', { fresh: true })
  assert.deepEqual(getCached('voice-A'), { fresh: true })
})

test('all unavailable candidates terminate with an actionable error', async () => {
  let attempts = 0
  const state = board({ A: () => { attempts++; return { 中文: {} } }, B: () => { attempts++; return { 中文: {} } } })
  state.operators.value = [{ name: 'A', rarity: '0' }, { name: 'B', rarity: '0' }]
  await state.startNewQuestion()
  assert.equal(state.currentQuestion.value, null)
  assert.equal(state.loading.value, false)
  assert.ok(state.questionError.value)
  assert.equal(attempts, 2)
})

test('a slow obsolete question cannot overwrite the latest request', async () => {
  let release
  const slow = new Promise(resolve => { release = resolve })
  const voice = { 中文: { 登录: [{ url: 'voice/test.wav' }] } }
  const state = board({ A: () => slow, B: voice })
  state.operators.value = [{ name: 'A', rarity: '0' }, { name: 'B', rarity: '0' }]
  state.targetOperator.value = state.operators.value[0]
  const first = state.startNewQuestion()
  state.targetOperator.value = state.operators.value[1]
  await state.startNewQuestion()
  release(voice)
  await first
  assert.equal(state.currentQuestion.value.operator.name, 'B')
  assert.equal(state.loading.value, false)
})

test('all-correct challenges receive S for each length and input mode', () => {
  for (const count of [3, 10, 20]) {
    for (const isChoiceMode of [false, true]) {
      let state = createChallenge(count)
      for (let i = 0; i < count; i++) state = recordQuestion(state, { correct: true, clipsUsed: 1, isChoiceMode })
      const summary = generateSummary(state)
      assert.equal(summary.grade, 'S')
      assert.equal(summary.maxPossible, count * (isChoiceMode ? 100 : 150))
    }
  }
})

test('mixed input modes use the sum of each question maximum, including wrong answers', () => {
  let state = createChallenge(3)
  for (const correct of [true, false]) state = recordQuestion(state, { correct, clipsUsed: 1, isChoiceMode: true })
  state = recordQuestion(state, { correct: true, clipsUsed: 1, isChoiceMode: false })
  assert.equal(generateSummary(state).maxPossible, 350)
  assert.equal(generateSummary(state).grade, 'B')
})

test('an exhausted exclusion pool never repeats an operator', () => {
  assert.equal(selectRandomOperator([{ name: 'A' }], null, ['A']), null)
})

test('Worker cache misses return proxied audio with CORS and cache it', async t => {
  let saved
  t.mock.method(globalThis, 'fetch', async () => new Response('audio bytes', { headers: { 'Content-Type': 'audio/wav' } }))
  const previous = globalThis.caches
  globalThis.caches = { default: { match: async () => undefined, put: async (_key, value) => { saved = value } } }
  t.after(() => { globalThis.caches = previous })
  const pending = []
  const response = await worker.fetch(new Request('https://proxy.example/audio/voice/test.wav'), {}, { waitUntil: p => pending.push(p) })
  assert.equal(response.status, 200)
  assert.equal(response.headers.get('Access-Control-Allow-Origin'), '*')
  assert.equal(await response.text(), 'audio bytes')
  await Promise.all(pending)
  assert.equal(await saved.text(), 'audio bytes')
})

test('Worker upstream failures retain CORS and are not cached', async t => {
  t.mock.method(globalThis, 'fetch', async () => new Response('unavailable', { status: 503 }))
  const previous = globalThis.caches
  globalThis.caches = { default: { match: async () => undefined, put: async () => assert.fail('must not cache errors') } }
  t.after(() => { globalThis.caches = previous })
  const response = await worker.fetch(new Request('https://proxy.example/audio/voice/test.wav'), {}, { waitUntil: () => {} })
  assert.equal(response.status, 503)
  assert.equal(response.headers.get('Access-Control-Allow-Origin'), '*')
})
