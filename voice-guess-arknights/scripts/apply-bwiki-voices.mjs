import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT = path.join(__dirname, '..')
const VOICES_DIR = path.join(ROOT, 'public', 'data', 'voices')
const BWIKI_FILE = path.join(ROOT, '.bwiki-cache', 'bwiki-voices.json')

// Same in-game label -> project category table scripts/update-p3r-operators.mjs uses.
const LABEL_TO_CATEGORY = {
  任命助理: '登录',
  交谈1: '交谈',
  交谈2: '交谈',
  交谈3: '交谈',
  '晋升后交谈1': '晋升交谈',
  '晋升后交谈2': '晋升交谈',
  信赖提升后交谈1: '信赖',
  信赖提升后交谈2: '信赖',
  信赖提升后交谈3: '信赖',
  闲置: '闲置',
  干员报到: '报到',
  观看作战记录: '作战记录',
  精英化晋升1: '精英化1',
  精英化晋升2: '精英化2',
  编入队伍: '编入',
  任命队长: '任命队长',
  行动出发: '行动出发',
  行动开始: '行动开始',
  选中干员1: '选中',
  选中干员2: '选中',
  部署1: '部署',
  部署2: '部署',
  作战中1: '技能',
  作战中2: '技能',
  作战中3: '技能',
  作战中4: '技能',
  完成高难行动: '高难胜利',
  '3星结束行动': '3星胜利',
  非3星结束行动: '非3星胜利',
  行动失败: '失败',
  进驻设施: '进驻',
  戳一下: '戳一下',
  信赖触摸: '信赖触摸',
  标题: '标题',
  新年祝福: '新年',
  问候: '问候',
}

const args = process.argv.slice(2)
const WRITE = args.includes('--write')
// Evidence collection needs pairs for vetoed operators too, otherwise the veto hides its own inputs.
const IGNORE_VETO = args.includes('--ignore-veto')
const pairsFlag = args.indexOf('--pairs')
const pairsAt = pairsFlag < 0 ? null : args[pairsFlag + 1]
const rest = args.filter((arg, index) => !arg.startsWith('--') && index !== pairsFlag + 1)
const only = rest.length ? rest[0].split(',') : null

const urlOf = entry => (typeof entry === 'string' ? entry : entry.url)
const textOf = entry => (typeof entry === 'string' ? '' : entry.text || '')
const isDialect = entry => urlOf(entry).startsWith('voice_custom/')
const stripHints = text => String(text).replace(/\s*(提升信赖至\d+%以查看|提升至精英阶段\d以查看)/g, '')
const norm = text => stripHints(text).replace(/[…]+/g, '.').replace(/[\s]/g, '').replace(/[\p{P}\p{S}]/gu, '')

// skin shards inherited the base line's text, and dialect rows carry the Mandarin script:
// only a disagreement outside those two cases is a real cross-wiki conflict.
function driftKind(ourText, theirText, category, dialectOperator) {
  const mine = norm(ourText)
  const theirs = norm(theirText)
  if (!mine || !theirs || mine === theirs || theirs.includes(mine) || mine.includes(theirs)) return null
  if (category.includes('皮肤')) return 'skin-text'
  if (dialectOperator) return 'dialect-script'
  return 'conflict'
}

function rowsByCategory(page) {
  const rows = Object.values(page)
  // 联动干员的音频在主页面单列（无语言标记），中文与日文共用它
  const cn = rows.some(row => row['中']) ? '中' : rows.some(row => row['联']) ? '联' : null
  const jp = rows.some(row => row['日']) ? '日' : cn === '联' ? '联' : null
  const groups = {}
  for (const [label, row] of Object.entries(page)) {
    const category = LABEL_TO_CATEGORY[label]
    if (!category) continue
    groups[category] ||= { standard: [], dialect: [], jp: [] }
    if (cn && row[cn]) groups[category].standard.push({ ...row, label })
    if (row['方']) groups[category].dialect.push({ ...row, label })
    if (jp && row[jp]) groups[category].jp.push({ ...row, label })
  }
  return { groups, cn, jp }
}

function pickSkin(pages, category) {
  const skins = Object.keys(pages).filter(skin => skin !== '默认')
  if (skins.length !== 1) {
    return { error: `${category}: bwiki 有 ${skins.length} 个皮肤页（${skins.join('/')}），无法判定对应关系` }
  }
  return { page: pages[skins[0]] }
}

