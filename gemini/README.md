# Gemini Gem 使用指导

本目录用于把当前 AG Skill 迁移成 Gemini 的 Gem 配置。  
目标是尽可能复现 Skill 的效果：先判相关性，再检索 Stacks + 多源网页证据，再输出带引用回答。

当前文档已对齐 Agent 改进版（v5）：

- 相关性门控：`low` 时停止深答并给重述建议
- 多源检索：`arXiv/OpenAlex/Semantic Scholar/Crossref/MathOverflow/Math StackExchange/Wikipedia`
- 论文检索失败自动降级：继续 Stacks-only，不中断
- Stacks 检索失败自动降级：继续 Web-only，并显式降低结论置信
- 引用绑定：无证据不引用，不编造 `[P*]`
- 长主题按“定判例反联用”分槽位续写，而不是单轮写满

## 1. 文件说明

- `GEM_填写模板.md`：可直接复制到 Gemini「名称 / 说明 / 指令」
- `knowledge/AG_GEM_CORE_PROTOCOL.md`：核心流程协议
- `knowledge/AG_GEM_CONTINUATION_PROTOCOL.md`：续写协议
- `knowledge/AG_GEM_RETRIEVAL_TEMPLATE.md`：定判例反联用检索模板
- `knowledge/AG_GEM_CITATION_POLICY.md`：引用规则
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
4. 在「知识」区域上传 `knowledge/` 下的核心 `.md` 文件。

可选上传：

- `workspace/ag提示词.md`
- `workspace/skills/ag-stacks-paper-assistant/SKILL.md`

推荐上传顺序：

1. `AG_GEM_CORE_PROTOCOL.md`
2. `AG_GEM_CONTINUATION_PROTOCOL.md`
3. `AG_GEM_RETRIEVAL_TEMPLATE.md`
4. `AG_GEM_CITATION_POLICY.md`
5. `AG_GEM_WEB_SEARCH_POLICY.md`
6. `AG_GEM_EVAL_CHECKLIST.md`

## 3. 默认 arXiv 检索约束（建议保留）

Gem 指令中建议保留默认类别约束：

- `math.AG OR math.AC OR math.RT OR math.NT OR math.KT OR math.RA OR math.AT`

除非你明确要做其他数学分支，否则不建议删除。

## 4. 快速验收（上线前 5 分钟）

建议用这 4 类问题做冒烟测试：

1. 低相关：
- `今天上海天气怎么样？`
- 预期：提示低相关，不硬答 AG。

2. 基础 AG：
- `什么是 flat morphism of schemes？`
- 预期：给定义/性质，并含 Stacks 引用。

3. 研究导向：
- `平坦态射近年的研究方向有哪些？`
- 预期：有论文/网页引用，且能区分基础事实与研究趋势。

4. 社区讨论导向：
- `What are common intuitions for derived functors?`
- 预期：可出现 MathOverflow / Math StackExchange 引用，但不会把讨论帖当成定理证明。

5. 长主题续写：
- `系统讲解 flat morphism，先讲定义和例子`
- 下一轮：`继续，补判据和反例`
- 预期：Gem 会按槽位续写，而不是从头重写。

## 5. 常见问题

如果回答没有引用：

- 检查指令中是否还保留“关键结论必须引用”的约束。
- 检查知识文件是否上传完整。

如果回答跑偏：

- 在指令开头强化“先相关性判定，再回答”的顺序。
- 增加“不相关时停止 AG 深答”的硬约束。

如果外部来源质量偏弱：

- 在指令中强调“优先近期 + 至少 1 个基础来源 + 多源交叉”。
- 明确要求给出标题、作者、年份、链接与相关性一句话。

如果联网检索偶发失败：

- 保持“Stacks 优先”回答链路，不要中断。
- 在答案中增加简短 `Warning`，说明 Papers/Web 暂不可用。
- 不要输出未核验的论文引用。
