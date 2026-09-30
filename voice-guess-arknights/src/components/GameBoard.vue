<template>
  <div class="game-board">
    <div class="header">
      <div class="logo">🎧 语音猜干员</div>
      <div class="header-sub">听声音，猜干员</div>
      <div class="credit">数据来源<a href="https://prts.wiki" target="_blank">prts.wiki</a>，音频主要来自<a href="https://wiki.biligame.com/arknights" target="_blank">明日方舟BWiki</a>，感谢伟大的wiki及工作人员</div>
    </div>

    <!-- 挑战设置页面 -->
    <template v-if="showChallengeSetup">
      <div class="challenge-setup">
        <button class="back-btn" @click="showChallengeSetup = false">← 返回</button>
        <div class="setup-card">
          <h2 class="setup-title">🏆 挑战模式</h2>
          <p class="setup-desc">{{ settings.questionCount }}道题，看看你能拿多少分</p>

          <div class="setting-group">
            <div class="setting-label">输入模式</div>
            <div class="toggle-group">
              <button class="toggle-option" :class="{ active: settings.inputMode === 'typing' }" @click="settings.inputMode = 'typing'">输入模式</button>
              <button class="toggle-option" :class="{ active: settings.inputMode === 'choice' }" @click="settings.inputMode = 'choice'">选择模式</button>
            </div>
          </div>

          <div class="setting-group">
            <div class="setting-label">语音语言</div>
            <div class="check-group">
              <div class="check-item" :class="{ checked: settings.languages.includes('中文') }" @click="toggleLang('中文')">
                <div class="check-box">{{ settings.languages.includes('中文') ? '✓' : '' }}</div>
                中文配音
              </div>
              <div class="check-item" :class="{ checked: settings.languages.includes('日文') }" @click="toggleLang('日文')">
                <div class="check-box">{{ settings.languages.includes('日文') ? '✓' : '' }}</div>
                日文配音
              </div>
            </div>
          </div>

          <div class="setting-group">
            <div class="setting-label">干员星级</div>
            <div class="check-group">
              <div v-for="star in 6" :key="star" class="check-item" :class="{ checked: settings.selectedStars.includes(star) }" @click="toggleStar(star)">
                <div class="check-box">{{ settings.selectedStars.includes(star) ? '✓' : '' }}</div>
                {{ '★'.repeat(star) }}
              </div>
            </div>
          </div>

          <div class="setting-group">
            <div class="setting-label">题目数量</div>
            <div class="slider-container">
              <div class="slider-header">
                <span class="slider-desc">题数</span>
                <span class="slider-value">{{ settings.questionCount }}</span>
              </div>
              <input type="range" class="slider" min="3" max="20" v-model.number="settings.questionCount" />
              <div class="slider-labels"><span>3</span><span>11</span><span>20</span></div>
            </div>
          </div>

          <div class="setting-group">
            <div class="setting-label">每题最大猜测次数</div>
            <div class="slider-container">
              <div class="slider-header">
                <span class="slider-desc">总次数上限</span>
                <span class="slider-value">{{ settings.maxGuesses }}</span>
              </div>
              <input type="range" class="slider" min="3" max="30" v-model.number="settings.maxGuesses" />
              <div class="slider-labels"><span>3</span><span>15</span><span>30</span></div>
            </div>
          </div>

          <div class="setting-group">
            <div class="setting-label">猜几次后播下一条语音</div>
            <div class="slider-container">
              <div class="slider-header">
                <span class="slider-desc">每条次数</span>
                <span class="slider-value">{{ settings.guessesPerClip }}</span>
              </div>
              <input type="range" class="slider" min="1" max="10" v-model.number="settings.guessesPerClip" />
              <div class="slider-labels"><span>1</span><span>5</span><span>10</span></div>
            </div>
          </div>

          <div class="setting-group">
            <div class="setting-label">语音类型</div>
            <div class="check-group">
              <div v-for="vt in voiceTypesList" :key="vt" class="check-item" :class="{ checked: settings.voiceTypes.includes(vt) }" @click="toggleVoiceType(vt)">
                <div class="check-box">{{ settings.voiceTypes.includes(vt) ? '✓' : '' }}</div>
                {{ vt }}
              </div>
            </div>
          </div>

          <button class="start-btn" :disabled="checkingChallenge" @click="startChallenge">{{ checkingChallenge ? '检查题目中...' : '开始挑战' }}</button>
          <div v-if="setupError" class="setup-error">⚠️ {{ setupError }}</div>
        </div>
      </div>
    </template>

    <!-- 主页面 -->
    <template v-else>
      <div class="top-controls">
        <button class="ctrl-btn" :class="{ active: settings.inputMode === 'typing' }" @click="settings.inputMode = settings.inputMode === 'typing' ? 'choice' : 'typing'">
          ⌨ {{ settings.inputMode === 'typing' ? '输入模式' : '选择模式' }}
        </button>
        <button class="ctrl-btn text-toggle" :class="{ active: showText }" @click="showText = !showText">
          {{ showText ? '文本 开' : '文本' }}
        </button>
        <button class="ctrl-btn" @click="showChallengeSetup = true">🏆 挑战</button>
        <button class="ctrl-btn" @click="showSettings = true">⚙ 设置</button>
      </div>

      <div v-if="loading" class="loading-state">
        <div class="loading-text">加载中...</div>
      </div>
      <div v-else-if="questionError" class="setup-error" role="alert">
        {{ questionError }}
        <button class="ctrl-btn" @click="startNewQuestion">重试</button>
      </div>

      <template v-else>
        <ChallengeBar v-if="inChallenge" :streak="challenge.streak" :score="challenge.score" :current="challenge.currentQuestion" :total="challenge.totalQuestions" />

        <SummaryReport v-if="inChallenge && challenge.isComplete && showSummary" v-bind="summaryData" @restart="showChallengeSetup = true" />

        <template v-else-if="currentQuestion">
          <!-- 显示所有已加载的语音 -->
          <div v-for="(clip, idx) in displayedClips" :key="'clip-' + idx" class="clip-wrapper">
            <AudioPlayer
              :url="clip.url"
              :alt="clip.alt || ''"
              :language="clip.language"
              :voiceType="clip.type"
              :clipIndex="idx + 1"
              :guessesLeft="idx === displayedClips.length - 1 ? guessesLeftForClip : 0"
              :text="showText ? (clip.text || '') : ''"
              :active="idx === displayedClips.length - 1"
              @skip="onAudioSkip(idx)"
            />
          </div>

          <!-- 猜对时卡片显示在语音和选项中间 -->
          <ResultCard v-if="showResult" :operator="currentQuestion.operator" :correct="lastGuessCorrect" :clipsUsed="currentClipIndex" :isLast="inChallenge && challenge.isComplete" @next="nextQuestion" />

          <!-- 未猜对时显示输入 -->
          <template v-if="!showResult">
            <GuessInput v-if="settings.inputMode === 'typing'" v-model="guessText" :operators="operators" :history="currentHistory" :disabled="showResult" @submit="onGuess" ref="guessInputRef" />
            <ChoiceMode v-else :choices="currentChoices" :history="currentHistory" @select="onGuess" />
          </template>
        </template>
      </template>
    </template>

    <footer class="site-footer">
      <nav class="creator-links" aria-label="创作者链接">
        <a href="https://space.bilibili.com/389249150" target="_blank" rel="noopener noreferrer">B站</a>
        <a href="https://www.douyin.com/user/MS4wLjABAAAA10EENdMMtzEytWZPzF2JCIGRJuP30J1V7nXfERlqHH4" target="_blank" rel="noopener noreferrer">抖音</a>
        <a href="https://github.com/CoConuts-Milk0325/arknights-operator-guess" target="_blank" rel="noopener noreferrer">GitHub</a>
      </nav>
    </footer>

    <SettingsDrawer
      v-model="showSettings"
      v-model:inputMode="settings.inputMode"
      v-model:languages="settings.languages"
      v-model:selectedStars="settings.selectedStars"
      v-model:maxGuesses="settings.maxGuesses"
      v-model:guessesPerClip="settings.guessesPerClip"
      v-model:selectedVoiceTypes="settings.voiceTypes"
      @confirm="onSettingsConfirm"
    />
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch, nextTick } from 'vue'
import { loadOperators, searchOperators } from '../logic/operatorSearch.js'
import { getCached, setCache } from '../cache.js'
import { selectRandomOperator, getVoiceClips, generateChoices, getAvatarUrl } from '../logic/gameEngine.js'
import { createChallenge, recordQuestion, generateSummary } from '../logic/challenge.js'
import { buildVoiceUrl, preloadAudio } from '../logic/audioLoader.js'
import { VOICE_TYPES } from '../utils/constants.js'
import { DATA_VERSION } from '../dataVersion.js'

