export const VOICE_TYPES = [
  '登录', '交谈', '晋升交谈', '信赖', '闲置',
  '报到', '作战记录', '精英化1', '精英化2', '编入',
  '任命队长', '行动出发', '行动开始', '选中', '部署',
  '技能', '高难胜利', '3星胜利', '非3星胜利', '失败',
  '进驻', '戳一下', '信赖触摸', '标题', '新年', '问候'
]

export const GRADE_THRESHOLDS = [
  { grade: 'S', minScore: 2700 },
  { grade: 'A', minScore: 2200 },
  { grade: 'B', minScore: 1600 },
  { grade: 'C', minScore: 1000 },
  { grade: 'D', minScore: 0 }
]

export const MAX_QUESTIONS = 20

export const MAX_SCORE_PER_QUESTION = 150

// 音频源：bwiki 是 B 站自有 CDN，prts 是粉丝镜像，仅用于 bwiki 没有的条目
export const AUDIO_BASES = {
  bwiki: 'https://patchwiki.biligame.com/images/arknights/',
  prts: 'https://torappu.prts.wiki/assets/audio/'
}

export const DEFAULT_AUDIO_SOURCE = 'prts'
