# 干员辨识训练

此仓库构建并发布到 [coconutsmilk.top](https://coconutsmilk.top/)。

- `/`：双游戏首页
- `/voice/`：[voice-guess-arknights](https://github.com/CoConuts-Milk0325/voice-guess-arknights) 语音猜干员
- `/clues/`：本仓库的四线索猜干员
- `/干员档案展示版/`：线索游戏引用的干员档案

四线索游戏的完整玩法和判题口径见[玩家规则](猜干员网页游戏/玩家规则.md)。
网站的“说明文档”页由该文件生成；修改规则后运行 `node 猜干员网页游戏/生成规则页.mjs`，站点构建时也会自动更新该页面。

语音项目通过 Git 子模块固定到一个提交；更新其内容时，先更新子模块指针并提交本仓库。克隆后运行 `git submodule update --init --recursive`。

## Cloudflare Pages

- 生产分支：`main`
- 构建命令：`node build.mjs`
- 构建输出目录：`dist`

构建脚本会安装语音项目依赖、构建 Vite 资源，并将两个游戏和档案汇集到 `dist/`。本地运行方式相同。部分生成脚本与核验记录已纳入仓库；原始资料仍保留在本地工作区，重新生成索引和档案需要这些资料。站点构建只发布生成后的游戏文件和档案页面。