import AudioPlayer from './AudioPlayer.vue'
import GuessInput from './GuessInput.vue'
import ChoiceMode from './ChoiceMode.vue'
import ResultCard from './ResultCard.vue'
import SettingsDrawer from './SettingsDrawer.vue'
import ChallengeBar from './ChallengeBar.vue'
import SummaryReport from './SummaryReport.vue'

const loading = ref(true)
const questionError = ref('')
const operators = ref([])
const showSettings = ref(false)
const showText = ref(false)
const showChallengeSetup = ref(false)
const guessText = ref('')
const guessInputRef = ref(null)
const inChallenge = ref(false)
const lastOperatorName = ref(null)
const targetOperator = ref(null)
const audioKey = ref(0)

const voiceTypesList = VOICE_TYPES

const settings = reactive({
  inputMode: 'choice',
  languages: ['中文', '日文'],
  selectedStars: [1, 2, 3, 4, 5, 6],
  maxGuesses: 10,
  guessesPerClip: 3,
  questionCount: 10,
  voiceTypes: [...VOICE_TYPES]
})

const challenge = ref(createChallenge())
const showSummary = ref(false)
const checkingChallenge = ref(false)
const availabilityError = ref('')
const availabilityErrorSnapshot = ref('')

const setupError = computed(() => {
  const available = getFilteredOperators().length
  if (available < settings.questionCount) {
    return `可用干员不足：当前筛选后仅 ${available} 个干员，需要 ${settings.questionCount} 个`
  }
  return availabilityErrorSnapshot.value === challengeAvailabilitySnapshot() ? availabilityError.value : ''
})

