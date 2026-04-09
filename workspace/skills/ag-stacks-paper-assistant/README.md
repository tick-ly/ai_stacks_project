# AG Stacks Paper Assistant 使用指导

本目录是“代数几何问答 + 引用”Skill 的实现。  
它会先判断问题是否与代数几何相关，再做 Stacks 检索与 arXiv 检索，最后输出带引用的结构化结果。

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
- `route`：`ag_retrieval` 或 `low_relevance_stop`
- `stacks.results`：Stacks 证据，含 tag 与 URL
- `papers.results`：arXiv 证据
- `citations.all_references`：可直接粘贴的引用列表

## 4. 分步调试命令

仅做相关性判定：

```powershell
python skills\ag-stacks-paper-assistant\scripts\classify_relevance.py --query "Explain moduli stack"
```

仅查 Stacks：

```powershell
python skills\ag-stacks-paper-assistant\scripts\retrieve_stacks.py --query "flat morphism of schemes definition" --top-k 8
```

仅查 arXiv（带默认类别约束）：

```powershell
python skills\ag-stacks-paper-assistant\scripts\retrieve_papers.py --query "flat morphism of schemes" --top-k 6
```

默认 arXiv 类别约束为：

- `math.AG, math.AC, math.RT, math.NT, math.KT, math.RA, math.AT`

若要覆盖默认类别，可显式传参：

```powershell
python skills\ag-stacks-paper-assistant\scripts\retrieve_papers.py --query "derived stacks" --categories "math.AG,math.AT"
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
- 若 arXiv 超时/限流，主流程会降级为“仅 Stacks”，并在输出中给 `warnings`。
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

