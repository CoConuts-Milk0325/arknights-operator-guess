import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

// Shards are the source of truth. Refresh optional local exports if present.
export function syncVoiceTexts(projectRoot) {
  const voicesDir = path.join(projectRoot, 'public', 'data', 'voices')
  const data = Object.fromEntries(fs.readdirSync(voicesDir).filter(file => file.endsWith('.json')).map(file => [
    file.slice(0, -5), JSON.parse(fs.readFileSync(path.join(voicesDir, file), 'utf8'))
  ]))
  const workspace = path.dirname(projectRoot)
  for (const file of [path.join(workspace, 'voice-texts.json'), path.join(workspace, 'voice-line-search', 'voice-texts.json')]) {
    if (fs.existsSync(file)) fs.writeFileSync(file, JSON.stringify(data))
  }
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  syncVoiceTexts(path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..'))
}