function planOperator(name, shard, pages, issues, baseline, appended) {
  const plan = {}
  const hasDialect = Object.values(pages).some(page => Object.values(page).some(row => row['方']))
  let clips = 0

  for (const [language, categories] of Object.entries(shard)) {
    if (!['中文', '日文'].includes(language)) continue
    for (const [category, entries] of Object.entries(categories)) {
      const isSkin = category.endsWith('（皮肤）')
      const base = isSkin ? category.slice(0, -4) : category
      let page = pages['默认']
      if (!isSkin && !Object.values(page).some(row => row['中'] || row['日']) && pages['主页面']) page = pages['主页面']
      if (isSkin) {
        const picked = pickSkin(pages, category)
        if (picked.error) {
          issues.push(`${name} ${category}: ${picked.error} — 保留 PRTS`)
          continue
        }
        page = picked.page
      }
      const table = rowsByCategory(page)
      const groups = table.groups[base]
      if (!groups) {
        issues.push(`${name} ${category}: bwiki 页面没有对应行 — 保留 PRTS`)
        continue
      }

      // The pristine (pre-migration) shard is the reference for what each slot used to be: once a URL is
      // rewritten the voice_custom marker and the original PRTS path are gone from the live data.
      const origin = baseline?.[language]?.[category] || entries
      if (language === '日文') {
        if (entries.length !== groups.jp.length) {
          issues.push(`${name} ${category}: 分片 ${entries.length} 条 vs bwiki ${groups.jp.length} 条 (日文) — 保留 PRTS`)
          continue
        }
        plan[language] ||= {}
        plan[language][category] = groups.jp.map((row, i) => ({ url: row[table.jp], text: row.text || '', skin: isSkin, originUrl: urlOf(origin[i]), originText: textOf(origin[i]), drift: null }))
        clips += groups.jp.length
        continue
      }

      const ourDialect = origin.filter(isDialect).length
      if (origin.slice(origin.length - ourDialect).some(entry => !isDialect(entry))) {
        issues.push(`${name} 中文 ${category}: 方言条目不在尾部 — 保留 PRTS`)
        continue
      }
      if (origin.length - ourDialect !== groups.standard.length || ourDialect > groups.dialect.length) {
        issues.push(`${name} 中文 ${category}: 分片 标准${origin.length - ourDialect}+方言${ourDialect} vs bwiki 标准${groups.standard.length}+方言${groups.dialect.length} — 保留 PRTS`)
        continue
      }
      const known = [...groups.standard, ...groups.dialect.slice(0, ourDialect)]
      const extras = groups.dialect.slice(ourDialect).map(row => {
        // bwiki stores the dialect script, but the game text we display stays Mandarin: reuse the
        // Mandarin line of the same label from our own standard entries.
        const match = groups.standard.findIndex(item => item.label === row.label)
        const base = match >= 0 ? urlOf(origin[match]) : ''
        return {
          url: row['方'],
          text: match >= 0 ? textOf(origin[match]) : row.text || '',
          alt: base.replace(/^voice_cn\/(.+)\/(cn_\d+)\.wav$/, 'voice_custom/$1_cn_topolect/$2.mp3'),
          skin: isSkin,
          append: true,
          originUrl: null,
          originText: '',
          drift: null,
        }
      })
      plan[language] ||= {}
      plan[language][category] = [
        ...known.map((row, i) => ({
          url: i >= groups.standard.length ? row['方'] : row[table.cn],
          text: row.text || '',
          skin: isSkin,
          originUrl: urlOf(origin[i]),
          originText: textOf(origin[i]),
          drift: driftKind(textOf(origin[i]), row.text, category, hasDialect),
        })),
        ...extras,
      ]
      clips += known.length + extras.length
      if (extras.length) appended.push(`${name} ${category} +${extras.length}`)
    }
  }
  return { plan, clips }
}

// Slots that stay on PRTS even though bwiki has a link for them. Each one was checked by
// byte-comparing both hosts and by Qwen3-ASR on 2026-09-24; the earlier duration-based veto is
// retired because its measurements were wrong (see scripts/compare-audio-duration.mjs history).
const HOLDOUT = {
  // Its bwiki subpage cells are empty and the 主页面（联）column ASR hears as Japanese, while
  // PRTS voice_cn/ really is the Mandarin take (confirmed by ear).
  operators: new Set(['水灯心']),
  // 红隼 中文: bwiki's （中） column repeats 翎羽's clips — same file hash under different dialogue
  // (选中干员1 and 问候 are byte-identical to 翎羽's, and the files are 0.3-0.7s long).
  languages: new Set(['红隼|中文']),
  // 蓝毒 选中2: bwiki's cell repeats 白面鸮's clip (identical bytes, and it says 初始化完成).
  // 玛露西尔 新年: the bwiki hash has no file behind it; the PRTS mp3 does.
  // 远山 选中2/部署1/闲置/交谈2: bwiki's （中） cells hold 赫默's lines (ASR heard 没有异常 /
  // 我只是想小睡一下 / 睡着了吗), while PRTS voice_cn says 远山's own 台词 verbatim.
  // 可颂 新年（日文）: bwiki gives 提丰's recording for both operators; PRTS has 可颂's own take.
  slots: new Set([
    '蓝毒|中文|选中|1', '玛露西尔|中文|新年|0', '玛露西尔|日文|新年|0', '可颂|日文|新年|0',
    '远山|中文|选中|1', '远山|中文|部署|0', '远山|中文|闲置|0', '远山|中文|交谈|1',
  ]),
}

function loadVeto() {
  return { operators: HOLDOUT.operators, slots: HOLDOUT.slots, categories: HOLDOUT.languages }
}

