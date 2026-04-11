# 当前项目风险与改进建议

评估日期：2026-04-10

## 1. 总体判断

当前项目已经具备可运行的研究型 MVP 形态：它围绕 Stacks Project 构建结构化语料、向量索引、SQLite FTS5 词法索引、混合检索、评估脚本、Codex Skill 与 Gemini Gem 迁移材料。

如果目标是个人研究和本地检索使用，当前基础较好；如果目标是公开交付、团队协作或生产服务，则还需要补强复现、测试、评估、写入兼容和检索质量闭环。

## 2. 主要风险

### 2.1 检索质量风险

当前默认 embedding provider 是 `hash`，适合离线烟测和结构验证，但不是真正语义向量。它能帮助 pipeline 跑通，却不能代表真实语义检索质量。

已观察到的现象：

- 查询 `flat morphism of schemes definition` 时，结果中出现语义相关性较弱的条目。
- 当前混合检索依赖 BM25 与 hash vector 融合，真实语义召回能力仍未被充分验证。

影响：

- 用户可能得到看似相关、实则偏题的 Stacks 条目。
- 如果后续用于问答系统，错误召回会直接放大为错误解释或错误引用。

### 2.2 评估集过小

当前样例评估集只有 5 条 query。现有 baseline 中 `recall@10 = 1.0`、`mrr@10 = 0.9` 只能说明 demo 通，不足以证明系统质量稳定。

影响：

- 无法覆盖定义、引理、定理、证明、章节过滤、tag 直达、中文术语、公式片段等关键场景。
- 后续重构或换 embedding 模型时，缺少可靠回归信号。

### 2.3 Windows 写入兼容风险

在当前 Windows/Codex 环境中，写入型验证暴露了 `Path.replace()` 权限问题：

- `python -m compileall scripts` 写 `__pycache__` 失败。
- `eval_retrieval.py` 写 `data/eval/latest_metrics.json` 时，在原子替换阶段触发 `PermissionError`。

影响：

- 评估脚本在某些 Windows 或受限沙箱环境中可能无法稳定写出结果。
- CI 或本地自动化流程可能出现非业务逻辑失败。

### 2.4 SQLite 临时文件污染风险

读取或写入 `workspace/data/index/lexical.db` 后，SQLite 可能生成：

- `lexical.db-wal`
- `lexical.db-shm`

当前 `.gitignore` 未显式忽略这类文件。

影响：

- 本地验证后容易出现未跟踪文件。
- 如果误提交，会污染仓库并增加不必要的数据文件。

### 2.5 文档与实际数据策略不完全一致

根目录 `README.md` 说明 `workspace/data/` 大生成物被排除，但实际项目通过 Git LFS 跟踪了 `workspace/data/processed/` 和 `workspace/data/index/` 下的核心产物。

影响：

- 新协作者可能不清楚哪些数据需要 `git lfs pull`，哪些需要重新生成。
- GitHub 上查看仓库时，数据边界与复现路径不够明确。

### 2.6 网络与 TLS 依赖风险

AG Skill 中的 arXiv/paper 检索依赖网络与 TLS 证书链。当前本地 Stacks 检索可运行，但端到端 paper pipeline 在受限网络下仍可能失败。

影响：

- 研究型问题如果依赖论文检索，可能降级为仅 Stacks 结果。
- 如果降级提示不够明确，用户可能误以为系统已经完成完整文献检索。

### 2.7 缺少正式测试与 CI

当前项目有脚本和样例评估，但没有明显的正式测试目录、CI 配置或自动化质量门槛。

影响：

- parser、normalizer、hybrid fusion、incremental update 等逻辑变更后缺乏快速保护。
- 长期维护时容易出现静默退化。

## 3. 改进建议

### 3.1 高优先级

1. 补充 `.gitignore`

   建议忽略 SQLite 临时文件：

   ```gitignore
   workspace/data/index/*.db-wal
   workspace/data/index/*.db-shm
   ```

