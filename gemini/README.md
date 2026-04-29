# Gemini Gem 使用指导（AG 专用）

本目录用于把当前 AG Skill 迁移成 Gemini 的 Gem 配置。  
目标是尽可能复现 Skill 的效果：先判相关性，再检索 Stacks + 多源网页证据，再输出带引用回答。

这一套更适合：

- 代数几何问答
- Stacks 定锚 + 多源网页补充
- 判据、定义、定理、反例、用途讲解
- 文献比较、研究方向、阅读路径

如果你的目标是“数学书 / 讲义 / 教材连续扩写”，而不是 AG 检索问答，请优先使用通用学习目录里的数学书扩写版；当前目录更适合代数几何专用场景。

## 1. 先选入口

当前目录建议分成两种使用方式：

1. 最快落地
- 直接使用 `GEM_最终指令成稿_AG专用版.md`
- 适合你已经决定做 AG 专用 Gem，只想把一份稳定成稿直接粘贴进 Gemini 指令框

2. 需要继续自定义
- 使用 `GEM_填写模板.md`
- 适合你还想继续改名称、说明或把部分规则裁短

一句话建议：

- 要最快可用，就用“最终成稿”
- 要继续编辑，就用“填写模板”

## 2. 最快起步（推荐）

如果你只是想尽快在 Gemini 里得到一个可用版本：

1. 打开 Gemini 的「新 Gem」页面。
2. 名称先填：`代数几何助手（Stacks 优先 + 多源网页）`
3. 说明先填：`面向代数几何问答，优先用 The Stacks Project 定锚，再补多源网页证据，并保持引用与降级纪律。`
4. 将 `GEM_最终指令成稿_AG专用版.md` 里的正文复制到「指令」框。
5. 开启联网检索（Web/Search）；若有 URL 读取，也建议开启。
6. 再按下文上传最小有效知识集。

## 3. 文件说明

- `GEM_最终指令成稿_AG专用版.md`：当前推荐入口，可直接复制到 Gemini 指令框
- `GEM_填写模板.md`：需要拆开填写“名称 / 说明 / 指令”时使用
- `knowledge/AG_GEM_CORE_PROTOCOL.md`：核心流程、mode、batch、continuation 与输出结构
- `knowledge/AG_GEM_RETRIEVAL_POLICY.md`：检索、source routing、query rewrite、冲突裁决与降级规则
- `knowledge/AG_GEM_QUALITY_GUARDRAILS.md`：引用绑定、校验层、不确定性与质量红线
- `knowledge/AG_GEM_EVAL_CHECKLIST.md`：上线前验收清单

## 4. 在 Gemini 中创建 Gem（模板方式）

如果你不想直接用“最终成稿”，而想边填边改：

1. 打开 Gemini 的「新 Gem」页面。
2. 复制 `GEM_填写模板.md` 中对应内容到：
- 名称
- 说明
- 指令
3. 默认工具建议：
- 打开联网检索（Web/Search）
- 打开 URL 读取（如果有该选项）
4. 在「知识」区域优先上传最小有效集，必要时再加增强文件。

## 5. Knowledge 上传建议

如果你已经使用了“最终成稿”，Knowledge 建议按下面的轻重顺序添加：

- 最小有效集：保证基础行为已经稳
- 验收清单：用于上线前测试，不必默认塞进上下文

最小有效上传集：

1. `AG_GEM_CORE_PROTOCOL.md`
2. `AG_GEM_RETRIEVAL_POLICY.md`
3. `AG_GEM_QUALITY_GUARDRAILS.md`

可选上传：

- `workspace/ag提示词.md`
- `workspace/skills/ag-stacks-paper-assistant/SKILL.md`

不建议默认上传：

4. `AG_GEM_EVAL_CHECKLIST.md`
5. `README.md` 本身

## 6. 默认 arXiv 检索约束（建议保留）

Gem 指令中建议保留默认类别约束：

- `math.AG OR math.AC OR math.RT OR math.NT OR math.KT OR math.RA OR math.AT`

除非你明确要做其他数学分支，否则不建议删除。

## 7. 快速验收（上线前 5 分钟）

建议用这 5 类问题做冒烟测试：

1. 低相关
- `今天上海天气怎么样？`
- 预期：提示低相关，不硬答 AG。