function main() {
  const all = JSON.parse(fs.readFileSync(BWIKI_FILE, 'utf8'))
  const veto = loadVeto()
  // bwiki titles use full-width parentheses (阿米娅（近卫）) while our shards use half-width.
  const pageByName = new Map(Object.keys(all).map(key => [key.replace(/（/g, '(').replace(/）/g, ')'), key]))
  const shardNames = fs.readdirSync(VOICES_DIR).filter(file => file.endsWith('.json')).map(file => file.slice(0, -5))
  const names = (only || shardNames).filter(name => pageByName.has(name.replace(/（/g, '(').replace(/）/g, ')')))
  const issues = []
  const pairs = []
  const appended = []
  const vetoedOperators = []
  const vetoedCategories = []
  let touched = 0
  let totalClips = 0

  for (const name of names) {
    if (!IGNORE_VETO && veto.operators.has(name)) {
      vetoedOperators.push(name)
      continue
    }
    const file = path.join(VOICES_DIR, `${name}.json`)
    const shard = JSON.parse(fs.readFileSync(file, 'utf8'))
    const pristine = path.join(ROOT, '.bwiki-cache', 'pristine', `${name}.json`)
    const baseline = fs.existsSync(pristine) ? JSON.parse(fs.readFileSync(pristine, 'utf8')) : null
    const pages = all[pageByName.get(name.replace(/（/g, '(').replace(/）/g, ')'))]
    const { plan, clips } = planOperator(name, shard, pages, issues, baseline, appended)
    totalClips += clips
    let changed = false
    for (const [language, categories] of Object.entries(plan)) {
      if (veto.categories.has(`${name}|${language}`)) continue
      for (const [category, items] of Object.entries(categories)) {
        if (veto.categories.has(`${name}|${language}|${category}`)) {
          vetoedCategories.push(`${name} ${language} ${category}`)
          continue
        }
        const current = shard[language][category]
        shard[language][category] = items.map((item, i) => {
          const entry = current[i]
          if (veto.slots.has(`${name}|${language}|${category}|${i}`)) return entry
          if (item.url && !item.append) pairs.push({ name, language, category, index: i, prts: item.originUrl, bwiki: item.url, text: item.originText, bwikiText: item.text, drift: item.drift })
          // PRTS stays as an audible fallback on every clip: the bwiki column choice has been wrong
          // often enough this session that each entry needs its own independently checkable backup.
          const alt = item.url ? item.alt || item.originUrl?.replace(/\.wav$/, '.mp3') || null : null
          if (!item.url) {
            if (!entry.alt) return entry
            changed = true
            const { alt: _drop, ...rest } = entry
            return rest
          }
          const next = `bwiki:${item.url}`
          if (!entry) {
            changed = true
            return { url: next, text: item.text, ...(alt ? { alt } : {}) }
          }
          // 皮肤条目的文本当年是从基础台词复制过来的，这里用 bwiki 皮肤页台本修正
          const text = item.skin && item.text ? item.text : textOf(entry)
          if (urlOf(entry) === next && textOf(entry) === text && entry.alt === alt) return entry
          changed = true
          return { ...entry, url: next, text, ...(alt ? { alt } : {}) }
        })
      }
    }
    if (changed) {
      touched++
      if (WRITE) fs.writeFileSync(file, JSON.stringify(shard))
    }
  }

  if (pairsAt) {
    fs.writeFileSync(path.resolve(ROOT, pairsAt), JSON.stringify(pairs))
    console.log(`配对表已写出 ${pairsAt}：${pairs.length} 条`)
  }

  const drift = {}
  for (const pair of pairs) if (pair.drift) drift[pair.drift] = (drift[pair.drift] || 0) + 1
  const unfixable = {}
  for (const line of issues) {
    const reason = line.replace(/^.*? — /, '').replace(/\d+/g, 'N')
    unfixable[reason] = (unfixable[reason] || 0) + 1
  }
  console.log(`${WRITE ? '已改写' : '可改写'} ${touched}/${names.length} 个分片，覆盖 ${totalClips} 条语音`)
  console.log(`文本分歧: ${JSON.stringify(drift)}（conflict 才是需要听的）`)
  if (appended.length) console.log(`补入 bwiki 有而我们缺的方言条目 ${appended.reduce((n, line) => n + Number(/(\d+)$/.exec(line)[1]), 0)} 条，涉及 ${appended.length} 个类别`)
  console.log(`时长反证否决: 整员 ${vetoedOperators.length} 个 (${vetoedOperators.join(', ')})；类别 ${vetoedCategories.length} 个`)
  console.log(`无法配对 ${issues.length} 项`)
  for (const [reason, count] of Object.entries(unfixable)) console.log(`  ${reason}: ${count}`)
  for (const line of issues.slice(0, 25)) console.log('  · ' + line)
  if (issues.length > 25) console.log(`  … 另有 ${issues.length - 25} 项`)
  if (!WRITE) console.log('\ndry-run：未写入任何文件。确认后用 --write 落地。')
}

main()
