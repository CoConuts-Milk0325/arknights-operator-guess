import { readFile, writeFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const escapeHtml = (value) => value.replaceAll('&', '&amp;').replaceAll('<', '&lt;')
  .replaceAll('>', '&gt;').replaceAll('"', '&quot;');

function inline(value) {
  return escapeHtml(value)
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_, label, url) =>
      `<a href="${escapeHtml(url)}">${label}</a>`)
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
}

function renderMarkdown(source) {
  const lines = source.replace(/\r\n/g, '\n').split('\n');
  const sections = [];
  const faqItems = [];
  const body = [];
  let title = '';
  let lead = '';
  let paragraph = [];
  let list = null;
  let sectionNumber = 0;
  let subNumber = 0;
  let inFaqSection = false;
  let faqSectionId = '';

  const flushParagraph = () => {
    if (paragraph.length) body.push(`<p>${inline(paragraph.join(' '))}</p>`);
    paragraph = [];
  };
  const closeList = () => {
    if (list) body.push(`</${list}>`);
    list = null;
  };

  for (let index = 0; index < lines.length; index++) {
    const line = lines[index].trim();
    if (!line) { flushParagraph(); closeList(); continue; }
    if (line.startsWith('# ')) { title = line.slice(2); continue; }
    if (!lead && !sections.length && !line.startsWith('## ')) { lead = line; continue; }

    const heading = line.match(/^(#{2,3}) (.+)$/);
    if (heading) {
      flushParagraph(); closeList();
      if (heading[1].length === 2) {
        if (sectionNumber > 0) body.push('</section>');
        sectionNumber++;
        subNumber = 0;
        const id = `section-${sectionNumber}`;
        inFaqSection = heading[2].includes('常见疑问');
        if (inFaqSection) faqSectionId = id;
        sections.push({ id, text: heading[2], children: [] });
        body.push(`<section class="doc-section" aria-labelledby="${id}"><div class="section-label">SECTION ${String(sectionNumber).padStart(2, '0')}</div><h2 id="${id}">${inline(heading[2])}</h2>`);
      } else {
        subNumber++;
        const id = `section-${sectionNumber}-${subNumber}`;
        sections.at(-1)?.children.push({ id, text: heading[2] });
        body.push(`<h3 id="${id}">${inline(heading[2])}</h3>`);
      }
      continue;
    }
    if (/^---+$/.test(line)) { flushParagraph(); closeList(); body.push('<hr>'); continue; }

    if (line.startsWith('|')) {
      flushParagraph(); closeList();
      const rows = [];
      while (index < lines.length && lines[index].trim().startsWith('|')) {
        const cells = lines[index].trim().replace(/^\||\|$/g, '').split('|').map((cell) => cell.trim());
        if (!cells.every((cell) => /^:?-{3,}:?$/.test(cell))) rows.push(cells);
        index++;
      }
      index--;
      const [head, ...rest] = rows;
      body.push('<div class="table-scroll"><table><thead><tr>'
        + head.map((cell) => `<th scope="col">${inline(cell)}</th>`).join('')
        + '</tr></thead><tbody>'
        + rest.map((row) => `<tr>${row.map((cell) => `<td>${inline(cell)}</td>`).join('')}</tr>`).join('')
        + '</tbody></table></div>');
      continue;
    }

    const faq = inFaqSection && line.match(/^\*\*(.+?[？?])\*\*\s*(.+)$/);
    if (faq) {
      flushParagraph(); closeList();
      faqItems.push({ question: faq[1], answer: faq[2] });
      body.push(`<div class="faq-item"><h3>${inline(faq[1])}</h3><p>${inline(faq[2])}</p></div>`);
      continue;
    }

    const ordered = line.match(/^\d+\. (.+)$/);
    const bullet = line.match(/^- (.+)$/);
    if (ordered || bullet) {
      flushParagraph();
      const kind = ordered ? 'ol' : 'ul';
      if (list !== kind) { closeList(); body.push(`<${kind}>`); list = kind; }
      body.push(`<li>${inline((ordered || bullet)[1])}</li>`);
      continue;
    }
    closeList();
    paragraph.push(line);
  }
  flushParagraph(); closeList();

  const navigation = sections.map(({ id, text, children }) =>
    `<li><a href="#${id}">${escapeHtml(text)}</a>${children.length
      ? `<ul>${children.map((child) => `<li><a href="#${child.id}">${escapeHtml(child.text)}</a></li>`).join('')}</ul>`
      : ''}</li>`).join('');

  return { title, lead, navigation, body: body.join('\n'), faqItems, faqSectionId };
}

export async function generateRulePage(gameDirectory) {
  const markdown = await readFile(join(gameDirectory, '玩家规则.md'), 'utf8');
  const { title, lead, navigation, body, faqItems, faqSectionId } = renderMarkdown(markdown);
  const homepagePath = join(gameDirectory, '首页.html');
  const homepage = await readFile(homepagePath, 'utf8');
  const faqPattern = /(<div class="faq-grid">)[\s\S]*?(<\/div>\s*<\/aside>)/;
  if (!faqItems.length || !faqPattern.test(homepage)) {
    throw new Error('未找到玩家规则中的常见疑问或首页问答容器，无法同步规则页面');
  }
  const faqHtml = faqItems.map(({ question, answer }) =>
    `        <details><summary>${inline(question)}</summary><p>${inline(answer)}</p></details>`).join('\n');
  const updatedHomepage = homepage.replace(faqPattern, (_, opening, closing) =>
    `${opening}\n${faqHtml}\n      ${closing}`)
    .replace(/href="规则说明\.html#section-\d+"/, `href="规则说明.html#${faqSectionId}"`);
  const displayTitle = title.replace(/^密封档案 · /, '').replace('｜完整玩家规则', '玩家规则');
  const html = `<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#f7f8f6">
  <title>说明文档 · 密封档案</title>
  <link rel="stylesheet" href="规则说明.css">
</head>
<body>
  <a class="skip-link" href="#content">跳转到正文</a>
  <header class="docs-header">
    <a class="docs-brand" href="首页.html" aria-label="返回猜干员游戏"><span class="brand-symbol" aria-hidden="true">◈</span><span>密封档案<small>RHODES ISLAND / CLUES</small></span></a>
    <span class="header-type">说明文档 <span aria-hidden="true">/</span> 玩家规则</span>
    <a class="back-link" href="首页.html">返回游戏 <span aria-hidden="true">↗</span></a>
  </header>
  <div class="docs-layout">
    <aside class="docs-sidebar" aria-label="文档目录">
      <div class="sidebar-inner">
        <p class="nav-eyebrow">DOCUMENTATION</p>
        <p class="nav-heading">规则目录</p>
        <nav><ol>${navigation}</ol></nav>
        <div class="sidebar-foot"><span class="foot-mark" aria-hidden="true">◈</span> 四条线索，锁定一名干员。</div>
      </div>
    </aside>
    <main class="docs-main" id="content">
      <div class="docs-content">
        <div class="breadcrumb"><a href="首页.html">猜干员</a><span>/</span><span>说明文档</span></div>
        <div class="hero-label"><span class="hero-line" aria-hidden="true"></span> GAME MANUAL <span class="hero-version">当前资料快照</span></div>
        <h1>${inline(displayTitle)}</h1>
        <p class="lead">${inline(lead)}</p>
        <div class="at-a-glance" aria-label="快速了解"><strong>先了解这局游戏</strong><div><span>每局 4 条线索</span><span>猜错自动揭示下一条</span><span>四条公开后仍可继续猜</span></div></div>
        <details class="mobile-navigation"><summary>查看规则目录</summary><nav aria-label="移动端文档目录"><ol>${navigation}</ol></nav></details>
        <article class="rule-article">${body}\n</section></article>
        <footer class="article-footer"><span>档案阅读完毕</span><a href="首页.html">返回游戏继续猜 <span aria-hidden="true">↗</span></a></footer>
      </div>
    </main>
  </div>
  <script>
    const links = [...document.querySelectorAll('.docs-sidebar nav a')];
    const observed = links.map((link) => document.getElementById(link.hash.slice(1))).filter(Boolean);
    if ('IntersectionObserver' in window) {
      const observer = new IntersectionObserver((entries) => {
        const visible = entries.filter((entry) => entry.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
        if (!visible) return;
        links.forEach((link) => link.classList.toggle('active', link.hash === '#' + visible.target.id));
      }, { rootMargin: '-12% 0px -75% 0px' });
      observed.forEach((item) => observer.observe(item));
    }
  </script>
</body>
</html>\n`;
  await writeFile(join(gameDirectory, '规则说明.html'), html, 'utf8');
  if (updatedHomepage !== homepage) await writeFile(homepagePath, updatedHomepage, 'utf8');
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  await generateRulePage(dirname(fileURLToPath(import.meta.url)));
}
