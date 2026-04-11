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
- `gemini/knowledge/AG_GEM_WEB_SEARCH_POLICY.md`
- `gemini/knowledge/AG_GEM_CITATION_POLICY.md`
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