const currentQuestion = ref(null)
const currentClipIndex = ref(1)
const currentClips = ref([])
const currentChoices = ref([])
const currentHistory = ref([])
const showResult = ref(false)
const lastGuessCorrect = ref(false)
const questionGuessCount = ref(0)
const questionStartTime = ref(0)

const preloadedQuestion = ref(null)
const preloadSettingsSnapshot = ref('')
let preloadEpoch = 0

const currentClip = computed(() => {
  return currentClips.value[currentClipIndex.value - 1] || null
})

// 显示所有已加载的语音（递进式）
const displayedClips = computed(() => {
  return currentClips.value.slice(0, currentClipIndex.value)
})

const guessesLeftForClip = computed(() => {
  return Math.max(0, settings.guessesPerClip - (questionGuessCount.value % settings.guessesPerClip))
})

const summaryData = computed(() => generateSummary(challenge.value))

// Load voice index (small file)
onMounted(async () => {
  try {
    operators.value = await loadOperators()
    // Index file loaded - voice data loaded on-demand per operator
  } catch (e) {
    console.error('Failed to load data:', e)
  } finally {
    loading.value = false
    resolveTargetOperator()
    startNewQuestion()
  }
})

// Parse ?target=xxx from URL and resolve to an operator
function resolveTargetOperator() {
  const params = new URLSearchParams(window.location.search)
  const target = params.get('target')
  if (!target) return
  const matches = searchOperators(target, operators.value)
  if (matches.length) {
    targetOperator.value = matches[0]
    console.log('Target operator:', targetOperator.value.name)
  }
}

// 校验缓存语音数据是否完整（防止因缓存了旧版缺失文本的数据而无法展示）
function isValidVoiceData(data) {
  if (!data || typeof data !== 'object') return false
  if (data['日文']) {
    let hasClips = false
    let hasAnyText = false
    for (const type in data['日文']) {
      const list = data['日文'][type]
      if (Array.isArray(list) && list.length > 0) {
        hasClips = true
        if (list.some(clip => clip && typeof clip.text === 'string' && clip.text.trim().length > 0)) {
          hasAnyText = true
          break
        }
      }
    }
    if (hasClips && !hasAnyText) {
      return false
    }
  }
  return true
}

