<template>
  <div>
    <div class="settings-overlay" :class="{ open: modelValue }" @click="$emit('update:modelValue', false)"></div>
    <div class="settings-drawer" :class="{ open: modelValue }">
      <div class="settings-handle"></div>
      <div class="settings-title">游戏设置</div>

      <div class="setting-group">
        <div class="setting-label">输入模式</div>
        <div class="toggle-group">
          <button class="toggle-option" :class="{ active: inputMode === 'typing' }" @click="$emit('update:inputMode', 'typing')">输入模式</button>
          <button class="toggle-option" :class="{ active: inputMode === 'choice' }" @click="$emit('update:inputMode', 'choice')">选择模式</button>
        </div>
      </div>

      <div class="setting-group">
        <div class="setting-label">语音语言</div>
        <div class="check-group">
          <div class="check-item" :class="{ checked: languages.includes('中文') }" @click="toggleLang('中文')">
            <div class="check-box">{{ languages.includes('中文') ? '✓' : '' }}</div>
            中文配音
          </div>
          <div class="check-item" :class="{ checked: languages.includes('日文') }" @click="toggleLang('日文')">
            <div class="check-box">{{ languages.includes('日文') ? '✓' : '' }}</div>
            日文配音
          </div>
        </div>
      </div>

      <div class="setting-group">
        <div class="setting-label">干员星级</div>
        <div class="check-group">
          <div v-for="star in 6" :key="star" class="check-item" :class="{ checked: selectedStars.includes(star) }" @click="toggleStar(star)">
            <div class="check-box">{{ selectedStars.includes(star) ? '✓' : '' }}</div>
            {{ '★'.repeat(star) }}
          </div>
        </div>
      </div>

      <div class="setting-group">
        <div class="setting-label">每题最大猜测次数</div>
        <div class="slider-container">
          <div class="slider-header">
            <span class="slider-desc">总次数上限</span>
            <span class="slider-value">{{ maxGuesses }}</span>
          </div>
          <input type="range" class="slider" min="3" max="30" :value="maxGuesses" @input="$emit('update:maxGuesses', +$event.target.value)" />
          <div class="slider-labels"><span>3</span><span>15</span><span>30</span></div>
        </div>
      </div>

      <div class="setting-group">
        <div class="setting-label">猜几次后播下一条语音</div>
        <div class="slider-container">
          <div class="slider-header">
            <span class="slider-desc">每条次数</span>
            <span class="slider-value">{{ guessesPerClip }}</span>
          </div>
          <input type="range" class="slider" min="1" max="10" :value="guessesPerClip" @input="$emit('update:guessesPerClip', +$event.target.value)" />
          <div class="slider-labels"><span>1</span><span>5</span><span>10</span></div>
        </div>
      </div>

      <div class="setting-group">
        <div class="setting-label">语音类型</div>
        <div class="check-group">
          <div v-for="vt in voiceTypes" :key="vt" class="check-item" :class="{ checked: selectedVoiceTypes.includes(vt) }" @click="toggleVoiceType(vt)">
            <div class="check-box">{{ selectedVoiceTypes.includes(vt) ? '✓' : '' }}</div>
            {{ vt }}
          </div>
        </div>
      </div>

      <button class="confirm-btn" @click="handleConfirm">确定</button>
    </div>
  </div>
</template>

<script setup>
import { VOICE_TYPES } from '../utils/constants.js'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  inputMode: { type: String, default: 'typing' },
  languages: { type: Array, default: () => ['中文', '日文'] },
  selectedStars: { type: Array, default: () => [1, 2, 3, 4, 5, 6] },
  maxGuesses: { type: Number, default: 10 },
  guessesPerClip: { type: Number, default: 3 },
  selectedVoiceTypes: { type: Array, default: () => [] }
})

const emit = defineEmits([
  'update:modelValue',
  'update:inputMode',
  'update:languages',
  'update:selectedStars',
  'update:maxGuesses',
  'update:guessesPerClip',
  'update:selectedVoiceTypes',
  'confirm'
])

const voiceTypes = VOICE_TYPES

function toggleLang(lang) {
  const current = [...props.languages]
  const idx = current.indexOf(lang)
  if (idx >= 0) {
    current.splice(idx, 1)
  } else {
    current.push(lang)
  }
  if (current.length > 0) {
    emit('update:languages', current)
  }
}

