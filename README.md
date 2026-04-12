# ai_stacks_project

Toolkit and workflow assets for:

- Stacks Project vectorization pipeline
- AG retrieval and evaluation scripts
- AG skill package
- Gemini Gem templates and knowledge files

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