// Load voice data for a specific operator (on-demand)
async function loadOperatorVoices(operatorName) {
  const cacheKey = `voice-${operatorName}`
  const cached = getCached(cacheKey)
  if (cached && isValidVoiceData(cached)) return cached

  try {
    const resp = await fetch(`./data/voices/${encodeURIComponent(operatorName)}.json?v=${DATA_VERSION}`)
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    const data = await resp.json()
    setCache(cacheKey, data)
    return data
  } catch (e) {
    console.error(`Failed to load voice data for ${operatorName}:`, e)
    return null
  }
}

function toggleLang(lang) {
  const idx = settings.languages.indexOf(lang)
  if (idx >= 0) {
    if (settings.languages.length > 1) settings.languages.splice(idx, 1)
  } else {
    settings.languages.push(lang)
  }
}

function toggleVoiceType(vt) {
  const idx = settings.voiceTypes.indexOf(vt)
  if (idx >= 0) settings.voiceTypes.splice(idx, 1)
  else settings.voiceTypes.push(vt)
}

function toggleStar(star) {
  const idx = settings.selectedStars.indexOf(star)
  if (idx >= 0) {
    if (settings.selectedStars.length > 1) settings.selectedStars.splice(idx, 1)
  } else {
    settings.selectedStars.push(star)
  }
}

function challengeAvailabilitySnapshot() {
  return `${settingsSnapshot()}|${settings.questionCount}`
}

async function startChallenge() {
  if (checkingChallenge.value || getFilteredOperators().length < settings.questionCount) return
  checkingChallenge.value = true
  availabilityError.value = ''
  availabilityErrorSnapshot.value = ''
  const snapshot = challengeAvailabilitySnapshot()
  let available = 0
  try {
    const candidates = getFilteredOperators()
    // Check only as many shards as needed, in small batches to limit concurrent requests.
    for (let i = 0; i < candidates.length && available < settings.questionCount; i += 8) {
      const playable = await Promise.all(candidates.slice(i, i + 8).map(async op => {
        const voiceData = await loadOperatorVoices(op.name)
        if (!voiceData) return false
        return getVoiceClips(op.name, { [op.name]: voiceData }, settings)
          .some(clip => typeof clip.url === 'string' && clip.url.trim())
      }))
      if (snapshot !== challengeAvailabilitySnapshot() || !showChallengeSetup.value) return
      available += playable.filter(Boolean).length
    }
    if (available < settings.questionCount) {
      availabilityErrorSnapshot.value = snapshot
      availabilityError.value = `可用干员不足：当前语音筛选后仅 ${available} 个干员有可播放语音，需要 ${settings.questionCount} 个；也请检查网络后重试。`
      return
    }
    inChallenge.value = true
    showChallengeSetup.value = false
    showSummary.value = false
    challenge.value = createChallenge(settings.questionCount)
    startNewQuestion()
  } finally {
    checkingChallenge.value = false
  }
}

function onSettingsConfirm() {
  showSettings.value = false
  // Keep the current challenge question; a fresh question would consume an operator without recording a result.
  if (!inChallenge.value || questionError.value || !currentQuestion.value) startNewQuestion()
}

// Filter operators by star rating
function getFilteredOperators() {
  return operators.value.filter(op => {
    const rarity = parseInt(op.rarity) || 0
    return settings.selectedStars.includes(rarity + 1)
  })
}

