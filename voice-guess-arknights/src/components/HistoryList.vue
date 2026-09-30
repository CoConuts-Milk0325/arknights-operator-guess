<template>
  <div class="history-list-container">
    <div v-for="(item, index) in history" :key="index" class="history-row" :class="item.correct ? 'correct' : 'wrong'">
      <div class="row-index">{{ index + 1 }}</div>
      <div class="row-avatar">
        <img v-if="item.avatarUrl" :src="item.avatarUrl" :alt="item.operatorName" @error="$event.target.style.display='none'" />
      </div>
      <div class="row-info">
        <div class="row-name">
          {{ item.operatorName }}
          <span v-if="!item.correct" class="row-correct-answer">({{ item.guessed || '未猜' }} → 正确)</span>
        </div>
        <div class="row-meta">
          {{ item.correct ? '✓' : '✗' }}
          · {{ item.clipsUsed }}条语音
          · {{ item.timeUsed }}
          · {{ item.language }}
          <span v-if="item.score > 0" class="row-score">+{{ item.score }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  history: { type: Array, default: () => [] }
})
</script>

<style scoped>
.history-list-container {
  max-height: 400px;
  overflow-y: auto;
  border-radius: var(--r-md);
  border: 1px solid var(--border);
}

.history-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  border-bottom: 1px solid var(--border-light);
  transition: background 0.15s;
}

.history-row:last-child {
  border-bottom: none;
}

.history-row.correct {
  background: #f0fdf4;
}

.history-row.wrong {
  background: #fef2f2;
}

.row-index {
  font-family: var(--font-display);
  font-size: 13px;
  font-weight: 600;
  color: var(--text-muted);
  width: 20px;
  text-align: center;
  flex-shrink: 0;
}

.row-avatar {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  overflow: hidden;
  background: white;
  border: 1px solid var(--border-light);
  flex-shrink: 0;
}

.row-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.row-info {
  flex: 1;
  min-width: 0;
}

.row-name {
  font-size: 14px;
  font-weight: 500;
}

.row-correct-answer {
  font-size: 12px;
  color: var(--text-muted);
  font-weight: 400;
}

.row-meta {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 2px;
}

.row-score {
  color: var(--accent);
  font-weight: 600;
  margin-left: 4px;
}
</style>
