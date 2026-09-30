(() => {
  "use strict";

  const data = window.GUESS_DATA;
  const $ = (id) => document.getElementById(id);
  const ui = Object.fromEntries([
    "data-status", "rules-toggle", "rules-panel", "intro-screen", "start-button",
    "game-screen", "round-label", "stage-count", "score-label", "clue-list",
    "operator-search", "suggestions", "selected-operator", "submit-button",
    "next-button", "give-up-button", "feedback", "guesses-list", "result-screen",
    "result-kicker", "result-title", "result-subtitle", "result-score", "answer-name",
    "answer-meta", "evidence-list", "archive-link", "again-button", "record-summary",
    "clear-record-button", "rarity-filter", "rarity-count",
  ].map((id) => [id, $(id)]));

  if (!data || !Array.isArray(data.operators) || !Array.isArray(data.facts)) {
    ui["data-status"].textContent = "档案数据未加载";
    ui["start-button"].disabled = true;
    return;
  }

  const STORAGE_KEY = "sealed-dossier-history-v2";
  const RARITY_KEY = "sealed-dossier-rarities-v1";
  const allIndexes = data.operators.map((_, index) => index);
  const searchIndex = data.operators.map((operator) => {
    const name = normalizeSearch(operator.name);
    const entry = (window.OPERATOR_SEARCH_INDEX || {})[name] || {};
    return {
      name,
      aliases: (entry.aliases || []).map(normalizeSearch),
      pinyin: entry.pinyinFull || [],
      initials: entry.pinyinInitials || [],
    };
  });
  const memberSets = data.facts.map((fact) => new Set(fact.possibleMembers || fact.members));
  const eligible = Object.keys(data.fallback).map(Number).filter(Number.isInteger);
  const rarities = [...new Set(eligible.map((index) => Number(data.operators[index].rarity)))].sort((a, b) => a - b);
  let selectedRarities = readRarities();
  let record = readRecord();
  let round = null;
  let selected = null;
  let suggestions = [];
  let highlighted = -1;

  function readRarities() {
    try {
      const saved = JSON.parse(localStorage.getItem(RARITY_KEY) || "null");
      if (Array.isArray(saved)) {
        const valid = saved.filter((rarity) => rarities.includes(rarity));
        if (valid.length) return new Set(valid);
      }
    } catch (_) { /* 本地存储不可用时使用全部星级。 */ }
    return new Set(rarities);
  }

  function rarityPool() {
    return eligible.filter((index) => selectedRarities.has(Number(data.operators[index].rarity)));
  }

  function renderRarityFilter() {
    if (!ui["rarity-filter"].children.length) {
      ui["rarity-filter"].replaceChildren(...rarities.map((rarity) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "rarity-button";
        button.dataset.rarity = String(rarity);
        button.textContent = `${rarity} 星`;
        button.addEventListener("click", () => {
          if (selectedRarities.has(rarity) && selectedRarities.size === 1) return;
          if (selectedRarities.has(rarity)) selectedRarities.delete(rarity);
          else selectedRarities.add(rarity);
          try { localStorage.setItem(RARITY_KEY, JSON.stringify([...selectedRarities])); }
          catch (_) { /* 无法保存偏好时仍可筛选。 */ }
          renderRarityFilter();
          if (round && !round.finished && !selectedRarities.has(Number(data.operators[round.target].rarity))) {
            begin("星级范围已更新，已重新抽题。");
          } else if (round && !round.finished) {
            if (selected !== null && !selectedRarities.has(Number(data.operators[selected].rarity))) clearSelection();
            else if (selected === null) renderSuggestions();
          }
        });
        return button;
      }));
    }
    for (const button of ui["rarity-filter"].children) {
      button.setAttribute("aria-pressed", String(selectedRarities.has(Number(button.dataset.rarity))));
    }
    ui["rarity-count"].textContent = `${rarityPool().length} 名可出题`;
  }

  function readRecord() {
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
      if (saved && typeof saved === "object") {
        return {
          plays: Number(saved.plays) || 0,
          points: Number(saved.points) || 0,
          recentAnswers: Array.isArray(saved.recentAnswers) ? saved.recentAnswers.slice(-eligible.length) : [],
          recentSignatures: Array.isArray(saved.recentSignatures) ? saved.recentSignatures.slice(-240) : [],
          recentFacts: Array.isArray(saved.recentFacts) ? saved.recentFacts.slice(-160) : [],
          recentTopics: Array.isArray(saved.recentTopics) ? saved.recentTopics.slice(-80) : [],
        };
      }
    } catch (_) { /* 本地存储不可用时继续游玩。 */ }
    return { plays: 0, points: 0, recentAnswers: [], recentSignatures: [], recentFacts: [], recentTopics: [] };
  }

  function saveRecord() {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(record)); } catch (_) { /* 使用内存记录。 */ }
    ui["record-summary"].textContent = `已完成 ${record.plays} 局 · 总分 ${record.points}`;
  }

  function seededRandom(seed) {
    let value = seed >>> 0;
    return () => {
      value += 0x6d2b79f5;
      let mixed = value;
      mixed = Math.imul(mixed ^ (mixed >>> 15), mixed | 1);
      mixed ^= mixed + Math.imul(mixed ^ (mixed >>> 7), mixed | 61);
      return ((mixed ^ (mixed >>> 14)) >>> 0) / 4294967296;
    };
  }

  function newSeed() {
    if (window.crypto && window.crypto.getRandomValues) {
      const buffer = new Uint32Array(1);
      window.crypto.getRandomValues(buffer);
      return buffer[0];
    }
    return (Date.now() ^ Math.floor(Math.random() * 0xffffffff)) >>> 0;
  }

  function shuffle(values, random) {
    const result = values.slice();
    for (let index = result.length - 1; index > 0; index--) {
      const other = Math.floor(random() * (index + 1));
      [result[index], result[other]] = [result[other], result[index]];
    }
    return result;
  }

  function intersect(current, factIndex) {
    const allowed = memberSets[factIndex];
    return current.filter((index) => allowed.has(index));
  }

  function uniqueCombination(target, random) {
    const possible = data.byOperator[target];
    if (!possible || possible.length < 4) return null;
    const anchorIds = new Set(["attack:true_aoe", "combo:outside_and_shrink",
      "range:two_skills_outside", "heal:hunger", "ally:output_multi", "ally:survival_nonheal"]);
    possible.forEach((index) => {
      const id = data.facts[index].id;
      if (id.startsWith("attack:skill_targets:")) anchorIds.add(id);
    });
    const recentUse = new Map();
    for (const id of record.recentFacts) recentUse.set(id, (recentUse.get(id) || 0) + 1);
    const recentTopicUse = new Map();
    for (const topic of record.recentTopics) recentTopicUse.set(topic, (recentTopicUse.get(topic) || 0) + 1);
    for (let attempt = 0; attempt < 180; attempt++) {
      let candidates = allIndexes;
      const chosen = [];
      const usedTopics = new Set();
      const pool = shuffle(possible, random);
      for (let stage = 0; stage < 4; stage++) {
        const options = [];
        for (const factIndex of pool) {
          const fact = data.facts[factIndex];
          if (usedTopics.has(fact.topic)) continue;
          if (chosen.some((index) => {
            const other = data.facts[index].id;
            const isDamageControlCombo = (id) => ["combo:one_damage_no_control", "combo:two_damage_one_control"].includes(id);
            return (isDamageControlCombo(fact.id) && /^(damage|control):/.test(other))
              || (isDamageControlCombo(other) && /^(damage|control):/.test(fact.id));
          })) continue;
          if (["统计", "数值"].includes(fact.family) &&
              chosen.some((index) => ["统计", "数值"].includes(data.facts[index].family))) continue;
          if (fact.family === "复合" && chosen.some((index) => data.facts[index].family === "复合")) continue;
          if (chosen.some((index) => {
            const previous = data.facts[index];
            return (fact.implies || []).includes(previous.id)
              || (previous.implies || []).includes(fact.id);
          })) continue;
          const next = intersect(candidates, factIndex);
          if (stage < 3 && next.length < 2) continue;
          if (stage === 3 && next.length !== 1) continue;
          if (stage < 2 && next.length === candidates.length) continue;
          const quality = anchorIds.has(fact.id) ? 3 : fact.family === "复合" || fact.id.startsWith("control:can:")
            || ["技能", "攻击", "恢复", "范围", "削弱", "生存", "阻挡", "召唤"].includes(fact.family)
            ? 2 : ["伤害", "支援", "目标"].includes(fact.family) ? 1 : fact.family === "数值" ? -2 : 0;
          const repeated = Math.min(recentUse.get(fact.id) || 0, 4);
          const repeatedTopic = Math.min(recentTopicUse.get(fact.topic) || 0, 5);
          options.push({ factIndex, next, rank: Math.log2(next.length) - quality * 0.55
            + repeated * 0.45 + repeatedTopic * 0.2,
            jitter: random() });
        }
        if (!options.length) break;
        options.sort((a, b) => a.rank - b.rank || a.jitter - b.jitter);
        const picked = options[Math.floor(random() * Math.min(8, options.length))];
        chosen.push(picked.factIndex);
        usedTopics.add(data.facts[picked.factIndex].topic);
        candidates = picked.next;
      }
      if (chosen.length === 4 && candidates.length === 1 && candidates[0] === target &&
          new Set(chosen.map((index) => data.facts[index].family)).size >= 3) {
        return chosen;
      }
    }
    const fallback = data.fallback[target];
    if (Array.isArray(fallback) && fallback.length === 4) {
      const finalCandidates = fallback.reduce((candidates, index) => intersect(candidates, index), allIndexes);
      if (finalCandidates.length === 1 && finalCandidates[0] === target) return fallback.slice();
    }
    return null;
  }

  function createRound(seed, target) {
    if (!eligible.length) return null;
    const random = seededRandom(seed);
    const facts = uniqueCombination(target, random);
    if (!facts) return null;
    const signature = `${data.version}:${data.operators[target].id}:${facts.map((index) => data.facts[index].id).sort().join("|")}`;
    return { seed, target, facts, signature, stage: 1, guesses: [], finished: false };
  }

  function chooseRound() {
    const pool = rarityPool();
    let unseen = pool.filter((index) => !record.recentAnswers.includes(data.operators[index].id));
    if (!unseen.length) {
      unseen = pool;
    }
    const random = seededRandom(newSeed());
    const sampled = shuffle(unseen, random).slice(0, 14);
    const recentUse = new Map();
    for (const id of record.recentFacts) recentUse.set(id, (recentUse.get(id) || 0) + 1);
    const recentTopicUse = new Map();
    for (const topic of record.recentTopics) recentTopicUse.set(topic, (recentTopicUse.get(topic) || 0) + 1);
    let best = null;
    let bestScore = Infinity;
    for (const target of sampled) {
      const candidate = createRound(newSeed(), target);
      if (!candidate) continue;
      const repeatedClues = candidate.facts.reduce((sum, index) =>
        sum + (recentUse.get(data.facts[index].id) || 0), 0);
      const repeatedTopics = candidate.facts.reduce((sum, index) =>
        sum + (recentTopicUse.get(data.facts[index].topic) || 0), 0);
      const numeric = candidate.facts.filter((index) => data.facts[index].family === "数值").length;
      const score = repeatedClues + repeatedTopics * 0.3 + numeric * 0.7
        + (record.recentSignatures.includes(candidate.signature) ? 20 : 0);
      if (score < bestScore) { best = candidate; bestScore = score; }
      if (score === 0) break;
    }
    return best;
  }

  function showScreen(name) {
    ui["intro-screen"].hidden = name !== "intro";
    ui["game-screen"].hidden = name !== "game";
    ui["result-screen"].hidden = name !== "result";
    window.scrollTo({ top: 0, behavior: "auto" });
  }

  function card(number, text, locked) {
    const item = document.createElement("li");
    item.className = `clue-card${locked ? " locked" : ""}`;
    const marker = document.createElement("span");
    marker.className = "clue-number";
    marker.textContent = String(number).padStart(2, "0");
    const body = document.createElement("span");
    body.className = "clue-content";
    body.textContent = locked ? "尚未公开 / SEALED" : text;
    item.append(marker, body);
    return item;
  }

  function renderGame(message = "") {
    ui["round-label"].textContent = `档案 ${String(record.plays + 1).padStart(3, "0")}`;
    ui["stage-count"].innerHTML = `${round.stage} <small>/ 4</small>`;
    ui["score-label"].textContent = `当前可得 ${5 - round.stage} 分`;
    ui["clue-list"].replaceChildren(...round.facts.map((index, place) =>
      card(place + 1, data.facts[index].text, place >= round.stage)));
    ui["guesses-list"].textContent = round.guesses.length
      ? round.guesses.map((index) => data.operators[index].name).join("、") : "暂无";
    ui["next-button"].disabled = round.stage === 4;
    ui["feedback"].textContent = message;
    clearSelection();
  }

  function clearSelection() {
    selected = null;
    ui["operator-search"].value = "";
    ui["selected-operator"].textContent = "尚未选择干员";
    ui["selected-operator"].classList.remove("has-selection");
    ui["submit-button"].disabled = true;
    hideSuggestions();
  }

  function hideSuggestions() {
    suggestions = [];
    highlighted = -1;
    ui["suggestions"].hidden = true;
    ui["suggestions"].replaceChildren();
    ui["operator-search"].setAttribute("aria-expanded", "false");
  }

  function renderSuggestions() {
    const query = normalizeSearch(ui["operator-search"].value);
    if (!query || !round || round.finished) { hideSuggestions(); return; }
    suggestions = allIndexes
      .filter((index) => selectedRarities.has(Number(data.operators[index].rarity)))
      .map((index) => ({ index, score: scoreSearch(searchIndex[index], query) }))
      .filter((match) => match.score > 0)
      .sort((a, b) => b.score - a.score
        || data.operators[a.index].name.length - data.operators[b.index].name.length)
      .slice(0, 9).map((match) => match.index);
    if (!suggestions.length) { hideSuggestions(); return; }
    ui["suggestions"].replaceChildren(...suggestions.map((index, position) => {
      const option = document.createElement("button");
      option.type = "button";
      option.className = `suggestion${position === highlighted ? " active" : ""}`;
      option.setAttribute("role", "option");
      option.setAttribute("aria-selected", String(position === highlighted));
      const label = document.createElement("span");
      label.textContent = data.operators[index].name;
      const meta = document.createElement("small");
      meta.textContent = data.operators[index].profession;
      option.append(label, meta);
      option.addEventListener("click", () => selectOperator(index));
      return option;
    }));
    ui["suggestions"].hidden = false;
    ui["operator-search"].setAttribute("aria-expanded", "true");
  }

  function normalizeSearch(value) {
    return value.normalize("NFKC").toLowerCase().replace(/[üǖǘǚǜ]/g, "v")
      .normalize("NFD").replace(/\p{M}/gu, "").replace(/[^\p{L}\p{N}]/gu, "");
  }

  function scoreSearch(entry, query) {
    const score = (values, exact, prefix, partial = 0) => Math.max(0, ...values.map((value) =>
      value === query ? exact : value.startsWith(query) ? prefix : value.includes(query) ? partial : 0));
    return Math.max(
      score([entry.name], 1000, 800, 600),
      score(entry.aliases, 900, 650, 450),
      score(entry.pinyin, 750, 550, 300),
      score(entry.initials, 500, 400),
    );
  }

  function selectOperator(index) {
    selected = index;
    ui["operator-search"].value = data.operators[index].name;
    ui["selected-operator"].textContent = `已选择：${data.operators[index].name}`;
    ui["selected-operator"].classList.add("has-selection");
    ui["submit-button"].disabled = false;
    hideSuggestions();
    ui["submit-button"].focus();
  }

  function begin(message = "") {
    round = chooseRound();
    if (!round) {
      ui["data-status"].textContent = "当前档案未能生成唯一题目";
      return;
    }
    record.recentAnswers.push(data.operators[round.target].id);
    record.recentAnswers = record.recentAnswers.slice(-eligible.length);
    record.recentSignatures.push(round.signature);
    record.recentSignatures = record.recentSignatures.slice(-240);
    record.recentFacts.push(...round.facts.map((index) => data.facts[index].id));
    record.recentFacts = record.recentFacts.slice(-160);
    record.recentTopics.push(...round.facts.map((index) => data.facts[index].topic));
    record.recentTopics = record.recentTopics.slice(-80);
    saveRecord();
    showScreen("game");
    renderGame(message);
    ui["operator-search"].focus();
  }

  function submitGuess() {
    if (!round || round.finished || selected === null) return;
    if (round.guesses.includes(selected)) {
      ui["feedback"].textContent = "这名干员已经猜过，请换一个答案。";
      return;
    }
    const guess = selected;
    round.guesses.push(guess);
    if (guess === round.target) {
      finish(true);
    } else {
      if (round.stage < 4) {
        round.stage++;
        renderGame(`不是 ${data.operators[guess].name}。已公开下一条线索。`);
      } else {
        renderGame(`不是 ${data.operators[guess].name}。四条线索已全部公开，可以继续猜。`);
      }
      ui["operator-search"].focus();
    }
  }

  function revealNext() {
    if (!round || round.finished || round.stage >= 4) return;
    round.stage++;
    renderGame("下一条线索已公开。");
  }

  function finish(correct) {
    if (!round || round.finished) return;
    round.finished = true;
    const gained = correct ? 5 - round.stage : 0;
    record.plays++;
    record.points += gained;
    saveRecord();
    const operator = data.operators[round.target];
    ui["result-kicker"].textContent = correct ? "目标已确认 / 档案解封" : "本局结束 / 档案解封";
    ui["result-title"].textContent = correct ? "猜中了。" : "答案揭晓。";
    ui["result-subtitle"].textContent = correct ? `在第 ${round.stage} 条线索阶段确认目标。` : "已放弃本题，答案与线索依据如下。";
    ui["result-score"].innerHTML = `+${gained} <small>分</small>`;
    ui["answer-name"].textContent = operator.name;
    ui["answer-meta"].textContent = `${operator.rarity} 星 · ${operator.profession}`;
    ui["archive-link"].href = operator.archive;
    ui["evidence-list"].replaceChildren(...round.facts.map((factIndex, place) => {
      const fact = data.facts[factIndex];
      const source = fact.evidence[round.target] || ["本地档案", "来源记录缺失"];
      const item = document.createElement("li");
      item.className = "evidence-card";
      const heading = document.createElement("strong");
      heading.textContent = `${String(place + 1).padStart(2, "0")} / ${fact.text}`;
      const quote = document.createElement("p");
      quote.textContent = source[1];
      const label = document.createElement("small");
      label.textContent = `依据：${source[0]}`;
      item.append(heading, quote, label);
      return item;
    }));
    showScreen("result");
    ui["again-button"].focus();
  }

  ui["rules-toggle"].addEventListener("click", () => {
    const opening = ui["rules-panel"].hidden;
    ui["rules-panel"].hidden = !opening;
    ui["rules-toggle"].setAttribute("aria-expanded", String(opening));
  });
  ui["start-button"].addEventListener("click", () => begin());
  ui["again-button"].addEventListener("click", () => begin());
  ui["submit-button"].addEventListener("click", submitGuess);
  ui["next-button"].addEventListener("click", revealNext);
  ui["give-up-button"].addEventListener("click", () => finish(false));
  ui["operator-search"].addEventListener("input", () => {
    selected = null;
    ui["selected-operator"].textContent = "尚未选择干员";
    ui["selected-operator"].classList.remove("has-selection");
    ui["submit-button"].disabled = true;
    highlighted = -1;
    renderSuggestions();
  });
  ui["operator-search"].addEventListener("keydown", (event) => {
    if (event.isComposing || event.keyCode === 229) return;
    if (event.key === "Escape") { hideSuggestions(); return; }
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      if (!suggestions.length) return;
      event.preventDefault();
      highlighted = (highlighted + (event.key === "ArrowDown" ? 1 : -1) + suggestions.length) % suggestions.length;
      renderSuggestions();
    } else if (event.key === "Enter") {
      event.preventDefault();
      if (suggestions.length) selectOperator(suggestions[Math.max(0, highlighted)]);
      else if (selected !== null) submitGuess();
    }
  });
  ui["operator-search"].addEventListener("blur", () => setTimeout(hideSuggestions, 160));
  ui["clear-record-button"].addEventListener("click", () => {
    record = { plays: 0, points: 0, recentAnswers: [], recentSignatures: [], recentFacts: [], recentTopics: [] };
    saveRecord();
    ui["clear-record-button"].textContent = "已清除";
    setTimeout(() => { ui["clear-record-button"].textContent = "清除记录"; }, 1800);
  });

  ui["data-status"].textContent = `${data.operators.length} 名干员 · 本地快照`;
  ui["start-button"].disabled = eligible.length === 0;
  renderRarityFilter();
  saveRecord();
})();
