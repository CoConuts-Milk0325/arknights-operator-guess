# 干员辨识训练

此仓库构建并发布到 [coconutsmilk.top](https://coconutsmilk.top/)。

- `/`：双游戏首页
- `/voice/`：[voice-guess-arknights](https://github.com/CoConuts-Milk0325/voice-guess-arknights) 语音猜干员
- `/clues/`：本仓库的四线索猜干员
- `/干员档案展示版/`：线索游戏引用的干员档案

语音项目通过 Git 子模块固定到一个提交；更新其内容时，先更新子模块指针并提交本仓库。克隆后运行 `git submodule update --init --recursive`。

## Cloudflare Pages

- 生产分支：`main`
- 构建命令：`node build.mjs`
- 构建输出目录：`dist`

构建脚本会安装语音项目依赖、构建 Vite 资源，并将两个游戏和档案汇集到 `dist/`。本地运行方式相同。原始资料及生成脚本保留在本地工作区，不上传到网站仓库。
