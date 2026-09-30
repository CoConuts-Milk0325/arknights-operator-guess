import { pinyin } from 'pinyin-pro'
import { DATA_VERSION } from '../dataVersion.js'
import searchIndex from '../operatorSearchIndex.json' with { type: 'json' }

let operatorsCache = null

// 归一化：转小写并去掉所有特殊字符（保留中文/字母/数字），用于忽略大小写和特殊字符匹配
function normalize(s) {
  return (s || '').normalize('NFKC').toLowerCase().replace(/[üǖǘǚǜ]/g, 'v')
    .normalize('NFD').replace(/\p{M}/gu, '').replace(/[^\p{L}\p{N}]/gu, '')
}

export async function loadOperators() {
  if (operatorsCache) return operatorsCache

  const response = await fetch(`./data/operators.json?v=${DATA_VERSION}`)
  if (!response.ok) throw new Error(`Unable to load operators: ${response.status}`)
  const data = await response.json()
  operatorsCache = data.map(op => {
    const name = op['干员']
    const nameEn = op['干员外文名']
    const pinyinFull = pinyin(name, { toneType: 'none', type: 'array' }).join('')
    const entry = searchIndex[normalize(name)] || {}
    return {
      name,
      nameEn,
      profession: op['职业'],
      subProfession: op['子职业'],
      rarity: op['稀有度'],
      race: op['种族'],
      country: op['国家'],
      team: op['团队'],
      gender: op['性别'],
      pinyinFull,
      pinyinInitials: pinyin(name, { pattern: 'first', toneType: 'none', type: 'array' }).join(''),
      normName: normalize(name),
      normNameEn: normalize(nameEn),
      normPinyin: normalize(pinyinFull),
      normAliases: (entry.aliases || []).map(normalize),
      normPinyins: [...new Set([normalize(pinyinFull), ...(entry.pinyinFull || [])])],
      normInitials: [...new Set([
        normalize(pinyin(name, { pattern: 'first', toneType: 'none', type: 'array' }).join('')),
        ...(entry.pinyinInitials || []),
      ])]
    }
  })
  return operatorsCache
}

export function searchOperators(query, operators) {
  if (!query || !query.trim()) return []

  const q = normalize(query)
  if (!q) return []

  const scored = []
  for (const op of operators) {
    const score = scoreMatch(op, q)
    if (score > 0) scored.push({ op, score })
  }

  // 按匹配度降序，同类保持原顺序
  scored.sort((a, b) => b.score - a.score)
  return scored.slice(0, 10).map(s => s.op)
}

// 完整本名优先于外号；共享外号保留多个候选，供玩家选择。
function scoreMatch(op, q) {
  const score = (values, exact, prefix, partial = 0) => Math.max(0, ...values.filter(Boolean).map(value =>
    value === q ? exact : value.startsWith(q) ? prefix : value.includes(q) ? partial : 0))
  return Math.max(
    score([op.normName], 1000, 800, 600),
    score(op.normAliases || [], 900, 650, 450),
    score(op.normPinyins || [op.normPinyin], 750, 550, 300),
    score(op.normInitials || [op.pinyinInitials], 500, 400),
    score([op.normNameEn], 700, 350, 200),
  )
}
