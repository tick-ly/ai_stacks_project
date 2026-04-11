# Retrieval Improvement Plan

Date: 2026-04-10

## Goal

Improve retrieval quality and remove known shortfalls found in the latest evaluation pass.

## Prioritized Actions

1. `exact tag direct-hit`
2. `Chinese query expansion`
3. `intent parsing + structured rerank`
4. `bucket metrics in eval output`
5. stronger embedding model comparison
6. proof/statement route balancing
7. citation-graph-aware rerank

## Implemented Now (First 4 Items)

### 1) Exact Tag Direct-Hit

Status: `done`

What changed:

- Detects strict tag-shaped queries (`^[0-9A-Z]{4}$`).
- Seeds exact tag into candidate set before final ranking when corpus + filters allow it.
- Adds a strong direct-hit boost.

Why:

- Avoids the old behavior where exact tag bonus only applied if tag already appeared in candidates.

### 2) Chinese Query Expansion

Status: `done`

What changed:

- Adds a compact Chinese-to-English expansion table for high-value AG terms.
- Expands query text before vector encoding and BM25 lookup.

Terms included (examples):

- `概形 -> scheme`
- `层 -> sheaf`
- `平坦 -> flat`
- `态射 -> morphism`
- `代数栈 -> algebraic stack`
- `上同调 -> cohomology`
- `余切 -> cotangent`
- `除子 -> divisor`

### 3) Intent Parsing + Structured Rerank

Status: `done`

What changed:

- Detects query intent signals:
  - exact tag
  - env preference (`definition`, `theorem`, `lemma`, `proposition`, `remark`)
  - proof intent
  - reference-like patterns (`13.21.2`)
  - chapter hints
- Applies targeted boosts during final hybrid scoring:
  - exact tag
  - env match
  - proof preference
  - reference match
  - chapter hint match
  - lightweight title/full_label token hits

Why:

- Moves ranking from pure weighted fusion to intent-aware ranking without changing external APIs.

### 4) Bucket Metrics in Eval Output

Status: `done`

What changed:

- `eval_retrieval.py` now includes query `category` in `per_query`.
- Adds `aggregate_by_category` with the same Recall/MRR keys as global aggregate.

Why:

- Lets us track progress per shortfall bucket (`tag_direct`, `definition`, `theorem`, `proof`, `chapter_filter`, `chinese`) instead of only one global score.

## Files Updated

- `workspace/scripts/retrieval_engine.py`
- `workspace/scripts/eval_retrieval.py`

---

## Implemented Now (Item 7: GraphRAG-Style Citation Graph Retrieval)

Status: `done`

What changed:

- Added citation graph construction from `corpus.jsonl` (`outgoing_refs` + implicit incoming edges).
- Added GraphRAG-style neighborhood expansion from top base seeds:
  - outgoing citation propagation
  - incoming citation propagation
  - multi-hop decay
- Added graph score and centrality prior into final rerank.
- Added tunable graph parameters to:
  - `scripts/search_demo.py`
  - `scripts/eval_retrieval.py`
  - `skills/ag-stacks-paper-assistant/scripts/retrieve_stacks.py`
- Added sample config keys for graph retrieval in:
  - `config/pipeline.example.yaml`
  - `config/pipeline.example.json`

Why:

- Pure vector/BM25 often misses locally connected lemmas/theorems that are only obvious through citation neighborhoods.
- Graph expansion improves coverage for theorem chains and proof dependencies while keeping lexical/vector precision as the base signal.

---

## Implemented Now (Item 5: Stronger Embedding Model Comparison)

Status: `done`

What changed:

- Added one-click experiment runner `scripts/run_retrieval_improvement.py`.
- Supports multiple embedding candidates from JSON config:
  - `config/embedding_candidates.sample.json`
- Builds a separate vector index per candidate under `data/index_compare/*`.
- Runs `eval_retrieval.py` automatically for every candidate and writes result artifacts.
- Produces ranked summary outputs:
  - `data/eval/improvement_runs/summary.json`
  - `data/eval/improvement_runs/summary.md`

Why:

- Embedding choice is now a reproducible batch comparison instead of ad hoc single-run checks.

## Implemented Now (Item 6: Proof/Statement Route Balancing)

Status: `done`

What changed:

- Added explicit proof/statement route controls to retrieval:
  - `statement_route_weight`
  - `proof_route_weight`
  - `statement_route_bonus`
  - `proof_route_bonus`
  - `proof_route_fallback_bonus`
  - `nonproof_proof_penalty`
- Wired these controls through:
  - `scripts/search_demo.py`
  - `scripts/eval_retrieval.py`
  - `skills/ag-stacks-paper-assistant/scripts/retrieve_stacks.py`
- Added route grid config for one-click sweeps:
  - `config/route_balance_grid.sample.json`
- Integrated route grid sweep into `run_retrieval_improvement.py`.

Why:

- Makes proof-heavy and statement-first retrieval behavior tunable and measurable instead of fixed heuristics.

## Validation Checklist

1. Run search sanity checks:

```powershell
python scripts/search_demo.py --query "000B" --top-k 3
python scripts/search_demo.py --query "概形 的定义" --top-k 5
python scripts/search_demo.py --query "proof of yoneda" --top-k 5
```

2. Run eval and inspect bucket output:

```powershell
python scripts/eval_retrieval.py --config config/pipeline.example.yaml --output data/eval/latest_metrics.json --regression-tolerance 1.0
```

3. Confirm `aggregate_by_category` exists in output JSON.
