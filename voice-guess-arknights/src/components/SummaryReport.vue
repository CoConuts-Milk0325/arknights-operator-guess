<template>
  <div class="summary-card">
    <div class="summary-header">
      <div class="grade-badge">{{ grade }}</div>
      <div class="summary-title">挑战完成！</div>
    </div>

    <div class="stats-grid">
      <div class="stat-item">
        <div class="stat-value">{{ score }}<span class="stat-max">/{{ maxPossible }}</span></div>
        <div class="stat-label">总分</div>
      </div>
      <div class="stat-item">
        <div class="stat-value">{{ correctCount }}/{{ totalQuestions }}</div>
        <div class="stat-label">猜对</div>
      </div>
      <div class="stat-item">
        <div class="stat-value">{{ accuracy }}%</div>
        <div class="stat-label">猜对率</div>
      </div>
      <div class="stat-item">
        <div class="stat-value">{{ maxStreak }}</div>
        <div class="stat-label">最高连胜</div>
      </div>
      <div class="stat-item">
        <div class="stat-value">{{ timeUsed }}</div>
        <div class="stat-label">用时</div>
      </div>
      <div class="stat-item">
        <div class="stat-value">{{ chineseCorrect }}/{{ totalQuestions }}</div>
        <div class="stat-label">中文猜对</div>
      </div>
      <div class="stat-item">
        <div class="stat-value">{{ japaneseCorrect }}/{{ totalQuestions }}</div>
        <div class="stat-label">日文猜对</div>
      </div>
    </div>

    <div class="history-section">
      <div class="history-title">题目回顾</div>
      <HistoryList :history="history" />
    </div>

    <button class="restart-btn" @click="$emit('restart')">再来一轮</button>
  </div>
</template>

<script setup>
import HistoryList from './HistoryList.vue'

defineProps({
  score: { type: Number, default: 0 },
  maxPossible: { type: Number, default: 3000 },
  correctCount: { type: Number, default: 0 },
  totalQuestions: { type: Number, default: 20 },
  accuracy: { type: Number, default: 0 },
  maxStreak: { type: Number, default: 0 },
  timeUsed: { type: String, default: '0:00' },
  grade: { type: String, default: 'D' },
  chineseCorrect: { type: Number, default: 0 },
  japaneseCorrect: { type: Number, default: 0 },
  history: { type: Array, default: () => [] }
})

defineEmits(['restart'])
</script>

<style scoped>
.summary-card {
  background: var(--bg-white);
  border-radius: var(--r-lg);
  padding: 24px;
  box-shadow: var(--shadow-lg);
  animation: resultIn 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
}

@keyframes resultIn {
  from { opacity: 0; transform: translateY(16px) scale(0.98); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

.summary-header {
  text-align: center;
  margin-bottom: 24px;
}

.grade-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--accent), #f59e0b);
  color: white;
  font-family: var(--font-display);
  font-size: 32px;
  font-weight: 800;
  margin-bottom: 12px;
  box-shadow: 0 4px 16px rgba(232, 101, 42, 0.3);
}

.summary-title {
  font-family: var(--font-display);
  font-size: 20px;
  font-weight: 700;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-bottom: 24px;
}

.stat-item {
  text-align: center;
  padding: 12px 8px;
  background: var(--bg-warm);
  border-radius: var(--r-sm);
}

.stat-value {
  font-family: var(--font-display);
  font-size: 20px;
  font-weight: 700;
  color: var(--text);
}

.stat-max {
  font-size: 14px;
  color: var(--text-muted);
  font-weight: 400;
}

.stat-label {
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 4px;
}

.history-section {
  margin-top: 20px;
}

.history-title {
  font-family: var(--font-display);
  font-size: 14px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 12px;
}

.restart-btn {
  width: 100%;
  margin-top: 20px;
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

.restart-btn:hover {
  background: var(--accent-hover);
  transform: translateY(-1px);
}
</style>