function toggleStar(star) {
  const current = [...props.selectedStars]
  const idx = current.indexOf(star)
  if (idx >= 0) {
    current.splice(idx, 1)
  } else {
    current.push(star)
  }
  if (current.length > 0) {
    emit('update:selectedStars', current)
  }
}

function toggleVoiceType(vt) {
  const current = [...props.selectedVoiceTypes]
  const idx = current.indexOf(vt)
  if (idx >= 0) {
    current.splice(idx, 1)
  } else {
    current.push(vt)
  }
  emit('update:selectedVoiceTypes', current)
}

function handleConfirm() {
  console.log('SettingsDrawer: confirm button clicked')
  emit('confirm')
}
</script>

<style scoped>
.settings-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.3);
  backdrop-filter: blur(4px);
  z-index: 100;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.3s;
}

.settings-overlay.open {
  opacity: 1;
  pointer-events: auto;
}

.settings-drawer {
  position: fixed;
  bottom: 0;
  left: 50%;
  transform: translateX(-50%) translateY(100%);
  width: 100%;
  max-width: 440px;
  background: var(--bg-white);
  border-radius: var(--r-lg) var(--r-lg) 0 0;
  padding: 24px;
  z-index: 101;
  transition: transform 0.35s cubic-bezier(0.34, 1.56, 0.64, 1);
  box-shadow: 0 -8px 32px rgba(0,0,0,0.12);
  max-height: 85vh;
  overflow-y: auto;
}

.settings-drawer.open {
  transform: translateX(-50%) translateY(0);
}

.settings-handle {
  width: 36px;
  height: 4px;
  background: var(--border);
  border-radius: 2px;
  margin: 0 auto 20px;
}

.settings-title {
  font-family: var(--font-display);
  font-size: 18px;
  font-weight: 700;
  margin-bottom: 24px;
}

.setting-group {
  margin-bottom: 24px;
}

.setting-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 10px;
}

.toggle-group {
  display: flex;
  background: var(--bg-warm);
  border-radius: var(--r-md);
  padding: 4px;
  gap: 4px;
}

.toggle-option {
  flex: 1;
  padding: 10px;
  border-radius: var(--r-sm);
  border: none;
  background: transparent;
  font-family: var(--font-body);
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.2s;
  text-align: center;
}

.toggle-option.active {
  background: white;
  color: var(--text);
  box-shadow: var(--shadow-sm);
  font-weight: 600;
}

.check-group {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.check-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  background: var(--bg-warm);
  border-radius: var(--r-sm);
  cursor: pointer;
  transition: all 0.2s;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
  border: 1.5px solid transparent;
  user-select: none;
}

.check-item:hover {
  background: white;
}

.check-item.checked {
  background: var(--accent-light);
  color: var(--accent);
  border-color: var(--accent);
}

.check-box {
  width: 18px;
  height: 18px;
  border-radius: 5px;
  border: 2px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  transition: all 0.2s;
  flex-shrink: 0;
}

.check-item.checked .check-box {
  background: var(--accent);
  border-color: var(--accent);
  color: white;
}

.slider-container {
  background: var(--bg-warm);
  border-radius: var(--r-md);
  padding: 16px;
}

.slider-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.slider-desc {
  font-size: 13px;
  color: var(--text-secondary);
}

.slider-value {
  font-family: var(--font-display);
  font-size: 24px;
  font-weight: 700;
  color: var(--accent);
}

.slider-labels {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 8px;
}

.slider {
  -webkit-appearance: none;
  width: 100%;
  height: 6px;
  background: var(--border);
  border-radius: 3px;
  outline: none;
}

.slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--accent);
  cursor: pointer;
  box-shadow: 0 2px 8px rgba(232, 101, 42, 0.3);
  border: 3px solid white;
  transition: transform 0.15s;
}

.slider::-webkit-slider-thumb:hover {
  transform: scale(1.15);
}

.confirm-btn {
  width: 100%;
  padding: 14px;
  background: var(--accent);
  color: white;
  border: none;
  border-radius: var(--r-md);
  font-family: var(--font-body);
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  box-shadow: 0 4px 12px rgba(232, 101, 42, 0.2);
  margin-top: 8px;
}

.confirm-btn:hover {
  background: var(--accent-hover);
  transform: translateY(-1px);
}
</style>
