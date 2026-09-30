import { MAX_QUESTIONS, GRADE_THRESHOLDS } from '../utils/constants.js'
import { calculateScore } from './gameEngine.js'

export function createChallenge(totalQuestions = MAX_QUESTIONS) {
  return {
    currentQuestion: 0,
    totalQuestions,
    score: 0,
    streak: 0,
    maxStreak: 0,
    correctCount: 0,
    startTime: Date.now(),
    history: [],
    usedOperators: [],
    isComplete: false
  }
}

export function recordQuestion(challenge, record) {
  const score = record.correct ? calculateScore(record.clipsUsed, record.isChoiceMode) : 0

  const updated = {
    ...challenge,
    currentQuestion: challenge.currentQuestion + 1,
    score: challenge.score + score,
    correctCount: challenge.correctCount + (record.correct ? 1 : 0),
    streak: record.correct ? challenge.streak + 1 : 0,
    maxStreak: record.correct
      ? Math.max(challenge.maxStreak, challenge.streak + 1)
      : challenge.maxStreak,
    history: [...challenge.history, { ...record, score }],
    isComplete: challenge.currentQuestion + 1 >= challenge.totalQuestions
  }

  return updated
}

export function getGrade(score, maxPossible = 3000) {
  const normalized = maxPossible > 0 ? score / maxPossible * 3000 : 0
  for (const { grade, minScore } of GRADE_THRESHOLDS) {
    if (normalized >= minScore) return grade
  }
  return 'D'
}

export function generateSummary(challenge) {
  const elapsed = Date.now() - challenge.startTime
  const minutes = Math.floor(elapsed / 60000)
  const seconds = Math.floor((elapsed % 60000) / 1000)

  const maxPossible = challenge.history.reduce((sum, h) => sum + (h.isChoiceMode ? 100 : 150), 0)
  const grade = getGrade(challenge.score, maxPossible)

  const chineseCorrect = challenge.history.filter(
    h => h.correct && h.language === '中文'
  ).length
  const japaneseCorrect = challenge.history.filter(
    h => h.correct && h.language === '日文'
  ).length

  return {
    score: challenge.score,
    maxPossible,
    correctCount: challenge.correctCount,
    totalQuestions: challenge.totalQuestions,
    accuracy: Math.round((challenge.correctCount / challenge.totalQuestions) * 100),
    maxStreak: challenge.maxStreak,
    timeUsed: `${minutes}:${String(seconds).padStart(2, '0')}`,
    grade,
    chineseCorrect,
    japaneseCorrect,
    history: challenge.history
  }
}
