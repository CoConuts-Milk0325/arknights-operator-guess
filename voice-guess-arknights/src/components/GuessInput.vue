<template>
  <div class="guess-area">
    <div class="input-row">
      <input
        ref="inputEl"
        class="guess-input"
        :value="modelValue"
        @input="onInput"
        @keydown.enter="onSubmit"
        placeholder="输入干员名、外号或拼音"
      />
      <button class="submit-btn" @click="onSubmit">→</button>
    </div>

    <div v-if="showDropdown && results.length" class="search-dropdown">
      <div
        v-for="(op, i) in results"
        :key="op.name"
        class="search-item"
        :class="{ highlighted: i === 0 }"
        @click="onSelect(op)"
        @mousemove="highlightedIndex = i"
      >
        <span class="search-name">{{ op.name }}</span>
        <span class="search-sub">{{ op.profession }} · {{ op.nameEn }}</span>
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
import { ref } from 'vue'
import { searchOperators } from '../logic/operatorSearch.js'

const props = defineProps({
  modelValue: { type: String, default: '' },
  operators: { type: Array, default: () => [] },
  history: { type: Array, default: () => [] },
  disabled: { type: Boolean, default: false }
})

const emit = defineEmits(['update:modelValue', 'submit'])

const inputEl = ref(null)
const results = ref([])
const showDropdown = ref(false)
const highlightedIndex = ref(0)

function onInput(e) {
  const value = e.target.value
  emit('update:modelValue', value)
  highlightedIndex.value = 0

  if (value.trim()) {
    results.value = searchOperators(value, props.operators)
    showDropdown.value = results.value.length > 0
  } else {
    results.value = []
    showDropdown.value = false
  }
}

function onSelect(op) {
  emit('update:modelValue', op.name)
  showDropdown.value = false
  results.value = []
  emit('submit', op.name)
}

function onSubmit() {
  // 无匹配候选时无法提交
  if (!results.value.length) return
  // 自动匹配第一个候选
  const op = results.value[highlightedIndex.value] || results.value[0]
  onSelect(op)
}

function focus() {
  inputEl.value?.focus()
}

defineExpose({ focus })
</script>

<style scoped>
.guess-area {
  background: var(--bg-white);
  border-radius: var(--r-lg);
  padding: 20px;
  box-shadow: var(--shadow-md);
  margin-bottom: 16px;
  position: relative;
}

.input-row {
  position: relative;
}

.guess-input {
  width: 100%;
  padding: 14px 48px 14px 18px;
  background: var(--bg-warm);
  border: 2px solid transparent;
  border-radius: var(--r-md);
  font-family: var(--font-body);
  font-size: 16px;
  color: var(--text);
  outline: none;
  transition: all 0.2s;
}

.guess-input::placeholder {
  color: var(--text-muted);
  font-weight: 400;
}

.guess-input:focus {
  border-color: var(--accent);
  background: white;
  box-shadow: 0 0 0 4px rgba(232, 101, 42, 0.08);
}

.submit-btn {
  position: absolute;
  right: 6px;
  top: 50%;
  transform: translateY(-50%);
  width: 38px;
  height: 38px;
  border-radius: var(--r-sm);
  border: none;
  background: var(--accent);
  color: white;
  font-size: 16px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
  opacity: 0;
  pointer-events: none;
}

.guess-input:focus ~ .submit-btn {
  opacity: 1;
  pointer-events: auto;
}

.submit-btn:hover {
  background: var(--accent-hover);
}

.search-dropdown {
  position: absolute;
  left: 20px;
  right: 20px;
  top: 54px;
  background: white;
  border-radius: var(--r-md);
  box-shadow: var(--shadow-lg);
  z-index: 10;
  max-height: 240px;
  overflow-y: auto;
  border: 1px solid var(--border-light);
}

.search-item {
  padding: 10px 16px;
  cursor: pointer;
  display: flex;
  justify-content: space-between;
  align-items: center;
  transition: background 0.15s;
}

.search-item:hover,
.search-item.highlighted {
  background: var(--bg-warm);
}

.search-item.highlighted {
  background: var(--accent-light);
}

.search-item:first-child {
  border-radius: var(--r-md) var(--r-md) 0 0;
}

.search-item:last-child {
  border-radius: 0 0 var(--r-md) var(--r-md);
}

.search-name {
  font-weight: 500;
  font-size: 14px;
}

.search-sub {
  font-size: 12px;
  color: var(--text-muted);
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
