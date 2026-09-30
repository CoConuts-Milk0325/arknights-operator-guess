<template>
  <div class="guess-area">
    <div class="choices-area">
      <div class="choice-row">
        <button
          v-for="(opt, i) in choices"
          :key="opt.name"
          class="choice-card"
          :class="{ wrong: wrongNames.has(opt.name) }"
          @click="$emit('select', opt.name)"
        >
          <div class="choice-letter">{{ letters[i] }}</div>
          <div class="choice-text">{{ opt.name }}</div>
        </button>
      </div>
    </div>

    <div v-if="history.length" class="history">
      <div class="history-title">历史猜测</div>
      <div class="history-list">
        <span
          v-for="(item, i) in history"
          :key="i"
          class="history-chip"
          :class="item.correct ? 'correct' : 'wrong'"
        >
          <span class="chip-icon">{{ item.correct ? '✓' : '✗' }}</span>
          {{ item.name }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  choices: { type: Array, default: () => [] },
  history: { type: Array, default: () => [] }
})

defineEmits(['select'])

const wrongNames = computed(() => new Set(
  props.history.filter(h => !h.correct).map(h => h.name)
))

const letters = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10',
  '11', '12', '13', '14', '15', '16', '17', '18', '19', '20',
  '21', '22', '23', '24', '25', '26', '27', '28', '29', '30']
</script>

<style scoped>
.guess-area {
  background: var(--bg-white);
  border-radius: var(--r-lg);
  padding: 20px;
  box-shadow: var(--shadow-md);
  margin-bottom: 16px;
}

.choices-area {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.choice-card {
  width: 100%;
  padding: 14px 16px;
  background: var(--bg-white);
  border: 2px solid var(--border);
  border-radius: var(--r-md);
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  gap: 12px;
  box-shadow: var(--shadow-sm);
  font-family: var(--font-body);
}

.choice-card:hover {
  border-color: var(--accent);
  box-shadow: 0 2px 12px rgba(232, 101, 42, 0.1);
}

.choice-letter {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  background: var(--bg-warm);
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--font-display);
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
  flex-shrink: 0;
}

.choice-card:hover .choice-letter {
  background: var(--accent-light);
  color: var(--accent);
}

.choice-card.wrong {
  border-color: var(--red);
  background: var(--red-light);
}

.choice-card.wrong .choice-letter {
  background: var(--red);
  color: white;
}

.choice-text {
  font-size: 15px;
  font-weight: 500;
}

.history {
  margin-top: 14px;
}

.history-title {
  font-size: 11px;
  color: var(--text-muted);
  font-weight: 600;
  letter-spacing: 0.5px;
  text-transform: uppercase;
  margin-bottom: 8px;
}

.history-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.history-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 5px 12px;
  border-radius: var(--r-full);
  font-size: 13px;
  font-weight: 500;
}

.history-chip.wrong {
  background: var(--red-light);
  color: var(--red);
}

.history-chip.correct {
  background: var(--green-light);
  color: var(--green);
}

.chip-icon {
  font-size: 12px;
}
</style>