async function startNewQuestion() {
  const epoch = ++preloadEpoch
  loading.value = true
  questionError.value = ''
  if (!operators.value.length) {
    try {
      const data = await loadOperators()
      if (epoch !== preloadEpoch) return
      operators.value = data
      resolveTargetOperator()
    } catch {
      if (epoch === preloadEpoch) {
        questionError.value = '干员数据加载失败，请检查网络后重试。'
        loading.value = false
      }
      return
    }
  }
  const filteredOperators = getFilteredOperators()

  // Try to reuse the preloaded next question (discard if settings changed meanwhile)
  const snapshot = settingsSnapshot()
  const candidate = preloadedQuestion.value && preloadSettingsSnapshot.value === snapshot
    ? preloadedQuestion.value
    : null
  preloadedQuestion.value = null
  preloadSettingsSnapshot.value = ''

  // Use target operator from URL if set (and it passes star filter), otherwise reuse preload or pick random
  const exclude = new Set(inChallenge.value ? challenge.value.usedOperators : [])
  try {
    // Each candidate is attempted at most once. Empty selections cannot recurse forever.
    while (true) {
      const eligible = filteredOperators.filter(op => !exclude.has(op.name))
      const target = targetOperator.value
      const op = target && eligible.some(o => o.name === target.name)
        ? target
        : candidate && eligible.some(o => o.name === candidate.operator.name)
          ? candidate.operator
          : selectRandomOperator(eligible, lastOperatorName.value)
      if (!op) break
      exclude.add(op.name)
      const question = candidate?.operator.name === op.name ? candidate : await prepareQuestion(op)
      if (epoch !== preloadEpoch) return
      if (snapshot !== settingsSnapshot()) return startNewQuestion()
      if (!question) continue
      lastOperatorName.value = op.name
      applyQuestion(question)
      preloadNextQuestion()
      return
    }
    currentQuestion.value = null
    questionError.value = '当前筛选下没有可用的新题目，请调整语音类型或星级；若加载失败，请重试。'
  } finally {
    if (epoch === preloadEpoch) loading.value = false
  }
}

function settingsSnapshot() {
  return JSON.stringify({
    inputMode: settings.inputMode,
    maxGuesses: settings.maxGuesses,
    languages: [...settings.languages].sort(),
    stars: [...settings.selectedStars].sort(),
    voiceTypes: [...settings.voiceTypes].sort()
  })
}

async function prepareQuestion(op) {
  const voiceData = await loadOperatorVoices(op.name)
  if (!voiceData) return null

  const clips = getVoiceClips(op.name, { [op.name]: voiceData }, settings)
    .filter(clip => typeof clip.url === 'string' && clip.url.trim())
  if (!clips.length) return null
  const numChoices = settings.inputMode === 'choice' ? settings.maxGuesses : 4
  const choices = generateChoices(op, getFilteredOperators(), numChoices)

  return {
    operator: op,
    clips,
    choices
  }
}

function applyQuestion(question) {
  if (inChallenge.value && !challenge.value.usedOperators.includes(question.operator.name)) {
    challenge.value.usedOperators.push(question.operator.name)
  }
  currentQuestion.value = { operator: question.operator }
  currentClips.value = question.clips
  currentClipIndex.value = 1
  currentChoices.value = question.choices
  currentHistory.value = []
  showResult.value = false
  lastGuessCorrect.value = false
  questionGuessCount.value = 0
  questionStartTime.value = Date.now()
  guessText.value = ''
  audioKey.value++

  nextTick(() => {
    guessInputRef.value?.focus()
  })
}

// Pre-generate the next question and preload its first clip while guessing the current one
async function preloadNextQuestion() {
  if (targetOperator.value) return
  if (inChallenge.value && challenge.value.currentQuestion >= challenge.value.totalQuestions - 1) return
  if (!currentQuestion.value) return

  const filteredOperators = getFilteredOperators()
  const exclude = inChallenge.value ? challenge.value.usedOperators : []
  const op = selectRandomOperator(filteredOperators, currentQuestion.value.operator.name, exclude)
  if (!op) return

  const epoch = preloadEpoch
  const snapshot = settingsSnapshot()
  const question = await prepareQuestion(op)

  // Discard if a new question started or settings changed while we were preparing
  if (epoch !== preloadEpoch) return
  if (snapshot !== settingsSnapshot()) return
  if (!question) return

  preloadedQuestion.value = question
  preloadSettingsSnapshot.value = snapshot

  const firstClip = question.clips[0]
  if (firstClip?.url) preloadAudio(buildVoiceUrl(firstClip.url))
}

