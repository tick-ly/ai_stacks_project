# AG 检索增强与 Gemini 配置升级报告

日期：2026-04-10

## 1. 本次完成内容（按你要求落地）

### 1.1 Skill 侧代码升级

已将 `ag-stacks-paper-assistant` 从 arXiv-only 升级为“多源网页检索 + 去重融合 + 分层降级”：

- 检索源扩展到：
  - `arXiv`
  - `OpenAlex`
  - `Semantic Scholar`
  - `Crossref`
  - `MathOverflow`（`mathoverflow.net`）
  - `Math StackExchange`（`math.stackexchange.com`）
  - `Wikipedia`（术语兜底）
- 支持 DOI / arXiv ID / 标题归一化去重
- 支持融合排序（来源权重 + 相关词覆盖 + 时效 + 多源重合加分）
- 输出每个来源的 `source_breakdown`（`status/count/error/ssl_mode`）
- 保留并强化 TLS 策略（`ca-bundle` / `SSL_CERT_FILE` / truststore / certifi / 可选不安全回退）

此外已把主 pipeline 改成双侧降级：

- `route=ag_retrieval`：Stacks + Papers/Web 均可用
- `route=stacks_only_degraded`：Papers/Web 失败，继续 Stacks
- `route=papers_only_degraded`：Stacks 失败，继续 Papers/Web
- `route=retrieval_unavailable`：双侧都失败，返回证据缺口

### 1.1.1 数据集适配检查

Skill 仍与现有数据集路径一致（已实测可检索）：

- 向量索引：`workspace/data/index/embeddings.npy` + `ids.json` + `index_meta.json`
- 语料：`workspace/data/processed/corpus.jsonl`
- 词法索引：`workspace/data/index/lexical.db`
- `retrieve_stacks.py` 默认读取上述路径，无需额外迁移

### 1.2 Gemini Gem 配置升级

`gemini/` 下文档已对齐 v3 协议：

- 指令层面加入多源网页策略（含 MathOverflow / Math StackExchange）
- 明确“讨论帖可用于直觉/线索，但不能单独证明定理真值”
- 明确双侧降级策略（Papers 失败与 Stacks 失败分别怎么退化）
- 引用策略升级为 `Stacks` + `Papers/Web` 双分组

### 1.3 文档补齐

已更新 Skill 与 Gemini 的使用文档，保证“可直接运行 + 可直接配置 Gem”。

---

## 2. 关键改动文件

### Skill 代码

- `workspace/skills/ag-stacks-paper-assistant/scripts/retrieve_papers.py`
- `workspace/skills/ag-stacks-paper-assistant/scripts/ag_assistant_pipeline.py`

### Skill 文档

- `workspace/skills/ag-stacks-paper-assistant/README.md`
- `workspace/skills/ag-stacks-paper-assistant/SKILL.md`
- `workspace/skills/ag-stacks-paper-assistant/references/web_search_policy.md`

### Gemini 文档

- `gemini/GEM_填写模板.md`
- `gemini/README.md`
- `gemini/knowledge/AG_GEM_CORE_PROTOCOL.md`
- `gemini/knowledge/AG_GEM_RETRIEVAL_POLICY.md`
- `gemini/knowledge/AG_GEM_EVAL_CHECKLIST.md`

---

## 3. 使用说明（可直接跑）

## 3.1 多源网页检索（含 MO/MSE）

```powershell
python workspace\skills\ag-stacks-paper-assistant\scripts\retrieve_papers.py --query "what is a sheaf" --sources "mathoverflow,mathse,arxiv,openalex" --top-k 8 --per-source-k 8
```

可选参数：

- `--sources`：来源集合
- `--per-source-k`：每个来源的原始召回条数
- `--ag-query-hint / --no-ag-query-hint`：是否自动补 `algebraic geometry` 检索提示
- `--allow-insecure-ssl-fallback`：仅受限网络下启用

## 3.2 整体 AG pipeline（支持降级路由）

```powershell
python workspace\skills\ag-stacks-paper-assistant\scripts\ag_assistant_pipeline.py --query "What is a sheaf" --stacks-top-k 5 --papers-top-k 6 --papers-sources "mathoverflow,mathse,arxiv,openalex,semanticscholar,crossref" --papers-per-source-k 8 --output workspace\skills\ag-stacks-paper-assistant\tmp\pipeline_demo_v3.json
```

