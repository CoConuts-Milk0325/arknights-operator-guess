import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const VOICE_GUESS_ROOT = path.join(__dirname, '..')
const VOICES_DIR = path.join(VOICE_GUESS_ROOT, 'public', 'data', 'voices')
const ROOT_VOICE_TEXTS = path.join(VOICE_GUESS_ROOT, '..', 'voice-texts.json')
const SEARCH_VOICE_TEXTS = path.join(VOICE_GUESS_ROOT, '..', 'voice-line-search', 'voice-texts.json')

const TARGET_OPS = ['予愿安洁莉娜', '佩德洛', '嘉辛塔', '时隙', '机械师', '珊比', '谬因']

function fixOperator(name) {
  const file = path.join(VOICES_DIR, `${name}.json`)
  const data = JSON.parse(fs.readFileSync(file, 'utf8'))
  const cn = data['中文']
  const jp = data['日文']
  if (!cn || !jp) {
    console.warn(`[SKIP] Missing CN or JP section in ${name}`)
    return null
  }

  let fixedClips = 0
  for (const [cat, cnClips] of Object.entries(cn)) {
    const jpClips = jp[cat]
    if (!jpClips) continue
    for (let i = 0; i < cnClips.length; i++) {
      if (jpClips[i] && (!jpClips[i].text || !jpClips[i].text.trim())) {
        jpClips[i].text = cnClips[i].text
        fixedClips++
      }
    }
  }

  fs.writeFileSync(file, JSON.stringify(data))
  console.log(`Fixed ${name}: populated text for ${fixedClips} JP clips.`)
  return data
}

function main() {
  console.log('--- Step 1: Fixing JP text in voices/*.json ---')
  const updatedData = {}
  for (const name of TARGET_OPS) {
    const data = fixOperator(name)
    if (data) updatedData[name] = data
  }

  console.log('\n--- Step 2: Updating root voice-texts.json ---')
  if (fs.existsSync(ROOT_VOICE_TEXTS)) {
    const rootTexts = JSON.parse(fs.readFileSync(ROOT_VOICE_TEXTS, 'utf8'))
    for (const [name, data] of Object.entries(updatedData)) {
      rootTexts[name] = data
    }
    fs.writeFileSync(ROOT_VOICE_TEXTS, JSON.stringify(rootTexts))
    console.log(`Updated ${ROOT_VOICE_TEXTS}`)
  }

  console.log('\n--- Step 3: Updating voice-line-search/voice-texts.json ---')
  if (fs.existsSync(SEARCH_VOICE_TEXTS)) {
    const searchTexts = JSON.parse(fs.readFileSync(SEARCH_VOICE_TEXTS, 'utf8'))
    for (const [name, data] of Object.entries(updatedData)) {
      searchTexts[name] = data
    }
    fs.writeFileSync(SEARCH_VOICE_TEXTS, JSON.stringify(searchTexts))
    console.log(`Updated ${SEARCH_VOICE_TEXTS}`)
  }

  console.log('\nAll JP texts successfully restored!')
}

main()
