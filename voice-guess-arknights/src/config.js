// 音频配置
// 分片里的路径带源前缀（bwiki:/prts:）；无前缀的历史数据走 DEFAULT_AUDIO_SOURCE。
// 每条还带 alt（PRTS 侧 .mp3）作为备用，播放失败时由 AudioPlayer 自动回退。

import { AUDIO_BASES, DEFAULT_AUDIO_SOURCE } from './utils/constants.js';

// torappu 为每个 .wav 提供同名 .mp3，体积差一个数量级，所以一律请求 .mp3
function resolve(source, path) {
  const clean = source === 'prts' && path.endsWith('.wav') ? `${path.slice(0, -4)}.mp3` : path;
  return `${AUDIO_BASES[source]}${clean}`;
}

function split(relativePath) {
  const match = /^(\w+):(.+)$/.exec(relativePath);
  const prefixed = Boolean(match && AUDIO_BASES[match[1]]);
  return { source: prefixed ? match[1] : DEFAULT_AUDIO_SOURCE, path: prefixed ? match[2] : relativePath };
}

// 获取音频 URL
export function getAudioUrl(relativePath) {
  const { source, path } = split(relativePath);
  return resolve(source, path);
}

// 获取备用音频 URL（PRTS 镜像），没有备用时返回 null
export function getFallbackUrl(entry) {
  const alt = typeof entry === 'string' ? null : entry?.alt;
  if (!alt) return null;
  const { source, path } = split(alt);
  return resolve(source, path);
}