重点看输出字段：

- `route`
- `warnings`
- `papers.source_breakdown`
- `citations.all_references`

## 3.3 检索改进一键实验（你之前要求的 5/6）

```powershell
python workspace\scripts\run_retrieval_improvement.py --config workspace\config\pipeline.yaml
```

输出：

- `workspace/data/eval/improvement_runs/summary.json`
- `workspace/data/eval/improvement_runs/summary.md`

---

## 4. 已完成验证

本地已执行并通过：

1. `retrieve_papers.py` 语法编译
2. `ag_assistant_pipeline.py` 语法编译
3. 多源检索实测（含 `mathoverflow` / `mathse`）
4. pipeline 实测，确认出现：
   - `route=ag_retrieval`
   - `route=stacks_only_degraded`（通过故意传入无效 source 触发）
   - 输出包含有效 `source_breakdown` 与引用列表

---

## 5. Gemini 实际落地步骤（最短路径）

1. 打开 Gemini 新 Gem 页面。
2. 复制 `gemini/GEM_填写模板.md` 的 名称/说明/指令。
3. 上传 `gemini/knowledge/` 下 4 个知识文件。
4. 做 4 组冒烟：低相关、基础 AG、研究导向、讨论导向（MO/MSE）。
5. 检查是否满足：
   - 先相关性门控
   - 关键结论有引用
   - 检索失败时能降级而不中断

---

## 6. 说明

- 工作区中还有你之前已存在的其它改动（如 `workspace/scripts/retrieval_engine.py` 等）未被回滚，本次在其基础上继续增强 Skill 与 Gemini 对齐能力。
- 本报告仅记录本轮与你目标直接相关的新增/调整。

## 7. 2026-04-29 三项优化执行记录（按“最新/综述/比较提权 + 错误码统一 + 口径审计”）

### 7.1 检索提示策略提权（papers 侧）

- 已在 `retrieve_papers.py` 增加 freshness intent 检测：命中 `latest / recent / survey / comparison / 综述 / 最新 / 进展` 等词后，`_score_item` 使用更高时效权重。
- 对应配置：
  - 非该类意图：`recency_weight=0.25`
  - 时效意图：`recency_weight=0.40`
- 输出字段新增：
  - `freshness_intent`
  - `recency_weight`
- 运行验证：
  - `python workspace\skills\ag-stacks-paper-assistant\scripts\retrieve_papers.py --query "latest survey on derived stacks for moduli" --top-k 6`
  - 结果确认 `freshness_intent=true` 且 `recency_weight` 变更生效。

### 7.2 错误链路语义码统一

- 已统一 `classify_relevance.py` / `retrieve_stacks.py` / `retrieve_papers.py` / `format_citations.py` 的失败返回为：
  - `{"error": {"code": "...", "message": "...", "details": "..."}}`
- `ag_assistant_pipeline.py` 的 `_run_json` 可：
  - 解析子进程返回的标准错误负载；
  - 统一降级为标准码（如 `PIPELINE_SUBPROCESS_ERROR`）；
  - 将 warnings 改为结构化对象 `{source, code, message}`。
- 验证示例：
  - `python workspace\skills\ag-stacks-paper-assistant\scripts\retrieve_papers.py --query "x" --sources unknown`
  - `python workspace\skills\ag-stacks-paper-assistant\scripts\ag_assistant_pipeline.py --query "flat morphism" --papers-sources "unknown"`
  - 均能输出 `PAPERS_RETRIEVAL_ERROR`，并在 pipeline `warnings` 中保留 `code`。

### 7.3 Gem 知识条目与脚本默认值口径审计

- 先后完成了：
  - 源顺序审计：`arXiv -> OpenAlex -> Semantic Scholar -> Crossref -> MathOverflow -> Math StackExchange -> Wikipedia`；
  - 降级动作一致性：Stacks 优先；任一侧失败时回退到可用侧；双侧失败标记 `retrieval_unavailable`；
  - 可选参数默认值核对：默认 `math.AG/math.AC/...` 类别约束、`arXiv` 默认检索行为、TLS 修复顺序与 fallback 标注。
- 对齐产物：
  - `gemini/knowledge/AG_GEM_RETRIEVAL_POLICY.md`（新增）
  - `gemini/knowledge/AG_GEM_EVAL_CHECKLIST.md`（新增 `J2/K2` 验收项）
  - `workspace/skills/ag-stacks-paper-assistant/README.md` 与 `SKILL.md`（补齐时效意图、结构化 warning）
