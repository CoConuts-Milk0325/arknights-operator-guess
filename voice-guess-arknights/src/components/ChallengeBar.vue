<template>
  <div class="challenge-bar">
    <div class="challenge-item">
      <div class="challenge-label">当前连胜</div>
      <div class="challenge-value">{{ streak }}</div>
    </div>
    <div class="challenge-divider"></div>
    <div class="challenge-item">
      <div class="challenge-label">本轮得分</div>
      <div class="challenge-value">{{ score }}</div>
    </div>
    <div class="challenge-divider"></div>
    <div class="challenge-item">
      <div class="challenge-label">进度</div>
      <div class="challenge-value">{{ current }}/{{ total }}</div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  streak: { type: Number, default: 0 },
  score: { type: Number, default: 0 },
  current: { type: Number, default: 0 },
  total: { type: Number, default: 20 }
})
</script>

<style scoped>
.challenge-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 20px;
  background: var(--bg-white);
  border-radius: var(--r-md);
  box-shadow: var(--shadow-sm);
  margin-bottom: 20px;
}

.challenge-item {
  text-align: center;
}

.challenge-label {
  font-size: 11px;
  color: var(--text-muted);
  font-weight: 500;
  letter-spacing: 0.5px;
}

.challenge-value {
  font-family: var(--font-display);
  font-size: 20px;
  font-weight: 700;
  color: var(--accent);
  margin-top: 2px;
}

.challenge-divider {
  width: 1px;
  height: 32px;
  background: var(--border);
}
</style>
