import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { test } from 'node:test';
import vm from 'node:vm';

const directory = new URL('./', import.meta.url);
const html = readFileSync(new URL('首页.html', directory), 'utf8');
const script = readFileSync(new URL('游戏逻辑.js', directory), 'utf8');

class Element {
  constructor(tagName = 'DIV') {
    this.tagName = tagName;
    this.children = [];
    this.listeners = new Map();
    this.attributes = new Map();
    this.dataset = {};
    this.textContent = '';
    this.value = '';
    this.hidden = false;
    this.disabled = false;
    const classes = new Set();
    this.classList = {
      add: (name) => classes.add(name),
      remove: (name) => classes.delete(name),
      contains: (name) => classes.has(name),
    };
  }

  addEventListener(name, listener) { this.listeners.set(name, listener); }
  dispatch(name) {
    this.listeners.get(name)?.({ key: '', preventDefault() {}, isComposing: false });
  }
  setAttribute(name, value) { this.attributes.set(name, String(value)); }
  getAttribute(name) { return this.attributes.get(name); }
  replaceChildren(...children) { this.children = children; }
  append(...children) { this.children.push(...children); }
  focus() {}
}

function fixture() {
  const operators = [
    { id: 'one', name: '甲', rarity: 1, profession: '先锋', archive: 'one.html' },
    { id: 'two', name: '乙', rarity: 2, profession: '近卫', archive: 'two.html' },
    { id: 'three', name: '丁', rarity: 3, profession: '狙击', archive: 'three.html' },
    { id: 'four', name: '戊', rarity: 4, profession: '医疗', archive: 'four.html' },
    { id: 'five', name: '己', rarity: 5, profession: '辅助', archive: 'five.html' },
    { id: 'six', name: '丙', rarity: 6, profession: '术师', archive: 'six.html' },
  ];
  const facts = [];
  const byOperator = [];
  const fallback = {};
  operators.forEach((operator, index) => {
    const indexes = [];
    for (let number = 0; number < 4; number++) {
      indexes.push(facts.length);
      facts.push({ id: `${operator.id}:${number}`, text: `线索 ${number}`,
        topic: `主题 ${number}`, family: '技能', members: [index],
        evidence: { [index]: ['档案', '依据'] } });
    }
    byOperator.push(indexes);
    fallback[index] = indexes;
  });
  return { version: 'test', operators, facts, byOperator, fallback };
}

function boot(saved = new Map(), data = fixture(), search = '') {
  const elements = new Map([...html.matchAll(/\bid="([^"]+)"/g)]
    .map(([, id]) => [id, new Element()]));
  const document = {
    getElementById: (id) => elements.get(id) ?? null,
    createElement: (tagName) => new Element(tagName.toUpperCase()),
  };
  let seed = 1;
  const window = {
    GUESS_DATA: data,
    location: { search },
    crypto: { getRandomValues(values) { values[0] = seed++; } },
    scrollTo() {},
  };
  const localStorage = {
    getItem: (key) => saved.get(key) ?? null,
    setItem: (key, value) => saved.set(key, value),
  };
  const searchIndexPath = new URL('干员搜索索引.js', directory);
  if (existsSync(searchIndexPath)) {
    vm.runInNewContext(readFileSync(searchIndexPath, 'utf8'), { window });
  }
  vm.runInNewContext(script, { document, window, localStorage, setTimeout, URLSearchParams });
  const element = (id) => elements.get(id);
  const rarityButton = (rarity) => {
    const button = element('rarity-filter')?.children
      .find((child) => child.dataset.rarity === String(rarity));
    assert.ok(button, `${rarity} 星筛选按钮应存在`);
    return button;
  };
  const selectedStars = () => [1, 2, 3, 4, 5, 6]
    .filter((rarity) => rarityButton(rarity).getAttribute('aria-pressed') === 'true');
  const record = () => JSON.parse(saved.get('sealed-dossier-history-v2'));
  const target = () => data.operators.find((operator) => operator.id === record().recentAnswers.at(-1));
  return { data, element, rarityButton, selectedStars, record, target, saved };
}

function selectOnly(game, rarity) {
  for (const other of [1, 2, 3, 4, 5, 6]) {
    if (other !== rarity) game.rarityButton(other).dispatch('click');
  }
}

test('selected stars limit both new answers and search suggestions', () => {
  const game = boot();
  selectOnly(game, 2);
  assert.deepEqual(game.selectedStars(), [2]);
  game.element('start-button').dispatch('click');
  assert.equal(game.target().rarity, 2);
  game.element('operator-search').value = '丙';
  game.element('operator-search').dispatch('input');
  assert.equal(game.element('suggestions').children.length, 0);
  game.element('operator-search').value = '乙';
  game.element('operator-search').dispatch('input');
  assert.equal(game.element('suggestions').children.length, 1);
});

test('last selected star cannot be deselected and selection survives reload', () => {
  const game = boot();
  selectOnly(game, 1);
  game.rarityButton(1).dispatch('click');
  assert.deepEqual(game.selectedStars(), [1]);
  const reloaded = boot(game.saved);
  assert.deepEqual(reloaded.selectedStars(), [1]);
  reloaded.element('start-button').dispatch('click');
  assert.equal(reloaded.target().rarity, 1);
});

