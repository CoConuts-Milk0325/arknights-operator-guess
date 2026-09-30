import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const VOICE_GUESS_ROOT = path.join(__dirname, '..')
const VOICES_DIR = path.join(VOICE_GUESS_ROOT, 'public', 'data', 'voices')
const VOICE_INDEX_FILE = path.join(VOICE_GUESS_ROOT, 'public', 'data', 'voice-index.json')
const OPERATORS_FILE = path.join(VOICE_GUESS_ROOT, 'public', 'data', 'operators.json')
const ROOT_VOICE_TEXTS = path.join(VOICE_GUESS_ROOT, '..', 'voice-texts.json')
const SEARCH_VOICE_TEXTS = path.join(VOICE_GUESS_ROOT, '..', 'voice-line-search', 'voice-texts.json')
const WORDLE_OPERATORS_FILE = path.join(VOICE_GUESS_ROOT, '..', 'arknights-wordle', 'frontend', 'public', 'data', 'operators.json')

const TITLE_TO_CATEGORY = {
  '任命助理': '登录',
  '交谈1': '交谈',
  '交谈2': '交谈',
  '交谈3': '交谈',
  '晋升后交谈1': '晋升交谈',
  '晋升后交谈2': '晋升交谈',
  '信赖提升后交谈1': '信赖',
  '信赖提升后交谈2': '信赖',
  '信赖提升后交谈3': '信赖',
  '闲置': '闲置',
  '干员报到': '报到',
  '观看作战记录': '作战记录',
  '精英化晋升1': '精英化1',
  '精英化晋升2': '精英化2',
  '编入队伍': '编入',
  '任命队长': '任命队长',
  '行动出发': '行动出发',
  '行动开始': '行动开始',
  '选中干员1': '选中',
  '选中干员2': '选中',
  '部署1': '部署',
  '部署2': '部署',
  '作战中1': '技能',
  '作战中2': '技能',
  '作战中3': '技能',
  '作战中4': '技能',
  '完成高难行动': '高难胜利',
  '3星结束行动': '3星胜利',
  '非3星结束行动': '非3星胜利',
  '行动失败': '失败',
  '进驻设施': '进驻',
  '戳一下': '戳一下',
  '信赖触摸': '信赖触摸',
  '标题': '标题',
  '新年祝福': '新年',
  '问候': '问候'
}

