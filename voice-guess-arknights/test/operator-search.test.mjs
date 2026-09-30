import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { test } from 'node:test'
import { loadOperators, searchOperators } from '../src/logic/operatorSearch.js'

const sourceOperators = JSON.parse(await readFile(new URL('../public/data/operators.json', import.meta.url), 'utf8'))
const previousFetch = globalThis.fetch
let operators
try {
  globalThis.fetch = async () => ({ ok: true, json: async () => sourceOperators })
  operators = await loadOperators()
} finally {
  globalThis.fetch = previousFetch
}

test('the final nickname table resolves aliases and their pinyin to canonical names', () => {
  for (const [query, expected] of [
    ['火陈', '赤刃明霄陈'], ['HUO CHEN', '赤刃明霄陈'],
    ['crmxc', '赤刃明霄陈'], ['小羊', '艾雅法拉'],
    ['xiaoyang', '艾雅法拉'], ['42', '史尔特尔'],
    ['EW', '维什戴尔'], ['奶羊', '纯烬艾雅法拉'],
    ['chongyue', '重岳'], ['qiubai', '仇白'],
  ]) {
    assert.equal(searchOperators(query, operators)[0]?.name, expected, query)
  }
})

test('shared aliases retain all candidates and exact names win over another operator alias', () => {
  for (const query of ['蒂蒂', 'didi']) {
    assert.deepEqual(searchOperators(query, operators).slice(0, 2).map(op => op.name).sort(), ['斯卡蒂', '浊心斯卡蒂'])
  }
  assert.equal(searchOperators('苇草', operators)[0]?.name, '苇草')
  assert.equal(searchOperators('夜刀', operators)[0]?.name, '夜刀')
  const filtered = operators.filter(op => op.name !== '浊心斯卡蒂')
  assert.equal(searchOperators('红蒂', filtered).length, 0)
  assert.deepEqual(searchOperators(' -- ', operators), [])
  assert.deepEqual(searchOperators('不存在的干员外号', operators), [])
})
