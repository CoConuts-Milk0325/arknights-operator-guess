<template>
  <div class="audio-card">
    <div class="audio-header">
      <span class="audio-clip-label">第 {{ clipIndex }} 条语音</span>
      <span class="audio-lang-badge" :class="languageClass">{{ language }}</span>
    </div>
    <div class="player">
      <button class="play-btn" @click="togglePlay">
        {{ isPlaying ? '⏸' : '▶' }}
      </button>
      <div class="progress-track" @click="seek">
        <div class="progress-fill" :style="{ width: progressPercent + '%' }"></div>
      </div>
      <span class="time-label">{{ formatTime(currentTime) }}</span>
    </div>
    <div class="audio-footer">
      <span class="load-status" :class="isLoaded ? 'status-loaded' : 'status-loading'">
        <span class="status-icon"></span>
      </span>
      <span class="voice-type">{{ voiceType }}</span>
      <span class="guesses-left" v-if="guessesLeft > 0">
        还可猜 <strong>{{ guessesLeft }}</strong> 次
      </span>
    </div>
    <div v-if="text" class="voice-text">
      <div class="voice-text-content">「{{ text }}」</div>
    </div>
    <div v-if="loadError" class="voice-error">
      <span class="error-icon">⚠️</span>
      <span class="error-text">{{ loadError }}</span>
      <button class="retry-btn" @click="retryAudio">重试语音</button>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onUnmounted } from 'vue'
import { buildVoiceUrl } from '../logic/audioLoader.js'
import { getFallbackUrl } from '../config.js'

const props = defineProps({
  url: { type: String, required: true },
  alt: { type: String, default: '' },
  language: { type: String, default: '中文' },
  voiceType: { type: String, default: '' },
  clipIndex: { type: Number, default: 1 },
  guessesLeft: { type: Number, default: 3 },
  text: { type: String, default: '' },
  active: { type: Boolean, default: true }
})

const emit = defineEmits(['loaded', 'error', 'skip'])

const isPlaying = ref(false)
const currentTime = ref(0)
const duration = ref(0)
const progressPercent = ref(0)
const languageClass = ref('')
const loadError = ref('')
const isLoaded = ref(false)

let myAudio = null
let progressInterval = null
let playRequested = false
let playGeneration = 0

watch(() => props.language, (lang) => {
  languageClass.value = lang === '中文' ? 'lang-zh' : 'lang-jp'
}, { immediate: true })

// When this clip becomes inactive, pause audio
watch(() => props.active, (isActive) => {
  if (!isActive && playRequested && myAudio) {
    playRequested = false
    playGeneration++
    myAudio.pause()
    isPlaying.value = false
    stopProgress()
  }
})

watch(() => props.url, loadClip, { immediate: true })

function loadClip(newUrl) {
  stopMyAudio()
  isPlaying.value = false
  currentTime.value = 0
  duration.value = 0
  progressPercent.value = 0
  loadError.value = ''
  isLoaded.value = false

  if (!newUrl) {
    loadError.value = '无语音URL'
    return
  }

  const fullUrl = buildVoiceUrl(newUrl)
  const fallbackUrl = getFallbackUrl({ alt: props.alt })
  let usedFallback = false
  let failed = false

  try {
    const audio = new Audio()
    myAudio = audio
    audio.preload = 'auto'

    // 监听 duration 变化（用于进度条，不参与加载成败判定）
    const onDurationChange = () => {
      if (audio !== myAudio) return
      const dur = audio.duration
      if (Number.isFinite(dur) && dur > 0) duration.value = dur
    }
    audio.addEventListener('durationchange', onDurationChange)
    audio.addEventListener('loadedmetadata', onDurationChange)

    // 不阻塞等待任何加载事件：302/206 流式加载下
    // canplay/canplaythrough/loadedmetadata 都可能延迟或不触发，
    // 浏览器会在用户点击播放时自行处理缓冲。真正失败由 error 事件兜底。
    audio.addEventListener('error', () => {
      if (audio !== myAudio || failed) return
      const code = audio.error?.code
      // 主源网络或解码失败时回退到 PRTS 备用直链。
      if (!usedFallback && fallbackUrl && (code === 2 || code === 3 || code === 4)) {
        usedFallback = true
        isPlaying.value = false
        stopProgress()
        audio.src = fallbackUrl
        audio.load()
        if (playRequested) playCurrentAudio()
        return
      }
      if (code === 2 || code === 3 || code === 4) {
        failed = true
        failAudio()
      }
      // 1=ABORTED 可能由主动暂停或切源引起，不按资源失败处理。
    })

    audio.src = fullUrl

    isLoaded.value = true
    emit('loaded')
  } catch (e) {
    failAudio()
  }
}

function failAudio() {
  playRequested = false
  playGeneration++
  myAudio?.pause()
  isPlaying.value = false
  isLoaded.value = false
  stopProgress()
  loadError.value = '语音加载失败，可重试'
  if (props.active) emit('skip')
}

function retryAudio() {
  loadClip(props.url)
  if (myAudio) {
    playRequested = true
    playCurrentAudio()
  }
}

function togglePlay() {
  if (!myAudio) return

  if (playRequested && !loadError.value) {
    playRequested = false
    playGeneration++
    myAudio.pause()
    isPlaying.value = false
    stopProgress()
  } else {
    playRequested = true
    loadError.value = ''
    playCurrentAudio()
  }
}