function cleanText(t) {
  return t
    .replace(/\{\{DrName[^\}]*\}\}/g, '博士')
    .replace(/\[\[(?:[^|\]]*\|)?([^\]]+)\]\]/g, '$1')
    .replace(/&nbsp;/g, ' ')
    .replace(/&#160;/g, ' ')
    .replace(/'''?/g, '')
    .trim()
}

async function fetchVoiceData(name, charId) {
  const url = 'https://prts.wiki/api.php?action=query&titles=' + encodeURIComponent(name + '/语音记录') + '&prop=revisions&rvprop=content&format=json'
  const res = await fetch(url).then(r => r.json())
  const content = Object.values(res.query.pages)[0].revisions[0]['*']

  const blocks = content.split(/\|标题\d+=/).slice(1)
  const cnObj = {}
  const jpObj = {}

  for (const block of blocks) {
    const lines = block.split('\n')
    const title = lines[0].trim()
    const cat = TITLE_TO_CATEGORY[title]
    if (!cat) continue

    const voiceMatch = block.match(/\|语音\d+=([^\n\|]+)/)
    if (!voiceMatch) continue
    const wav = voiceMatch[1].trim().toLowerCase()
    const url = `voice/${charId}/${wav}`

    const wordMatch = block.match(/\{\{VoiceData\/word\|中文\|([\s\S]*?)\}\}(?=\{\{VoiceData\/word|\n|\|)/)
    const text = wordMatch ? cleanText(wordMatch[1]) : ''

    if (!cnObj[cat]) cnObj[cat] = []
    if (!jpObj[cat]) jpObj[cat] = []

    cnObj[cat].push({ url, text })
    jpObj[cat].push({ url, text })
  }

  return { '中文': cnObj, '日文': jpObj }
}

const NEW_OPERATORS = [
  {
    "干员": "虎狼丸",
    "职业": "近卫",
    "稀有度": "0",
    "标志": "S.E.E.S.",
    "团队": "S.E.E.S.",
    "干员外文名": "Koromaru",
    "干员名jp": "",
    "情报编号": "PS38",
    "位置": "近战位",
    "标签": "爆发 控场",
    "特性": "普通攻击连续造成两次伤害，且不受部署数量限制，但再部署时间极长",
    "干员序号": "428",
    "子职业": "剑豪",
    "国家": "S.E.E.S.",
    "组织": null,
    "皮肤1名称": "飞越甜蜜之城",
    "皮肤2名称": null,
    "皮肤3名称": null,
    "皮肤4名称": null,
    "皮肤5名称": null,
    "皮肤6名称": null,
    "皮肤7名称": null,
    "皮肤8名称": null,
    "皮肤9名称": null,
    "皮肤10名称": null,
    "出身地": "未知",
    "种族": "佩洛兽亲（据称）",
    "性别": "男",
    "物理强度": "标准",
    "战场机动": "优良",
    "生理耐受": "标准",
    "战术规划": "标准",
    "战斗技巧": "标准",
    "源石技艺适应性": "■■",
    "身高": "未知",
    "出生日期": "未知",
    "感染状态": "非感染者",
    "获得方式": "SideStory「月行水上」活动获得",
    "上线时间": "2026年9月4日 12:00",
    "满级生命": "904",
    "满级攻击": "242",
    "满级防御": "125",
    "满级法术抗性": "0",
    "再部署时间": "200s",
    "部署费用": "3",
    "阻挡数": "2",
    "攻击速度": "1.3s",
    "潜能加成": "`",
    "信赖加成": "0,30,30",
    "_charId": "char_4220_kormr"
  },
  {
    "干员": "岳羽由加莉",
    "职业": "辅助",
    "稀有度": "4",
    "标志": "S.E.E.S.",
    "团队": "S.E.E.S.",
    "干员外文名": "Yukari Takeba",
    "干员名jp": "",
    "情报编号": "PS34",
    "位置": "远程位",
    "标签": "输出 支援",
    "特性": "可以使用触发型效果协助作战",
    "干员序号": "429",
    "子职业": "游击手",
    "国家": "S.E.E.S.",
    "组织": null,
    "皮肤1名称": "戍卫晨昏",
    "皮肤2名称": null,
    "皮肤3名称": null,
    "皮肤4名称": null,
    "皮肤5名称": null,
    "皮肤6名称": null,
    "皮肤7名称": null,
    "皮肤8名称": null,
    "皮肤9名称": null,
    "皮肤10名称": null,
    "出身地": "未知",
    "种族": "未知",
    "性别": "女",
    "物理强度": "标准",
    "战场机动": "标准",
    "生理耐受": "标准",
    "战术规划": "标准",
    "战斗技巧": "标准",
    "源石技艺适应性": "■■",
    "身高": "159cm",
    "出生日期": "10月19日",
    "感染状态": "非感染者",
    "获得方式": "限定寻访",
    "上线时间": "2026年9月4日 12:00",
    "满级生命": "1510",
    "满级攻击": "775",
    "满级防御": "200",
    "满级法术抗性": "10",
    "再部署时间": "70s",
    "部署费用": "14→16",
    "阻挡数": "1",
    "攻击速度": "2.1s",
    "潜能加成": "cost,re_deploy,atk,re_deploy,cost`-1,-4,30,-6,-1",
    "信赖加成": "300,30,0",
    "_charId": "char_4219_yukari"
  },
  {
    "干员": "埃癸斯",
    "职业": "狙击",
    "稀有度": "4",
    "标志": "S.E.E.S.",
    "团队": "S.E.E.S.",
    "干员外文名": "Aegis",
    "干员名jp": "",
    "情报编号": "PS37",
    "位置": "远程位",
    "标签": "群攻",
    "特性": "部署后起飞，起飞后只攻击空中敌人；技能开启时降落且攻击造成群体物理伤害",
    "干员序号": "430",
    "子职业": "裂空炮手",
    "国家": "S.E.E.S.",
    "组织": null,
    "皮肤1名称": "静思真谛",
    "皮肤2名称": null,
    "皮肤3名称": null,
    "皮肤4名称": null,
    "皮肤5名称": null,
    "皮肤6名称": null,
    "皮肤7名称": null,
    "皮肤8名称": null,
    "皮肤9名称": null,
    "皮肤10名称": null,
    "出身地": "未知",
    "种族": "未知",
    "性别": "女",
    "物理强度": "优良",
    "战场机动": "标准",
    "生理耐受": "优良",
    "战术规划": "标准",
    "战斗技巧": "优良",
    "源石技艺适应性": "■■",
    "身高": "163cm",
    "出生日期": "未知",
    "感染状态": "非感染者",
    "获得方式": "限定寻访",
    "上线时间": "2026年9月4日 12:00",
    "满级生命": "1586",
    "满级攻击": "882",
    "满级防御": "219",
    "满级法术抗性": "0",
    "再部署时间": "70s",
    "部署费用": "20→22",
    "阻挡数": "1",
    "攻击速度": "2.1s",
    "潜能加成": "cost,re_deploy,atk,,cost`-1,-4,33,,-1",
    "信赖加成": "100,60,0",
    "_charId": "char_4218_aigis"
  },
  {
    "干员": "结城理",
    "职业": "特种",
    "稀有度": "5",
    "标志": "S.E.E.S.",
    "团队": "S.E.E.S.",
    "干员外文名": "Makoto Yuki",
    "干员名jp": "",
    "情报编号": "PS33",
    "位置": "近战位",
    "标签": "输出 快速复活 治疗",
    "特性": "受到致命伤时不撤退，切换成<替身>作战（替身阻挡数为0），持续20秒后自身再次替换<替身>",
    "干员序号": "431",
    "子职业": "傀儡师",
    "国家": "S.E.E.S.",
    "组织": null,
    "皮肤1名称": "见证荣光",
    "皮肤2名称": null,
    "皮肤3名称": null,
    "皮肤4名称": null,
    "皮肤5名称": null,
    "皮肤6名称": null,
    "皮肤7名称": null,
    "皮肤8名称": null,
    "皮肤9名称": null,
    "皮肤10名称": null,
    "出身地": "未知",
    "种族": "未知",
    "性别": "男",
    "物理强度": "标准",
    "战场机动": "标准",
    "生理耐受": "标准",
    "战术规划": "优良",
    "战斗技巧": "优良",
    "源石技艺适应性": "■■",
    "身高": "170cm",
    "出生日期": "未知",
    "感染状态": "非感染者",
    "获得方式": "限定寻访",
    "上线时间": "2026年9月4日 12:00",
    "满级生命": "2805",
    "满级攻击": "785",
    "满级防御": "305",
    "满级法术抗性": "0",
    "再部署时间": "70s",
    "部署费用": "14→14→16",
    "阻挡数": "2",
    "攻击速度": "1.2s",
    "潜能加成": "cost,,atk,,cost`-1,,34,,-1",
    "信赖加成": "200,40,0",
    "_charId": "char_4217_makoto"
  }
]

async function main() {
  console.log('--- Step 1: Generating voice JSON files ---')
  const voiceDataMap = {}
  for (const op of NEW_OPERATORS) {
    console.log(`Fetching voice data for ${op.干员}...`)
    const voiceData = await fetchVoiceData(op.干员, op._charId)
    const filePath = path.join(VOICES_DIR, `${op.干员}.json`)
    fs.writeFileSync(filePath, JSON.stringify(voiceData))
    voiceDataMap[op.干员] = voiceData
    let clipCount = 0
    for (const cat of Object.values(voiceData['中文'])) clipCount += cat.length
    console.log(`Saved ${op.干员}.json with ${clipCount} clips.`)
  }

  console.log('\n--- Step 2: Updating voice-index.json ---')
  const voiceIndex = JSON.parse(fs.readFileSync(VOICE_INDEX_FILE, 'utf8'))
  for (const op of NEW_OPERATORS) {
    voiceIndex[op.干员] = ["中文", "日文"]
  }
  fs.writeFileSync(VOICE_INDEX_FILE, JSON.stringify(voiceIndex))
  console.log(`Updated ${VOICE_INDEX_FILE}, total operators: ${Object.keys(voiceIndex).length}`)

  console.log('\n--- Step 3: Updating operators.json in voice-guess ---')
  const operators = JSON.parse(fs.readFileSync(OPERATORS_FILE, 'utf8'))
  for (const op of NEW_OPERATORS) {
    const { _charId, ...opData } = op
    const existingIdx = operators.findIndex(o => o['干员'] === opData['干员'])
    if (existingIdx >= 0) {
      operators[existingIdx] = opData
    } else {
      operators.push(opData)
    }
  }
  fs.writeFileSync(OPERATORS_FILE, JSON.stringify(operators, null, 2))
  console.log(`Updated ${OPERATORS_FILE}, total operators: ${operators.length}`)

  console.log('\n--- Step 4: Updating voice-texts.json (root & voice-line-search) ---')
  if (fs.existsSync(ROOT_VOICE_TEXTS)) {
    const rootTexts = JSON.parse(fs.readFileSync(ROOT_VOICE_TEXTS, 'utf8'))
    for (const [name, data] of Object.entries(voiceDataMap)) {
      rootTexts[name] = data
    }
    fs.writeFileSync(ROOT_VOICE_TEXTS, JSON.stringify(rootTexts))
    console.log(`Updated ${ROOT_VOICE_TEXTS}, total operators: ${Object.keys(rootTexts).length}`)
  }

  if (fs.existsSync(SEARCH_VOICE_TEXTS)) {
    const searchTexts = JSON.parse(fs.readFileSync(SEARCH_VOICE_TEXTS, 'utf8'))
    for (const [name, data] of Object.entries(voiceDataMap)) {
      searchTexts[name] = data
    }
    fs.writeFileSync(SEARCH_VOICE_TEXTS, JSON.stringify(searchTexts))
    console.log(`Updated ${SEARCH_VOICE_TEXTS}, total operators: ${Object.keys(searchTexts).length}`)
  }

  console.log('\n--- Step 5: Updating arknights-wordle operators.json if needed ---')
  if (fs.existsSync(WORDLE_OPERATORS_FILE)) {
    const wordleOps = JSON.parse(fs.readFileSync(WORDLE_OPERATORS_FILE, 'utf8'))
    for (const op of NEW_OPERATORS) {
      const { _charId, ...opData } = op
      const existingIdx = wordleOps.findIndex(o => o['干员'] === opData['干员'])
      if (existingIdx >= 0) {
        wordleOps[existingIdx] = opData
      } else {
        wordleOps.push(opData)
      }
    }
    fs.writeFileSync(WORDLE_OPERATORS_FILE, JSON.stringify(wordleOps, null, 2))
    console.log(`Updated ${WORDLE_OPERATORS_FILE}, total operators: ${wordleOps.length}`)
  }

  console.log('\nAll data updates completed successfully!')
}

main().catch(err => {
  console.error('Error updating operators:', err)
  process.exit(1)
})
