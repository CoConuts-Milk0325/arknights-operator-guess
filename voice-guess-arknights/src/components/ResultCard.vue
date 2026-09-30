<template>
  <div class="result-card" :class="correct ? 'success' : 'fail'">
    <div class="result-top">
      <div class="result-emoji">{{ correct ? '🎉' : '😅' }}</div>
      <div class="result-text" :class="correct ? 'text-green' : 'text-red'">
        {{ correct ? '猜对了！' : '没猜到' }}
      </div>
      <div class="result-sub">{{ subTitle }}</div>
    </div>

    <div class="operator-row">
      <div class="op-avatar">
        <img
          v-if="avatarUrl"
          :src="avatarUrl"
          :alt="operator.name"
          @error="avatarError = true"
        />
        <span v-else class="avatar-placeholder">?</span>
      </div>
      <div class="op-info">
        <div class="op-name">{{ operator.name }}</div>
        <div class="op-name-en">{{ operator.nameEn }}</div>
        <div class="op-tags">
          <span class="op-tag stars">{{ '★'.repeat(parseInt(operator.rarity) + 1) }}</span>
          <span class="op-tag">{{ operator.profession }}</span>
          <span v-if="operator.subProfession" class="op-tag">{{ operator.subProfession }}</span>
          <span v-if="operator.country" class="op-tag">{{ operator.country }}</span>
          <span v-if="operator.race" class="op-tag">{{ operator.race }}</span>
        </div>
      </div>
    </div>

    <button class="next-btn" @click="$emit('next')">
      {{ isLast ? '查看总结' : '下一题 →' }}
    </button>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { getAvatarUrl } from '../logic/gameEngine.js'

const props = defineProps({
  operator: { type: Object, required: true },
  correct: { type: Boolean, default: true },
  clipsUsed: { type: Number, default: 1 },
  isLast: { type: Boolean, default: false }
})

const emit = defineEmits(['next'])

const avatarError = ref(false)
const mountedAt = ref(0)

function onEnterKey(e) {
  if (e.key !== 'Enter' || e.repeat) return
  // 焦点在输入框时的回车是提交答案，不触发下一题
  const t = e.target
  if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable)) return
  // 忽略挂载初期（<500ms）的 Enter，避免提交答案后快速连按误触发下一题
  if (Date.now() - mountedAt.value < 500) return
  emit('next')
}

onMounted(() => {
  mountedAt.value = Date.now()
  window.addEventListener('keydown', onEnterKey)
})
onUnmounted(() => window.removeEventListener('keydown', onEnterKey))

const subTitle = computed(() => {
  if (props.correct) {
    return `第 ${props.clipsUsed} 条语音猜中`
  }
  return '下次再接再厉'
})

const avatarUrl = computed(() => {
  if (avatarError.value) return null
  return getAvatarUrl(props.operator)
})
</script>

<style scoped>
.result-card {
  border-radius: var(--r-lg);
  padding: 24px;
  box-shadow: var(--shadow-lg);
  margin-bottom: 16px;
  animation: resultIn 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
  position: relative;
  overflow: hidden;
  background: var(--bg-white);
}

.result-card.success::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 4px;
  background: linear-gradient(90deg, var(--green), #10b981);
  border-radius: var(--r-lg) var(--r-lg) 0 0;
}

.result-card.fail::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 4px;
  background: linear-gradient(90deg, var(--red), #f87171);
  border-radius: var(--r-lg) var(--r-lg) 0 0;
}

@keyframes resultIn {
  from { opacity: 0; transform: translateY(16px) scale(0.98); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

.result-top {
  text-align: center;
  margin-bottom: 20px;
}

.result-emoji {
  font-size: 40px;
  margin-bottom: 8px;
}

.result-text {
  font-family: var(--font-display);
  font-size: 20px;
  font-weight: 700;
}

.text-green { color: var(--green); }
.text-red { color: var(--red); }

.result-sub {
  font-size: 13px;
  color: var(--text-secondary);
  margin-top: 4px;
}

.operator-row {
  display: flex;
  gap: 16px;
  background: var(--bg-warm);
  padding: 16px;
  border-radius: var(--r-md);
}

.op-avatar {
  width: 68px;
  height: 68px;
  background: white;
  border-radius: var(--r-md);
  border: 2px solid var(--border-light);
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  flex-shrink: 0;
}

.op-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.avatar-placeholder {
  font-size: 28px;
  color: var(--text-muted);
}

.op-info {
  flex: 1;
  min-width: 0;
}

.op-name {
  font-family: var(--font-display);
  font-size: 20px;
  font-weight: 700;
}

.op-name-en {
  font-size: 12px;
  color: var(--text-muted);
  font-weight: 400;
  margin-top: 1px;
}

.op-tags {
  display: flex;
  gap: 6px;
  margin-top: 8px;
  flex-wrap: wrap;
}

.op-tag {
  padding: 3px 10px;
  border-radius: var(--r-full);
  font-size: 11px;
  font-weight: 500;
  background: white;
  color: var(--text-secondary);
  border: 1px solid var(--border);
}

.op-tag.stars {
  background: #fef3c7;
  color: #d97706;
  border-color: #fde68a;
}

.next-btn {
  width: 100%;
  margin-top: 16px;
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
}

.next-btn:hover {
  background: var(--accent-hover);
  box-shadow: 0 6px 20px rgba(232, 101, 42, 0.3);
  transform: translateY(-1px);
}
</style>
