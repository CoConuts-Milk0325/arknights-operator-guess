# 语音猜干员

根据《明日方舟》干员语音猜干员的 Vue 3 + Vite 网页游戏。

统一站点配置地址：https://coconutsmilk.top/voice/

本目录已合并为 `arknights-operator-guess` 仓库的普通源码目录。日常构建、测试与整站预览优先使用上一级 README 的根目录命令；所有修改只向主仓库提交。原独立域名及本目录中的 CNAME、GitHub Pages 工作流为历史独立部署配置，不参与整站构建。

## 本地开发

使用 Node.js 24：

```powershell
npm ci
npm run dev
```

开发默认端口 5173。`start.bat` 也启动 Vite，但会强制结束占用 5173 的进程。

## 功能与规则

- 中文、日文、方言、皮肤语音，支持星级与语音类型筛选。
- 输入模式与选择模式；选择项数量跟随最大猜测次数，默认 10。
- 挑战题数 3～20，默认 10；开始前检查筛选后有足够可播放语音，同轮干员不重复。
- 评级按本轮可得满分折算；连胜仅统计，无额外加分。

## 验证与构建

```powershell
npm test
npm run verify:data
npm run build
npm run preview
```

数据更新后修改 `src/dataVersion.js` 的唯一版本号，同时刷新 HTTP 和 localStorage 数据缓存。

## 音频与代理

分片里的音频路径带源前缀：`bwiki:` 指向 B 站自有 CDN（`patchwiki.biligame.com`，32022 条中的 31864 条），无前缀或 `prts:` 指向 torappu 镜像（158 条：bwiki 该单元格没有文件、行文本对不上条数、或 bwiki 单元格串了别人的录音）。每条 `bwiki:` 条目都额外带一个 `alt`（PRTS 同名 `.mp3`），`src/config.js` 的 `getAudioUrl` / `getFallbackUrl` 按前缀选源并把 `.wav` 换成 `.mp3`，`AudioPlayer.vue` 在网络或解码失败时自动回退一次。

语音源相关脚本：`node scripts/fetch-bwiki-voices.mjs` 抓取 bwiki 语音页（455 页，缓存在 `.bwiki-cache/pages/`，可断点续跑），`node scripts/apply-bwiki-voices.mjs` 按「条数 + 方言条目落在类别尾部」结构对齐改写分片，默认 dry-run，加 `--write` 落地；确实不能让某个槽位走 bwiki 时，写进该文件顶部的 `HOLDOUT`（整员 / 语言池 / 槽位三级），并注明证据。对应关系的复核工具是 `scripts/audit-column-tags.mjs`（每条链接对回 bwiki 的（日）（中）（方）（联）列）、`scripts/audit-correspondence.mjs`（同音频复用、台词字数与音频时长比）、`scripts/verify-audio-text.mjs` + `scripts/adjudicate-cn.mjs`（逐条转写对台本）与 `scripts/find-cross-assignments.mjs`（把听错的台词反查回真正的干员）。

`node server.js` 提供 `dist/` 和本地音频代理；代理只服务 `/audio/` 前缀（PRTS 源），bwiki 直链由前端直接请求。本地服务未做生产安全加固，不要向公网暴露。

维护脚本及回归测试位于 `scripts/` 与 `test/`。`npm run verify:data` 无需外网和兄弟仓库；如存在工作区台词总表，会检查其与分片的一致性。手动修改分片后可执行 `node scripts/sync-voice-texts.mjs` 刷新已有总表。可选网络抽查使用 `node scripts/verify-updates.mjs --online`。

完整交接文档见 [docs/HANDOVER.md](docs/HANDOVER.md)。合并后以本目录的交接文档为准，不再要求同步原独立工作区的副本。
