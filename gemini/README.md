# Gemini Gem 使用指导

本目录用于把当前 AG Skill 迁移成 Gemini 的 Gem 配置。  
目标是尽可能复现 Skill 的效果：先判相关性，再检索 Stacks + 多源网页证据，再输出带引用回答。

当前文档已对齐本地改进版（v4）：

- 相关性门控：`low` 时停止深答并给重述建议
- 多源检索：`arXiv/OpenAlex/Semantic Scholar/Crossref/MathOverflow/Math StackExchange/Wikipedia`
- 论文检索失败自动降级：继续 Stacks-only，不中断
- Stacks 检索失败自动降级：继续 Web-only，并显式降低结论置信
- 引用绑定：无证据不引用，不编造 `[P*]`
- 分阶段续写：内部保留续写状态，但不向用户暴露控制块
- 高相关讲解加长：`study/high` 默认按“迷你讲义”输出，而不是极短摘要
- 文献讲解增强：`research` 默认做逐篇解析 + 跨文献综合 + 阅读路径

## 1. 文件说明

- `GEM_填写模板.md`：可直接复制到 Gemini「名称 / 说明 / 指令」
- `knowledge/AG_GEM_CORE_PROTOCOL.md`：核心流程协议
- `knowledge/AG_GEM_CONTINUATION_PROTOCOL.md`：隐藏式续写协议
- `knowledge/AG_GEM_CITATION_POLICY.md`：引用规则
- `knowledge/AG_GEM_RETRIEVAL_TEMPLATE.md`：`定 / 判 / 例 / 反 / 联 / 用` 检索骨架
- `knowledge/AG_GEM_RETRIEVAL_ORCHESTRATION.md`：query rewrite、证据打分与冲突裁决
- `knowledge/AG_GEM_VALIDATION_LAYER.md`：证明自检、反例扫描、来源一致性检查
- `knowledge/AG_GEM_WEB_SEARCH_POLICY.md`：联网检索策略
- `knowledge/AG_GEM_EVAL_CHECKLIST.md`：上线前验收清单

## 2. 在 Gemini 中创建 Gem

1. 打开 Gemini 的「新 Gem」页面。
2. 复制 `GEM_填写模板.md` 中对应内容到：
- 名称
- 说明
- 指令
3. 默认工具建议：
- 打开联网检索（Web/Search）
- 打开 URL 读取（如果有该选项）
4. 在「知识」区域优先上传最小有效集，必要时再加增强文件。

可选上传：

- `workspace/ag提示词.md`
- `workspace/skills/ag-stacks-paper-assistant/SKILL.md`

最小有效上传集：

1. `AG_GEM_CORE_PROTOCOL.md`
2. `AG_GEM_WEB_SEARCH_POLICY.md`
3. `AG_GEM_CITATION_POLICY.md`
4. `AG_GEM_CONTINUATION_PROTOCOL.md`

增强上传（希望检索更稳时再加）：

5. `AG_GEM_RETRIEVAL_ORCHESTRATION.md`
6. `AG_GEM_RETRIEVAL_TEMPLATE.md`

如果目标是尽量发挥数学能力上限，再加：

7. `AG_GEM_VALIDATION_LAYER.md`

不建议默认上传：

8. `AG_GEM_EVAL_CHECKLIST.md`
9. `README.md` 本身

## 3. 默认 arXiv 检索约束（建议保留）

Gem 指令中建议保留默认类别约束：

- `math.AG OR math.AC OR math.RT OR math.NT OR math.KT OR math.RA OR math.AT`

除非你明确要做其他数学分支，否则不建议删除。

## 4. 快速验收（上线前 5 分钟）

建议用这 5 类问题做冒烟测试：

1. 低相关：
- `今天上海天气怎么样？`
- 预期：提示低相关，不硬答 AG。

2. 基础 AG：
- `什么是 flat morphism of schemes？`
- 预期：给定义/性质，并含 Stacks 引用。

3. 高相关讲解长度：
- `详细讲解 flat morphism 的定义、判据、例子和反例。`
- 预期：不是极短摘要，而是一段可独立阅读的“迷你讲义”。

4. 研究导向：
- `平坦态射近年的研究方向有哪些？`
- 预期：有论文/网页引用，且能区分基础事实与研究趋势。

5. 社区讨论导向：
- `What are common intuitions for derived functors?`
- 预期：可出现 MathOverflow / Math StackExchange 引用，但不会把讨论帖当成定理证明。

## 5. 常见问题

如果回答没有引用：

- 检查指令中是否还保留“关键结论必须引用”的约束。
- 检查知识文件是否上传完整。

如果回答跑偏：

- 在指令开头强化“先相关性判定，再回答”的顺序。
- 增加“不相关时停止 AG 深答”的硬约束。

如果出现 `CONTINUE_STATE`、`slots_done` 这类奇怪片段：

- 说明 Gem 把内部续写状态直接打印出来了。
- 检查是否上传了旧版 continuation 文档，或主指令里仍保留原始控制块示例。
- 保留“分阶段续写”，但必须改成自然语言 `Next Step`。

如果回答过短：

- 检查主指令里是否明确要求 `study/high` 默认输出“迷你讲义”。
- 检查 `AG_GEM_RETRIEVAL_TEMPLATE.md` 是否已上传。
- 明确禁止“Relevance + Slot Focus + 两小段”这种过度压缩的输出。

如果检索质量不稳（搜偏、搜浅、冲突来源处理差）：

- 优先补传 `AG_GEM_RETRIEVAL_ORCHESTRATION.md`。
- 它比 `AG_GEM_EVAL_CHECKLIST.md` 更值得占用 Knowledge 上下文。

如果证明题或高难讲解还是容易跳步、漏条件、误引来源：

- 补传 `AG_GEM_VALIDATION_LAYER.md`。
- 这个文件的作用不是让回答更长，而是让关键结论更稳。

如果文献讲解质量差（只给标题、没有方法与贡献分析）：

- 检查主指令中是否保留了 `Literature Breakdown` / `Synthesis` / `Reading Path` 三段。
- 检查 `AG_GEM_CORE_PROTOCOL.md` 里的 research depth floor 是否被覆盖。
- 在用户问题里加上“请逐篇比较问题-方法-贡献-局限”，可稳定触发深讲模式。

如果联网检索偶发失败：

- 保持“Stacks 优先”回答链路，不要中断。
- 在答案中增加简短 `Warning`，说明 Papers/Web 暂不可用。
- 不要输出未核验的论文引用。

## 6. 高压测试

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
