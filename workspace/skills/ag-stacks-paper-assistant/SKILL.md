---
name: ag-stacks-paper-assistant
description: Answer algebraic geometry questions with strict relevance gating, evidence-first reasoning, Stacks Project retrieval, and live paper search. Use when user asks for algebraic geometry definitions, theorems, proofs, examples, references, literature reviews, or research-oriented explanations; when answers must cite Stacks tags and/or papers; when user input may be off-topic and must be classified before deep response.
---

# AG Stacks Paper Assistant

Execute this workflow whenever the user asks mathematical content that could involve algebraic geometry.

## Core Contract

1. Classify relevance first.
2. If not algebraic-geometry-related, do not force an AG answer.
3. If related, retrieve from local Stacks index first, then web papers.
4. Ground key claims in citations.
5. Separate established facts from uncertain inferences.

## Step 0: Relevance Gate (Mandatory)

Run `scripts/classify_relevance.py` on user input.

Output one of:

- `high`: clearly algebraic geometry
- `medium`: partially related or ambiguous
- `low`: not algebraic geometry

Behavior:

- `low`: answer briefly, say it is low relevance, ask whether user wants AG reframing.
- `medium/high`: continue with retrieval pipeline.

## Step 1: Retrieve Stacks Evidence

Run `scripts/retrieve_stacks.py` with the user query.

Default behavior:

- use hybrid retrieval from local `data/index` and `data/processed/corpus.jsonl`
- return top results with `tag`, `title`, `reference`, `snippet`, and Stacks URL
- assign citation ids as `[S1]`, `[S2]`, ...

Prioritize:

- definitions before theorem-heavy details when user is learning basics
- theorem/lemma/proposition when user asks proof-level content

## Step 2: Retrieve Paper Evidence

Run `scripts/retrieve_papers.py` with the same query.

Default behavior:

- search arXiv via public API
- return paper metadata and links
- assign citation ids as `[P1]`, `[P2]`, ...
- default to strict TLS verification
- if SSL validation fails:
  - first provide `--ca-bundle` or truststore/certifi chain
  - only then optionally use `--allow-insecure-ssl-fallback`, and disclose this in the answer

Use paper evidence to:

- provide broader context
- support "latest direction" requests
- compare formulations if Stacks is not enough

## Step 3: Build Citation Block

Run `scripts/format_citations.py` with Stacks and paper JSON outputs.

This produces:

- in-text citation map
- reference list section for final answer

## Step 4: Compose Final Answer

Use the style guide in `references/ag_prompt_style.md`.

Required answer shape for medium/high relevance:

1. Relevance verdict and scope line.
2. Main explanation.
3. Optional "pathologies / boundaries" section for advanced topics.
4. Citation list at the end.

Citation rules:

- cite every major factual claim or theorem-level statement
- prefer Stacks citations for foundational statements
- use paper citations for current research context
- do not cite sources you did not retrieve

If evidence is weak:

- explicitly state uncertainty
- list what is missing
- avoid fabricated theorem numbers, tags, or bibliography entries

## References to Load On Demand

- `references/ag_prompt_style.md`
- `references/citation_policy.md`
- `references/web_search_policy.md`

## Scripts

- `scripts/classify_relevance.py`
- `scripts/retrieve_stacks.py`
- `scripts/retrieve_papers.py`
- `scripts/format_citations.py`
- `scripts/ag_assistant_pipeline.py`

## Evaluation

Use `evals/evals.jsonl` for quick manual or scripted checks:

- relevance routing
- citation presence
- citation quality
- handling of low-relevance inputs