function playCurrentAudio() {
  const audio = myAudio
  const generation = ++playGeneration
  audio.play().then(() => {
    if (audio !== myAudio || generation !== playGeneration) return
    loadError.value = ''
    isPlaying.value = true
    startProgress()
  }).catch(() => {
    if (audio !== myAudio || generation !== playGeneration) return
    isPlaying.value = false
    stopProgress()
    loadError.value = '播放失败，请点击页面后重试'
  })
}

function startProgress() {
  stopProgress()
  progressInterval = setInterval(() => {
    if (!myAudio) return
    currentTime.value = myAudio.currentTime
    const dur = myAudio.duration
    if (Number.isFinite(dur) && dur > 0) duration.value = dur
    progressPercent.value = duration.value > 0 ? (currentTime.value / duration.value) * 100 : 0

    if (myAudio.ended) {
      playRequested = false
      isPlaying.value = false
      stopProgress()
    }
  }, 100)
}

function stopProgress() {
  if (progressInterval) {
    clearInterval(progressInterval)
    progressInterval = null
  }
}

function stopMyAudio() {
  stopProgress()
  playRequested = false
  playGeneration++
  if (myAudio) {
    myAudio.pause()
    myAudio.currentTime = 0
    myAudio.removeAttribute('src')
    myAudio.load()
    myAudio = null
  }
}

function seek(e) {
  if (!myAudio) return
  const rect = e.currentTarget.getBoundingClientRect()
  const percent = (e.clientX - rect.left) / rect.width
  myAudio.currentTime = percent * (Number.isFinite(myAudio.duration) ? myAudio.duration : 0)
}

function formatTime(seconds) {
  if (!Number.isFinite(seconds) || seconds <= 0) return '--:--'
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${String(s).padStart(2, '0')}`
}

onUnmounted(() => {
  stopMyAudio()
})
</script>

<style scoped>
.audio-card {
  background: var(--bg-white);
  border-radius: var(--r-lg);
  padding: 24px;
  box-shadow: var(--shadow-md);
  margin-bottom: 16px;
  position: relative;
  overflow: hidden;
}

.audio-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 4px;
  background: linear-gradient(90deg, var(--accent), #f59e0b);
  border-radius: var(--r-lg) var(--r-lg) 0 0;
}

.audio-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.audio-clip-label {
  font-family: var(--font-display);
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
}

.audio-lang-badge {
  padding: 4px 12px;
  border-radius: var(--r-full);
  font-size: 12px;
  font-weight: 500;
}

.lang-zh {
  background: var(--blue-light);
  color: var(--blue);
}

.lang-jp {
  background: #fdf2f8;
  color: #db2777;
}

.player {
  display: flex;
  align-items: center;
  gap: 14px;
}

.play-btn {
  width: 52px;
  height: 52px;
  border-radius: 50%;
  border: none;
  background: var(--accent);
  color: white;
  font-size: 18px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
  box-shadow: 0 4px 12px rgba(232, 101, 42, 0.3);
  flex-shrink: 0;
}

.play-btn:hover {
  transform: scale(1.05);
  box-shadow: 0 6px 20px rgba(232, 101, 42, 0.4);
}

.play-btn:active {
  transform: scale(0.97);
}

.progress-track {
  flex: 1;
  height: 6px;
  background: var(--border-light);
  border-radius: 3px;
  overflow: hidden;
  cursor: pointer;
}

.progress-fill {
  height: 100%;
  background: var(--accent);
  border-radius: 3px;
  transition: width 0.1s linear;
}

.time-label {
  font-family: var(--font-display);
  font-size: 13px;
  color: var(--text-muted);
  font-weight: 500;
  min-width: 36px;
  text-align: right;
}

.audio-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 14px;
  gap: 6px;
}

.load-status {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  flex-shrink: 0;
}

.status-icon {
  display: block;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  position: relative;
}

/* 加载中：旋转边框 */
.status-loading .status-icon {
  border: 2px solid var(--border);
  border-top-color: var(--accent);
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* 加载完：圆圈加对号 */
.status-loaded .status-icon {
  background: var(--accent);
}

.status-loaded .status-icon::after {
  content: '';
  position: absolute;
  top: 2px;
  left: 4px;
  width: 4px;
  height: 7px;
  border: solid white;
  border-width: 0 2px 2px 0;
  transform: rotate(45deg);
}

.voice-type {
  font-size: 12px;
  color: var(--text-muted);
  font-weight: 500;
}

.guesses-left {
  font-size: 12px;
  color: var(--text-secondary);
  font-weight: 500;
}

.guesses-left strong {
  color: var(--accent);
  font-weight: 700;
}

.voice-text {
  margin-top: 14px;
  padding: 12px 16px;
  background: var(--bg-warm);
  border-radius: var(--r-md);
  border-left: 3px solid var(--accent);
}

.voice-text-content {
  font-size: 14px;
  color: var(--text-secondary);
  line-height: 1.6;
  font-style: italic;
}

.voice-error {
  margin-top: 12px;
  padding: 10px 14px;
  background: var(--red-light);
  border-radius: var(--r-sm);
  border-left: 3px solid var(--red);
  display: flex;
  align-items: center;
  gap: 8px;
}

.error-icon {
  font-size: 14px;
}

.error-text {
  font-size: 12px;
  color: var(--red);
  font-weight: 500;
}

.retry-btn {
  flex-shrink: 0;
  margin-left: auto;
  border: 1px solid var(--red);
  border-radius: var(--r-sm);
  background: transparent;
  color: var(--red);
  padding: 4px 8px;
  cursor: pointer;
}
</style>
