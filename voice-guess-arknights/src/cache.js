// 本地缓存管理
// 使用 localStorage 缓存 JSON 数据，避免重复下载

import { DATA_VERSION } from './dataVersion.js';

const CACHE_VERSION = `v2-${DATA_VERSION}`;
const CACHE_PREFIX = `voice-guess-${CACHE_VERSION}-`;
const CACHE_DURATION = 24 * 60 * 60 * 1000; // 24 hours

// 清理旧版本缓存（清理 voice-guess- 开头但非当前前缀的项）
function cleanupLegacyCache() {
  try {
    const keys = Object.keys(localStorage);
    for (const key of keys) {
      if (key.startsWith('voice-guess-') && !key.startsWith(CACHE_PREFIX)) {
        localStorage.removeItem(key);
      }
    }
  } catch (e) {}
}

cleanupLegacyCache();

/**
 * 从缓存获取数据
 */
export function getCached(key) {
  try {
    const cached = localStorage.getItem(CACHE_PREFIX + key);
    if (!cached) return null;

    const { data, timestamp } = JSON.parse(cached);
    const age = Date.now() - timestamp;

    // Check if cache is expired
    if (age > CACHE_DURATION) {
      localStorage.removeItem(CACHE_PREFIX + key);
      return null;
    }

    return data;
  } catch (e) {
    return null;
  }
}

/**
 * 存入缓存
 */
export function setCache(key, data) {
  try {
    const entry = {
      data,
      timestamp: Date.now()
    };
    localStorage.setItem(CACHE_PREFIX + key, JSON.stringify(entry));
  } catch (e) {
    // localStorage full, clear old entries
    clearOldCache();
  }
}

/**
 * 清除过期缓存
 */
function clearOldCache() {
  try {
    const keys = Object.keys(localStorage);
    for (const key of keys) {
      if (key.startsWith(CACHE_PREFIX)) {
        try {
          const { timestamp } = JSON.parse(localStorage.getItem(key));
          if (Date.now() - timestamp > CACHE_DURATION) {
            localStorage.removeItem(key);
          }
        } catch (e) {
          localStorage.removeItem(key);
        }
      }
    }
  } catch (e) {} // 禁用存储时跳过缓存，不影响下载成功的数据。
}

/**
 * 清除所有缓存
 */
export function clearCache() {
  try {
    const keys = Object.keys(localStorage);
    for (const key of keys) {
      if (key.startsWith(CACHE_PREFIX)) {
        localStorage.removeItem(key);
      }
    }
  } catch (e) {}
}
