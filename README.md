# ai_stacks_project

## 项目介绍

这是一个面向代数几何（Algebraic Geometry）问答的检索增强项目，目标是把本地 Stacks Project 知识与外部论文/讨论源统一到同一输出链路中，并为 Gemini 提供可控、可审计、可降级的证据来源。

核心目标：

- 在本地先做 Stacks 检索，再补充论文与 web 文献；  
- 根据 `relevance` 与多源命中状态自动降级；  
- 在证据不足时明确表达不确定性与 `degrade_reason`；  
- 以统一模板/文档约束 Gemini 的回答风格与引用边界。

## Toolkit scope

- Stacks Project vectorization pipeline
- AG retrieval and evaluation scripts
- AG skill package
- Gemini Gem templates and knowledge files, you can test at:
- https://gemini.google.com/gem/1u-xtwhPV69k6PUFGiWADBds6f-0TwGny?usp=sharing

## Included

- `workspace/` (scripts, config, docs, skill, gem templates)
- `gemini/` (Gem setup package)
- `workspace/data/processed/` (processed corpus artifacts)
- `workspace/data/index/` (retrieval indexes)

## Excluded

- `stacks-project/` (excluded by request)

## Data Storage Notes

- `workspace/data` is excluded by default.
- Only `workspace/data/processed` and `workspace/data/index` are included.
- Large files in these paths are stored via Git LFS (`*.jsonl`, `*.npy`, `*.db` as configured).

## Recent Updates (2026-04-11)

- Upgraded AG Skill pipeline robustness:
  - relevance gating + hybrid retrieval path
  - arXiv default category constraints (`AG/AC/RT/NT/KT/RA/AT`)
  - paper retrieval fallback to Stacks-only mode with warnings
  - stricter citation and uncertainty handling
- Upgraded Gemini Gem package to align with current agent behavior (`gemini/` and `gemini/knowledge/`).
- Added/updated retrieval improvement planning and risk documentation.

## License

MIT. See `LICENSE`.
