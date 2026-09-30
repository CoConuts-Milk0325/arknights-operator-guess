# 挑战模式干员不重复 设计文档

日期：2026-08-11
状态：已批准

## 背景

当前挑战模式每道题随机选择干员，仅通过 `lastOperatorName` 避免"连续重复"（`gameEngine.js` 的 `selectRandomOperator`）。用户希望在挑战模式内**全程不重复**干员，参考 `D:\代码\猜干员\arknights-wordle-202606` 的 `challengeService.js` 实现。

## 需求

1. 挑战模式内，已出现过的干员不再出现（全程不重复）。
2. 当筛选后可用干员数 < 题目数时，**禁止开始挑战**并在设置界面提示。
3. 普通模式（非挑战）保持现状，不做更改。
4. `?target=` 调试干员走独立分支，不受去重影响。

## 方案

采用 Set 去重（方案 A），改动最小，贴合参考项目。

### 数据模型

`challenge.js` 的 `createChallenge` 返回值新增字段：

```js
usedOperators: []  // 本场挑战已出现过的干员名
```

### 选择逻辑

`gameEngine.js` 的 `selectRandomOperator` 增加可选参数：

```js
export function selectRandomOperator(operators, lastName = null, exclude = [])
```

- `exclude` 为空数组时行为不变。
- 非空时，先从 `operators` 中过滤掉 `exclude` 中同名干员，再按原逻辑随机选择。
- 若过滤后为空（极端情况），回退到原列表随机，避免返回 null 导致死循环。

### 挑战状态流转

`GameBoard.vue` 改动四处：

1. `startChallenge`：开始前检查 `getFilteredOperators().length >= settings.questionCount`，不足则显示错误提示（`setupError` ref），不开始挑战。
2. `startNewQuestion`：挑战模式下调用 `selectRandomOperator(filteredOperators, lastOperatorName, challenge.value.usedOperators)`。
3. `applyQuestion`：题目确定后（`prepareQuestion` 成功）将 `question.operator.name` push 进 `challenge.value.usedOperators`。无语音数据被跳过的干员不会计入。
4. `preloadNextQuestion`：预加载选干员时同样传入 `challenge.value.usedOperators` 排除已用干员。

### 边界处理

- `targetOperator`（URL `?target=`）分支不传 exclude，保持原逻辑。
- 预加载（`preloadNextQuestion`）必须同步感知 `usedOperators`，否则预生成的下一题可能与之前重复。
- 普通模式 `inChallenge=false` 时不传 exclude，行为不变。

## 测试

- 挑战模式 N 题，确认 N 个干员各不相同。
- 筛选后干员数 < 题目数时，设置界面出现提示且无法开始。
- 普通模式连续出题无异常。
- 预加载与去重无冲突（连续快速答题不出现重复干员）。