test('excluding the current answer starts a fresh unscored round', () => {
  const game = boot();
  game.element('start-button').dispatch('click');
  const previous = game.target();
  game.element('next-button').dispatch('click');
  assert.match(game.element('stage-count').innerHTML, /^2 /);
  game.rarityButton(previous.rarity).dispatch('click');
  assert.notEqual(game.target().id, previous.id);
  assert.match(game.element('stage-count').innerHTML, /^1 /);
  assert.equal(game.element('guesses-list').textContent, '暂无');
  assert.equal(game.record().plays, 0);
  assert.equal(game.record().points, 0);
});

test('changing a different star keeps the current round', () => {
  const game = boot();
  game.element('start-button').dispatch('click');
  const previous = game.target();
  game.element('next-button').dispatch('click');
  const other = [1, 2, 6].find((rarity) => rarity !== previous.rarity);
  game.rarityButton(other).dispatch('click');
  assert.equal(game.target().id, previous.id);
  assert.match(game.element('stage-count').innerHTML, /^2 /);
});

test('a one-operator star pool can start another round', () => {
  const game = boot();
  selectOnly(game, 1);
  game.element('start-button').dispatch('click');
  game.element('give-up-button').dispatch('click');
  game.element('again-button').dispatch('click');
  assert.equal(game.element('game-screen').hidden, false);
  assert.equal(game.target().rarity, 1);
  assert.equal(game.record().plays, 1);
});

function searchGame() {
  const data = fixture();
  ['桃金娘', '德克萨斯', '斯卡蒂', '浊心斯卡蒂', '维什戴尔', '赤刃明霄陈']
    .forEach((name, index) => { data.operators[index].name = name; });
  const game = boot(new Map(), data);
  game.element('start-button').dispatch('click');
  return game;
}

function suggestionNames(game, query) {
  game.element('operator-search').value = query;
  game.element('operator-search').dispatch('input');
  return Array.from(game.element('suggestions').children, option => option.children[0].textContent);
}

test('nicknames and pinyin select the canonical operator in the clue game', () => {
  const game = searchGame();
  for (const query of ['火陈', 'huochen', 'CHI REN MING XIAO CHEN', 'crmxc', '赤刃明霄陈']) {
    assert.equal(suggestionNames(game, query)[0], '赤刃明霄陈', query);
  }
  game.element('suggestions').children[0].dispatch('click');
  assert.equal(game.element('operator-search').value, '赤刃明霄陈');
  assert.equal(game.element('submit-button').disabled, false);
});

test('shared nicknames keep every matching form and follow the star filter', () => {
  const game = searchGame();
  assert.deepEqual(suggestionNames(game, '蒂蒂').sort(), ['斯卡蒂', '浊心斯卡蒂']);
  game.rarityButton(4).dispatch('click');
  assert.deepEqual(suggestionNames(game, 'didi'), ['斯卡蒂']);
  assert.deepEqual(suggestionNames(game, '  '), []);
  assert.deepEqual(suggestionNames(game, '不存在的外号'), []);
});

test('URL target fixes the answer across rounds and reloads despite recent history', () => {
  const game = boot(new Map(), fixture(), '?target=甲');
  game.element('start-button').dispatch('click');
  assert.equal(game.target().name, '甲');
  game.element('give-up-button').dispatch('click');
  assert.equal(game.element('answer-name').textContent, '甲');
  game.element('again-button').dispatch('click');
  assert.equal(game.target().name, '甲');
  const reloaded = boot(game.saved, fixture(), '?target=甲');
  reloaded.element('start-button').dispatch('click');
  assert.equal(reloaded.target().name, '甲');
});

test('URL target follows the star filter and returns when its star is enabled', () => {
  const game = boot(new Map(), fixture(), '?target=甲');
  selectOnly(game, 2);
  game.element('start-button').dispatch('click');
  assert.equal(game.target().name, '乙');
  game.rarityButton(1).dispatch('click');
  game.element('give-up-button').dispatch('click');
  game.element('again-button').dispatch('click');
  assert.equal(game.target().name, '甲');
  game.rarityButton(1).dispatch('click');
  assert.equal(game.target().name, '乙');
});

test('URL target uses canonical-name priority and supports aliases and pinyin', () => {
  const data = fixture();
  ['桃金娘', '德克萨斯', '斯卡蒂', '浊心斯卡蒂', '维什戴尔', '赤刃明霄陈']
    .forEach((name, index) => { data.operators[index].name = name; });
  for (const [query, expected] of [
    ['火陈', '赤刃明霄陈'], ['huochen', '赤刃明霄陈'],
    ['CHI REN MING XIAO CHEN', '赤刃明霄陈'], ['crmxc', '赤刃明霄陈'],
    ['斯卡蒂', '斯卡蒂'], ['蒂蒂', '斯卡蒂'],
  ]) {
    const game = boot(new Map(), data, `?target=${encodeURIComponent(query)}`);
    game.element('start-button').dispatch('click');
    assert.equal(game.target().name, expected, query);
  }
});

test('invalid or unavailable URL targets fall back to a playable random round', () => {
  for (const search of ['?target=', '?target=%20%20', '?target=不存在的干员', '?target=%E0%A4%A']) {
    const game = boot(new Map(), fixture(), search);
    selectOnly(game, 2);
    game.element('start-button').dispatch('click');
    assert.equal(game.target().name, '乙', search);
  }
  const data = fixture();
  delete data.fallback[0];
  const game = boot(new Map(), data, '?target=甲');
  game.element('start-button').dispatch('click');
  assert.notEqual(game.target().name, '甲');
});
