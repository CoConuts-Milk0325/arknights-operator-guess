const 检索框 = document.getElementById("档案检索");
const 结果文字 = document.getElementById("检索结果");
检索框.placeholder = "输入名字、技能或天赋关键词";
const 条目 = [...document.querySelectorAll(".干员条目")];
const 栏目名称 = ["技能", "天赋"];
const 内容索引 = window.档案检索索引 || {};
const 预处理索引 = new Map();

for (const 卡片 of 条目) {
  const 记录 = 内容索引[卡片.dataset.key] || [];
  const 原文 = 记录.length >= 4 ? [记录[0], 记录[3]] : [记录[0] || "", 记录[1] || ""];
  预处理索引.set(卡片, {
    原文,
    小写: 原文.map((文本) => 文本.toLocaleLowerCase()),
    名称: 卡片.querySelector(".干员名").textContent.toLocaleLowerCase(),
  });
}

function 摘要(原文, 小写, 查询词) {
  const 位置 = 小写.indexOf(查询词);
  if (位置 < 0) return "";
  const 起点 = Math.max(0, 位置 - 20);
  const 终点 = Math.min(原文.length, 位置 + 查询词.length + 30);
  return (起点 ? "…" : "") + 原文.slice(起点, 终点).trim() + (终点 < 原文.length ? "…" : "");
}

function 更新检索结果() {
  const 查询词 = 检索框.value.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
  const 完整查询 = 查询词.join(" ");
  let 命中数 = 0;
  for (const 卡片 of 条目) {
    const 索引 = 预处理索引.get(卡片);
    const 可检索 = [索引.名称, ...索引.小写];
    const 匹配 = 查询词.every((词) => 可检索.some((文本) => 文本.includes(词)));
    卡片.hidden = !匹配;
    if (!匹配) continue;
    命中数 += 1;

    const 代号 = 卡片.querySelector(".干员名").textContent.toLocaleLowerCase();
    let 顺序 = 6;
    if (查询词.length) {
      if (代号 === 完整查询) 顺序 = 0;
      else if (索引.名称.includes(完整查询)) 顺序 = 1;
      else {
        const 栏目 = 索引.小写.findIndex((文本) => 查询词.some((词) => 文本.includes(词)));
        if (栏目 >= 0) 顺序 = 栏目 + 2;
      }
    }
    卡片.style.order = String(顺序);

    const 提示 = 卡片.querySelector(".匹配提示");
    if (!提示) continue;
    const 命中栏目 = 索引.小写.findIndex((文本) => 查询词.some((词) => 文本.includes(词)));
    if (查询词.length && 顺序 > 1 && 命中栏目 >= 0) {
      const 命中词 = 查询词.find((词) => 索引.小写[命中栏目].includes(词));
      提示.textContent = 栏目名称[命中栏目] + "：" + 摘要(索引.原文[命中栏目], 索引.小写[命中栏目], 命中词);
      提示.hidden = false;
    } else {
      提示.textContent = "";
      提示.hidden = true;
    }
  }
  for (const 分组 of document.querySelectorAll(".职业组")) {
    const 可见条目 = [...分组.querySelectorAll(".干员条目")].filter((卡片) => !卡片.hidden);
    分组.hidden = !可见条目.length;
    分组.style.order = 查询词.length && 可见条目.length
      ? String(Math.min(...可见条目.map((卡片) => Number(卡片.style.order))))
      : "0";
  }
  结果文字.textContent = 命中数 + " 条档案";
}

let 待检索计时器;
检索框.addEventListener("input", (事件) => {
  if (事件.isComposing) return;
  clearTimeout(待检索计时器);
  待检索计时器 = setTimeout(更新检索结果, 60);
});
检索框.addEventListener("compositionend", () => {
  clearTimeout(待检索计时器);
  更新检索结果();
});