2. 修复 Windows 写入兼容

   建议检查 `common.atomic_write_text()`：

   - 确保临时文件与目标文件都使用一致的绝对路径。
   - 在 Windows 权限受限场景下，为 `Path.replace()` 增加降级写入策略。
   - 如果使用非原子 fallback，应记录 warning，避免静默降低可靠性。

3. 扩充评估集

   建议把 `config/eval_queries.sample.jsonl` 扩展到至少 50-200 条，覆盖：

   - tag 精确查询
   - 定义查询
   - 引理/命题/定理查询
   - 证明类查询
   - 章节过滤
   - 公式片段
   - 中文术语到英文 Stacks 内容
   - 容易混淆的相近概念

4. 建立真实 embedding baseline

   建议用同一评估集对比：

   - `hash`
   - OpenAI embedding
   - local sentence-transformer

   输出 `Recall@K`、`MRR@K`，并记录模型、维度、语料版本和索引构建参数。

### 3.2 中优先级

5. 增加最小自动化测试

   建议测试范围：

   - `parse_tags_file`
   - `normalize_math_text`
   - `extract_tag_refs`
   - `parse_makefile_chapter_keys_from_text`
   - `build_text`
   - `minmax_normalize`
   - `hybrid_search` 的基础排序行为
   - incremental update 的复用逻辑

6. 明确数据与 LFS 复现流程

   建议在 README 中明确：

   - 哪些文件由 Git LFS 管理。
   - clone 后需要运行 `git lfs pull`。
   - 没有 LFS 数据时如何重新生成索引。
   - `stacks-project/` 是本地上游源码目录，不进入仓库。

7. 为 AG Skill 增加离线 smoke test

   建议提供一个不依赖 arXiv 网络的测试命令，只验证：

   - relevance gate
   - local Stacks retrieval
   - citation formatting
   - paper retrieval 失败时的降级结构

8. 强化检索排序策略

   建议在 hybrid fusion 中增加轻量规则：

   - tag 精确命中强提升。
   - 查询包含 `definition` 时提升 `env_type=definition`。
   - 查询包含 `proof` / `prove` 时提升 proof 相关条目。
   - 标题命中、reference 命中、chapter 命中单独加权。

### 3.3 低优先级

9. 增加语料版本元数据

   建议在索引元数据中记录：

   - Stacks Project 源码 commit 或抓取日期。
   - API base URL。
   - tags 文件 hash。
   - corpus hash。

10. 增加查询调试输出

    建议在 search demo 或 debug 模式中输出：

    - BM25 候选
    - vector 候选
    - fusion 前后分数
    - 过滤条件

    这会显著降低检索调参成本。

11. 统一中文文档编码说明

    当前中文 Markdown 在 UTF-8 下是正常的，但某些 PowerShell 默认输出会显示乱码。建议在 README 中注明中文文档均使用 UTF-8，并在 Windows 示例中使用：

    ```powershell
    Get-Content -Encoding UTF8 path\to\file.md
    ```

## 4. 建议执行顺序

建议按以下顺序推进：

1. 修 `.gitignore`，避免 SQLite 临时文件污染。
2. 修 Windows 写入兼容，保证 eval 能稳定写出。
3. 扩充 eval query 到可用规模。
4. 跑真实 embedding 对比实验。
5. 加最小测试和 CI。
6. 更新 README 与 LFS 复现说明。
7. 优化 hybrid ranking。
8. 再考虑更高级的引用图扩展、中文术语扩展和论文检索增强。

## 5. 结论

当前项目方向正确，数据底座和脚本结构已经成型。真正决定下一阶段价值的不是继续堆功能，而是建立可靠的质量闭环：

- 可复现
- 可评估
- 可回归
- 可解释
- 可稳定运行

只要优先补齐评估、写入兼容、真实 embedding baseline 和最小测试，这个项目就能从“能跑的研究工具”推进到“可信赖的数学检索助手底座”。