function onGuess(name) {
  if (showResult.value || loading.value || !currentQuestion.value) return
  if (questionGuessCount.value >= settings.maxGuesses) {
    finishQuestion(false, currentHistory.value.at(-1)?.name || '')
    return
  }

  const correct = name === currentQuestion.value.operator.name
  questionGuessCount.value++

  currentHistory.value.push({ name, correct })

  if (correct) {
    finishQuestion(true, name)
  } else {
    if (questionGuessCount.value >= settings.maxGuesses) {
      finishQuestion(false, name)
    } else if (questionGuessCount.value % settings.guessesPerClip === 0 && currentClipIndex.value < currentClips.value.length) {
      currentClipIndex.value++
      audioKey.value++
    }

    guessText.value = ''
  }
}

function finishQuestion(correct, guessed) {
  if (showResult.value || !currentQuestion.value) return
  lastGuessCorrect.value = correct
  showResult.value = true
  if (inChallenge.value) {
    const timeUsed = Math.round((Date.now() - questionStartTime.value) / 1000)
    challenge.value = recordQuestion(challenge.value, {
      operatorName: currentQuestion.value.operator.name,
      guessed,
      correct,
      clipsUsed: currentClipIndex.value,
      language: currentClip.value?.language || '中文',
      timeUsed: `${timeUsed}s`,
      isChoiceMode: settings.inputMode === 'choice',
      avatarUrl: getAvatarUrl(currentQuestion.value.operator)
    })
  }
}

function nextQuestion() {
  if (inChallenge.value && challenge.value.isComplete) {
    showSummary.value = true
    return
  }
  startNewQuestion()
}

function onAudioSkip(index) {
  if (loading.value || showResult.value || index !== currentClipIndex.value - 1) return
  // 语音加载失败，自动跳到下一条
  if (currentClipIndex.value < currentClips.value.length) {
    currentClipIndex.value++
    audioKey.value++
  }
}

// 输入模式和猜测上限实时影响当前题，保持选项数与次数限制一致。
watch([() => settings.inputMode, () => settings.maxGuesses], () => {
  if (currentQuestion.value && !showResult.value && !loading.value) {
    if (questionGuessCount.value >= settings.maxGuesses) {
      finishQuestion(false, currentHistory.value.at(-1)?.name || '')
      return
    }
    const filteredOperators = getFilteredOperators()
    const numChoices = settings.inputMode === 'choice' ? settings.maxGuesses : 4
    currentChoices.value = generateChoices(currentQuestion.value.operator, filteredOperators, numChoices)
  }
})
</script>

<style scoped>
.game-board { position: relative; z-index: 1; max-width: 440px; margin: 0 auto; min-height: 100vh; padding: 24px 20px; display: flex; flex-direction: column; }
.header { text-align: center; padding: 8px 0 20px; }
.logo { font-family: var(--font-display); font-weight: 800; font-size: 30px; letter-spacing: -0.5px; }
.header-sub { font-size: 13px; color: var(--text-secondary); margin-top: 4px; }
.credit { font-size: 11px; color: var(--text-muted); margin-top: 8px; }
.credit a { color: var(--accent); text-decoration: none; }
.credit a:hover { text-decoration: underline; }
.top-controls { display: flex; justify-content: center; gap: 8px; margin-bottom: 20px; flex-wrap: wrap; }
.ctrl-btn { display: flex; align-items: center; gap: 6px; padding: 8px 16px; background: var(--bg-white); border: 1.5px solid var(--border); border-radius: var(--r-full); font-family: var(--font-body); font-size: 13px; font-weight: 500; color: var(--text-secondary); cursor: pointer; transition: all 0.2s; box-shadow: var(--shadow-sm); }
.ctrl-btn:hover { border-color: var(--accent); color: var(--accent); }
.ctrl-btn.active { background: var(--accent); border-color: var(--accent); color: white; }
.text-toggle { font-size: 14px; padding: 8px 12px; }
.loading-state { display: flex; justify-content: center; align-items: center; min-height: 200px; }
.loading-text { font-size: 16px; color: var(--text-muted); }

