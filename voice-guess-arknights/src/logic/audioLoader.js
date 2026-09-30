import { getAudioUrl } from '../config.js'

const cache = new Map()
const MAX_CACHE_SIZE = 8
let currentAudio = null

/**
 * Build audio URL through configured proxy
 */
export function buildVoiceUrl(relativePath) {
  return getAudioUrl(relativePath)
}

/**
 * Load audio through backend proxy with caching
 */
export function loadAudio(url) {
  // Stop previous audio but don't clear currentAudio reference yet
  if (currentAudio) {
    currentAudio.pause()
    currentAudio.currentTime = 0
  }

  return new Promise((resolve, reject) => {
    const audio = new Audio()
    audio.preload = 'auto'

    audio.addEventListener('canplaythrough', () => {
      currentAudio = audio
      resolve(audio)
    }, { once: true })

    audio.addEventListener('error', (e) => {
      console.error('Audio error:', url, e)
      reject(new Error(`Failed to load: ${url}`))
    }, { once: true })

    // Load from backend proxy (no cache busting - let backend handle caching)
    audio.src = url
    cache.set(url, audio)
  })
}

/**
 * Play audio
 */
export function playAudio(url) {
  return loadAudio(url).then(audio => {
    return audio.play()
  })
}

/**
 * Stop current audio
 */
export function stopAudio() {
  if (currentAudio) {
    currentAudio.pause()
    currentAudio.currentTime = 0
    currentAudio = null
  }
}

/**
 * Get current audio element
 */
export function getCurrentAudio() {
  return currentAudio
}

/**
 * Preload audio file
 */
export function preloadAudio(url) {
  if (cache.has(url)) return

  const audio = new Audio()
  audio.preload = 'auto'
  audio.src = url
  cache.set(url, audio)
  console.log('[preload]', url)

  // Bounded cache: evict oldest entries to avoid unbounded memory growth
  if (cache.size > MAX_CACHE_SIZE) {
    const oldest = cache.keys().next().value
    if (oldest !== url) cache.delete(oldest)
  }
}