- 一致性结论：在已核对项中，Skill 的脚本默认行为与 Gem 规则基本一致，未发现阻塞性偏差。

## 8. 2026-04-29 继续：并发安全与可观测性增强

本轮聚焦“可重复执行、可观测、可审计”的主流程行为，补齐你要求的三项优化点。

### 8.1 并发安全与幂等性

- `ag_assistant_pipeline.py` 已将临时文件从固定名改为 `NamedTemporaryFile`，并使用每次运行的随机路径（`tmp/stacks_*.json`、`tmp/papers_*.json`）；
- `tempfile` 文件在运行结束统一清理，避免多实例并发互相覆盖；
- 未引用的临时文件不会影响返回结构。

### 8.2 统一降级码（`degrade_reason`）

- 新增统一语义码：
  - `tls_restricted`
  - `timeout`
  - `parse_error`
  - `no_matches`
  - `error`
- `retrieve_papers.py` 在每个来源和总错误上都返回 `degrade_reason`；
- `ag_assistant_pipeline.py` 通过 `_build_degradation` / `_normalize_warning` 统一消费这些语义码；
- 主返回中新增/保留 `warnings`（含 `source/code/message/degrade_reason`）与 `degradations`（结构化降级清单）。

### 8.3 结果可解释性（证据质量字段）

- pipeline 顶层新增字段：
  - `source_confidence`（`0~1`）
  - `evidence_quality`（`high / medium / low`）
- 依据候选数、来源覆盖、SSL 回退与告警类型评分；
- 建议 Gemini 层据此调整不确定性措辞。

### 8.4 Gemini 与文档对齐

已同步更新：

- `workspace/skills/ag-stacks-paper-assistant/README.md`
- `workspace/skills/ag-stacks-paper-assistant/SKILL.md`
- `workspace/skills/ag-stacks-paper-assistant/references/web_search_policy.md`
- `gemini/knowledge/AG_GEM_CORE_PROTOCOL.md`
- `gemini/knowledge/AG_GEM_RETRIEVAL_POLICY.md`
- `gemini/knowledge/AG_GEM_QUALITY_GUARDRAILS.md`
- `gemini/knowledge/AG_GEM_EVAL_CHECKLIST.md`
- `gemini/GEM_最终指令成稿_AG专用版.md`

### 8.5 一键验证样例

- `python workspace\\skills\\ag-stacks-paper-assistant\\scripts\\ag_assistant_pipeline.py --query \"What is a flat morphism of schemes?\" --stacks-top-k 3 --papers-top-k 2`
- `python workspace\\skills\\ag-stacks-paper-assistant\\scripts\\ag_assistant_pipeline.py --query \"flat morphism\" --papers-sources unknown`
- `python workspace\\skills\\ag-stacks-paper-assistant\\scripts\\retrieve_papers.py --query \"asdasdzzzznonexistentterm12345\" --top-k 3 --sources \"arxiv,mathoverflow\"`

这三类命令已用于验证：

- 结构化降级码（`degrade_reason`）是否持续；
- 无匹配与部分来源错误是否正确回传；
- `source_confidence / evidence_quality` 的输出是否稳定。

### 8.6 继续补齐：子脚本输出标准化与警告源语义化（本次）

- 已将 `classify_relevance.py` / `retrieve_stacks.py` / `format_citations.py` 的异常返回补齐为可消费字段：
  - `source`（`relevance` / `stacks` / `citations`）
  - `degrade_reason`（优先 `error` / `parse_error`）
- `retrieve_stacks.py` 增加 `count==0` 时的 `warnings`，与主流程 `NO_MATCHES` 路径对齐。
- `format_citations.py` 增加无引用时的 `NO_MATCHES` warning，便于 `citations` 侧降级可观测。
- `ag_assistant_pipeline.py` 的 `_normalize_warning` 改为：
  - 当子脚本返回 `source: *.py`（历史兼容）时，自动替换为 `stacks/papers/citations/relevance` 这类业务源；
  - 保留子脚本显式语义 `source` 以兼容高优先级场景。
- 这一步的目标是让 Gem 的规则引擎只依赖业务字段（`source` 与 `degrade_reason`）而非脚本名。
