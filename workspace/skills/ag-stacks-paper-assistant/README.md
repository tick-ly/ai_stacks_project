# AG Stacks Paper Assistant 使用指导

本目录是“代数几何问答 + 引用”Skill 的实现。  
它会先判断问题是否与代数几何相关，再做 Stacks 检索与多源网页检索（arXiv/OpenAlex/Semantic Scholar/Crossref/MathOverflow/Math StackExchange/Wikipedia），最后输出带引用的结构化结果。

## 1. 目录结构

- `SKILL.md`：Skill 行为协议（给智能体用）
- `scripts/`：可执行脚本
- `references/`：回答风格与引用规范
- `evals/`：评测样例
- `tmp/`：运行时中间文件与示例输出

## 2. 运行前准备

在 `workspace` 根目录执行：

```powershell
pip install -r requirements.txt
```

需要确保向量索引与词法索引已生成（应有 `data/index/index_meta.json` 与 `data/index/lexical.db`）。

## 3. 最短可用流程（推荐）

在 `workspace` 根目录执行：

```powershell
python skills\ag-stacks-paper-assistant\scripts\ag_assistant_pipeline.py --query "What is a flat morphism of schemes?" --stacks-top-k 5 --papers-top-k 3 --output skills\ag-stacks-paper-assistant\tmp\pipeline_demo.json
```

输出 JSON 中重点字段：

- `relevance.label`：`high / medium / low`
- `route`：`ag_retrieval / stacks_only_degraded / papers_only_degraded / retrieval_unavailable / low_relevance_stop`
- `stacks.results`：Stacks 证据，含 tag 与 URL
- `papers.results`：多源网页证据
- `papers.source_breakdown`：每个来源的状态、错误码、计数、`degrade_reason`
- `citations.all_references`：可直接粘贴的引用列表
- `warnings`：结构化问题告警，含 `source`、`code`、`message`、`degrade_reason`
- `degradations`：当前路由失效点汇总（如 `NO_MATCHES`、`PAPERS_RETRIEVAL_ERROR`）
- `source_confidence`：证据置信度评分，范围 `0~1`
- `evidence_quality`：证据质量等级，`high / medium / low`

## 4. 分步调试命令

仅做相关性判定：

```powershell
python skills\ag-stacks-paper-assistant\scripts\classify_relevance.py --query "Explain moduli stack"
```

仅查 Stacks：

```powershell
python skills\ag-stacks-paper-assistant\scripts\retrieve_stacks.py --query "flat morphism of schemes definition" --top-k 8
```

仅查多源网页（默认含 arXiv）：

```powershell
python skills\ag-stacks-paper-assistant\scripts\retrieve_papers.py --query "flat morphism of schemes" --top-k 6
```

默认 arXiv 类别约束为：

- `math.AG, math.AC, math.RT, math.NT, math.KT, math.RA, math.AT`

若要覆盖默认类别，可显式传参：

```powershell
python skills\ag-stacks-paper-assistant\scripts\retrieve_papers.py --query "derived stacks" --categories "math.AG,math.AT"
```

若要限制来源：

```powershell
python skills\ag-stacks-paper-assistant\scripts\retrieve_papers.py --query "derived stacks" --sources "arxiv,openalex,semanticscholar" --per-source-k 10
```

也可显式启用社区问答源：

```powershell
python skills\ag-stacks-paper-assistant\scripts\retrieve_papers.py --query "derived category t-structure intuition" --sources "mathoverflow,mathse,arxiv" --per-source-k 8
```

论文检索器支持“新进展/综述/比较”意图自动提权（`recency_weight` 输出会反映为更高权重）：

```powershell
python skills\ag-stacks-paper-assistant\scripts\retrieve_papers.py --query "latest survey on derived stacks for moduli" --top-k 6
```

## 5. TLS 与网络排障

`retrieve_papers.py` 默认严格 TLS 校验，优先级如下：

1. `--ca-bundle`
2. 环境变量 `SSL_CERT_FILE`
3. 系统信任库（`truststore`）
4. `certifi`
5. Python 默认上下文

如证书链异常，优先用 `--ca-bundle` 或配置 `SSL_CERT_FILE`。  
仅在受限环境下才使用 `--allow-insecure-ssl-fallback`。

## 6. 结果判读与预期

- 若输入低相关，系统应停止 AG 深答并提示重述。
- 若 Papers 侧超时/限流/TLS 异常，主流程降级为“仅 Stacks”，并在输出中给 `warnings`（结构化 `source/code/message/degrade_reason`）。
- 若 Stacks 侧异常（索引缺失/脚本失败），主流程降级为“仅 Papers”，并在输出中给 `warnings`。
- 若双侧均失败，返回 `retrieval_unavailable`，并显式说明证据缺口；`evidence_quality` 通常为 `low`。
- `degrade_reason` 统一语义建议：
  - `tls_restricted`
  - `timeout`
  - `parse_error`
  - `no_matches`
  - `error`（兜底）

对 `source_confidence` 的建议阅读：

- `>= 0.75`：`high`，可支持较稳的基础说明
- `0.45 ~ 0.74`：`medium`，建议标注边界并降低推断强度
- `< 0.45`：`low`，需明显提示证据不足
- 基础性数学事实应优先由 Stacks 引用支撑。

## 7. 典型验收样例

```powershell
python skills\ag-stacks-paper-assistant\scripts\ag_assistant_pipeline.py --query "Explain flat morphism of schemes and cite sources" --stacks-top-k 3 --papers-top-k 2
```

验收要点：

- `relevance.label` 为 `high` 或 `medium`
- `stacks.count > 0`
- `citations.all_references` 非空
- Stacks 引用链接形如 `https://stacks.math.columbia.edu/tag/<TAG>`
