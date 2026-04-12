# Gemini 高压测试包

本目录用于手动压测当前 AG Gem 在高难数学任务上的表现，重点观察三类能力：

- `proof`：证明链条是否稳，是否会跳步、偷换假设、误用局部化或 Tor。
- `research`：文献讲解是否有逐篇分析、跨文献综合和阅读路径，而不是只列题目。
- `pathology/counterexample`：是否真的能识别边界、给出正确反例，并说明缺了什么条件。

这些测试是给 Gemini 在线运行用的。本仓库不包含 Gemini 运行时，所以这里提供的是：

- 可直接复制的压力题
- 每题的通过信号和失败信号
- 一套统一评分模板

## 推荐测试配置

若目标是尽量发挥数学能力上限，建议在 Gemini 的 Knowledge 中上传：

1. `AG_GEM_CORE_PROTOCOL.md`
2. `AG_GEM_WEB_SEARCH_POLICY.md`
3. `AG_GEM_CITATION_POLICY.md`
4. `AG_GEM_CONTINUATION_PROTOCOL.md`
5. `AG_GEM_RETRIEVAL_ORCHESTRATION.md`
6. `AG_GEM_RETRIEVAL_TEMPLATE.md`
7. `AG_GEM_VALIDATION_LAYER.md`

并确保：

- 开启 Web/Search
- 允许读取 URL（若 Gemini 界面可配置）
- 每道题尽量在新会话中单独测试

## 运行协议

1. 为每道题新开一个 Gemini 对话。
2. 原样粘贴题目，不要预先补提示。
3. 记录第一轮回答。
4. 若该题附带了续写检查，再发送一次 `继续，把上一题没展开完的关键部分补完。`
5. 用 [SCORECARD_TEMPLATE.md](/D:/program/ai_stacks_project/gemini/tests/SCORECARD_TEMPLATE.md) 记录结果。

## 红线失败

出现以下任一情况，应直接判该题失败：

- 编造 Stacks tag、定理编号、论文元数据或链接
- 把推断写成已核验事实
- 输出 `CONTINUE_STATE`、`slots_done`、`slots_next`、`refs_kept`、`locked_terms`
- `research` 题只给标题列表，没有逐篇解释
- `pathology` 题没有给出明确对象，只泛泛说“缺条件会失败”

## 建议通过线

- 单题：总评至少为 `Pass`
- 单组：3 题中至少 2 题通过，且没有红线失败
- 整包：3 组里至少 2 组稳定通过，第三组不应出现系统性短板

## 文件结构

- [PROOF_STRESS_TESTS.md](/D:/program/ai_stacks_project/gemini/tests/PROOF_STRESS_TESTS.md)
- [RESEARCH_STRESS_TESTS.md](/D:/program/ai_stacks_project/gemini/tests/RESEARCH_STRESS_TESTS.md)
- [PATHOLOGY_COUNTEREXAMPLE_STRESS_TESTS.md](/D:/program/ai_stacks_project/gemini/tests/PATHOLOGY_COUNTEREXAMPLE_STRESS_TESTS.md)
- [SCORECARD_TEMPLATE.md](/D:/program/ai_stacks_project/gemini/tests/SCORECARD_TEMPLATE.md)