.clip-wrapper {
  margin-bottom: 12px;
}
.site-footer { margin-top: auto; padding-top: 32px; }
.creator-links { display: flex; justify-content: center; align-items: center; flex-wrap: wrap; gap: 16px; padding-top: 12px; border-top: 1px solid var(--border); font-size: 12px; line-height: 1.5; }
.creator-links a { padding: 5px 0; color: var(--text-secondary); text-decoration: underline; text-decoration-color: var(--border); text-underline-offset: 4px; }
.creator-links a:hover { color: var(--accent); text-decoration-color: currentColor; }
.creator-links a:focus-visible { outline: 2px solid var(--accent); outline-offset: 4px; border-radius: 2px; }
.challenge-setup { flex: 1; }
.back-btn { display: flex; align-items: center; gap: 4px; padding: 8px 16px; background: none; border: none; font-family: var(--font-body); font-size: 14px; color: var(--text-secondary); cursor: pointer; margin-bottom: 16px; transition: color 0.2s; }
.back-btn:hover { color: var(--accent); }
.setup-card { background: var(--bg-white); border-radius: var(--r-lg); padding: 28px; box-shadow: var(--shadow-lg); }
.setup-title { font-family: var(--font-display); font-size: 22px; font-weight: 700; text-align: center; margin-bottom: 4px; }
.setup-desc { text-align: center; color: var(--text-secondary); font-size: 13px; margin-bottom: 24px; }
.setting-group { margin-bottom: 20px; }
.setting-label { font-size: 13px; font-weight: 600; color: var(--text-secondary); margin-bottom: 8px; }
.toggle-group { display: flex; background: var(--bg-warm); border-radius: var(--r-md); padding: 4px; gap: 4px; }
.toggle-option { flex: 1; padding: 10px; border-radius: var(--r-sm); border: none; background: transparent; font-family: var(--font-body); font-size: 13px; font-weight: 500; color: var(--text-secondary); cursor: pointer; transition: all 0.2s; text-align: center; }
.toggle-option.active { background: white; color: var(--text); box-shadow: var(--shadow-sm); font-weight: 600; }
.check-group { display: flex; gap: 8px; flex-wrap: wrap; }
.check-item { display: flex; align-items: center; gap: 8px; padding: 8px 14px; background: var(--bg-warm); border-radius: var(--r-sm); cursor: pointer; transition: all 0.2s; font-size: 13px; font-weight: 500; color: var(--text-secondary); border: 1.5px solid transparent; user-select: none; }
.check-item:hover { background: white; }
.check-item.checked { background: var(--accent-light); color: var(--accent); border-color: var(--accent); }
.check-box { width: 18px; height: 18px; border-radius: 5px; border: 2px solid var(--border); display: flex; align-items: center; justify-content: center; font-size: 11px; transition: all 0.2s; flex-shrink: 0; }
.check-item.checked .check-box { background: var(--accent); border-color: var(--accent); color: white; }
.slider-container { background: var(--bg-warm); border-radius: var(--r-md); padding: 16px; }
.slider-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.slider-desc { font-size: 13px; color: var(--text-secondary); }
.slider-value { font-family: var(--font-display); font-size: 24px; font-weight: 700; color: var(--accent); }
.slider-labels { display: flex; justify-content: space-between; font-size: 11px; color: var(--text-muted); margin-top: 8px; }
.slider { -webkit-appearance: none; width: 100%; height: 6px; background: var(--border); border-radius: 3px; outline: none; }
.slider::-webkit-slider-thumb { -webkit-appearance: none; width: 24px; height: 24px; border-radius: 50%; background: var(--accent); cursor: pointer; box-shadow: 0 2px 8px rgba(232,101,42,0.3); border: 3px solid white; transition: transform 0.15s; }
.slider::-webkit-slider-thumb:hover { transform: scale(1.15); }
.start-btn { width: 100%; margin-top: 8px; padding: 14px; background: var(--accent); color: white; border: none; border-radius: var(--r-md); font-family: var(--font-body); font-size: 16px; font-weight: 600; cursor: pointer; transition: all 0.2s; box-shadow: 0 4px 12px rgba(232,101,42,0.2); }
.start-btn:hover { background: var(--accent-hover); box-shadow: 0 6px 20px rgba(232,101,42,0.3); transform: translateY(-1px); }
.setup-error { margin-top: 12px; padding: 10px 14px; background: #fef2f2; border: 1px solid #fecaca; color: var(--red); border-radius: var(--r-md); font-size: 13px; font-weight: 500; text-align: center; }
</style>
