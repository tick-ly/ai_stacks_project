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

## Recent Updates (2026-04-12)

- Refactored Gemini Gem prompting toward continuation-first operation instead of one-shot long answers.
- Integrated the slot-based retrieval skeleton:
  - `定 / 判 / 例 / 反 / 联 / 用`
- Added continuation-oriented knowledge docs:
  - `AG_GEM_CONTINUATION_PROTOCOL.md`
  - `AG_GEM_RETRIEVAL_TEMPLATE.md`
- Updated the long AG prompt template to support:
  - one closed reasoning unit per turn
  - `CONTINUE_STATE` checkpoints
  - stable slot-by-slot continuation instead of restarting from scratch

## License

MIT. See `LICENSE`.