2. 基础 AG
- `什么是 flat morphism of schemes？`
- 预期：给定义/性质，并含 Stacks 引用。

3. 高相关讲解长度
- `详细讲解 flat morphism 的定义、判据、例子和反例。`
- 预期：不是极短摘要，而是一段可独立阅读的“迷你讲义”。

4. 研究导向
- `平坦态射近年的研究方向有哪些？`
- 预期：有论文/网页引用，且能区分基础事实与研究趋势。

5. 社区讨论导向
- `What are common intuitions for derived functors?`
- 预期：可出现 MathOverflow / Math StackExchange 引用，但不会把讨论帖当成定理证明。

## 8. 常见问题

如果回答没有引用：

- 检查主指令中是否还保留“关键结论必须引用”的约束。
- 检查 `AG_GEM_QUALITY_GUARDRAILS.md` 是否已上传。

如果回答跑偏：

- 在主指令开头强化“先相关性判定，再回答”的顺序。
- 增加“不相关时停止 AG 深答”的硬约束。

如果出现 `CONTINUE_STATE`、`slots_done` 这类奇怪片段：

- 说明 Gem 把内部续写状态直接打印出来了。
- 检查主指令中是否还残留旧控制块示例。
- 保留“分阶段续写”，但必须改成自然语言 `Next Step`。

如果网页端长任务容易变成“每轮只推进一点点”：

- 检查主指令里是否明确写了“内部微切片，对外闭合批次”。
- 检查 `AG_GEM_CORE_PROTOCOL.md` 是否已上传。
- 要求它每轮至少完成一个 `定义/判据/例子/反例` 簇，或一个 `定理/证明/用途` 簇。

如果回答过短：

- 检查主指令里是否明确要求 `study/high` 默认输出“迷你讲义”。
- 检查 `AG_GEM_CORE_PROTOCOL.md` 是否已上传。
- 明确禁止“Relevance + 两小段 + References”这种过度压缩的输出。

如果检索质量不稳（搜偏、搜浅、冲突来源处理差）：

- 优先补传 `AG_GEM_RETRIEVAL_POLICY.md`。
- 它已经把 query rewrite、source routing、冲突裁决和降级规则收在一起了。

如果证明题或高难讲解还是容易跳步、漏条件、误引来源：

- 补传 `AG_GEM_QUALITY_GUARDRAILS.md`。
- 这个文件的作用不是让回答更长，而是让关键结论更稳。

如果文献讲解质量差（只给标题、没有方法与贡献分析）：

- 检查主指令中是否保留了 `Literature Breakdown` / `Synthesis` / `Reading Path` 三段。
- 检查 `AG_GEM_CORE_PROTOCOL.md` 里的 research depth floor 是否被覆盖。
- 在用户问题里加上“请逐篇比较问题-方法-贡献-局限”，可稳定触发深讲模式。

如果联网检索偶发失败：

- 保持“Stacks 优先”回答链路，不要中断。
- 在答案中增加简短 `Warning`，说明 Papers/Web 暂不可用。
- 不要输出未核验的论文引用。

## 9. 高压测试

如果你要检查这套 Gem 是否真的把数学能力逼到更高上限，而不是只做“看起来更像样”的回答，可以直接使用：

- [gemini/tests/README.md](/D:/program/ai_stacks_project/gemini/tests/README.md)
- [gemini/tests/PROOF_STRESS_TESTS.md](/D:/program/ai_stacks_project/gemini/tests/PROOF_STRESS_TESTS.md)
- [gemini/tests/RESEARCH_STRESS_TESTS.md](/D:/program/ai_stacks_project/gemini/tests/RESEARCH_STRESS_TESTS.md)
- [gemini/tests/PATHOLOGY_COUNTEREXAMPLE_STRESS_TESTS.md](/D:/program/ai_stacks_project/gemini/tests/PATHOLOGY_COUNTEREXAMPLE_STRESS_TESTS.md)
- [gemini/tests/SCORECARD_TEMPLATE.md](/D:/program/ai_stacks_project/gemini/tests/SCORECARD_TEMPLATE.md)

建议优先跑 `proof / research / pathology-counterexample` 三组，而不是只做简单冒烟测试。  
这三组更容易暴露：

- 关键证明步骤跳步
- 文献只列标题不做综合
- 只会说“缺条件”但给不出明确反例
- 高压续写时再次泄漏控制字段
