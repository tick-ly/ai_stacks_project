# AG Gem Retrieval Policy

## Goal

Keep AG retrieval sharp, source-aware, and query-shaped instead of relying on the raw user sentence alone.

## Retrieval Order

1. The Stacks Project for foundational facts
2. papers and scholarly discovery tools for research context
3. expert discussion sources for intuition and comparison
4. generic context sources only as a fallback

## Query Rewriting

Before retrieving, rewrite the user request into 2-4 focused search views instead of using only the raw question.

Preferred views:

1. concept view
- formal term
- notation
- close synonym

2. theorem / criterion view
- known theorem names
- equivalent formulations
- local criteria

3. literature view
- paper-friendly keywords
- survey wording
- adjacent subfield labels

4. alternate terminology view
- older names
- notation variants
- school-specific naming

Prefer a small set of sharp rewrites over many weak ones.

## Local and Global Search Mindset

Use a local/global split inspired by graph-aware retrieval:

- local search: exact concept, tag, theorem, lemma, criterion, counterexample
- global search: topic map, literature cluster, community-level trend, theme relation

Routing rule:

- definition / criterion / proof question -> local first, then global context if needed
- survey / latest / reading-path question -> global first, then local anchors for key facts

## Source Tiers

Preferred tiers:

1. `The Stacks Project`
2. `arXiv`, `OpenAlex`, `Semantic Scholar`
3. `Crossref`
4. `MathOverflow`, `Math StackExchange`
5. `Wikipedia`

Use `MathOverflow` / `Math StackExchange` for intuition, terminology differences, and references, not as the sole basis for theorem truth.

## Default arXiv Scope

Unless the user overrides:

- `math.AG OR math.AC OR math.RT OR math.NT OR math.KT OR math.RA OR math.AT`

## Evidence Scoring

Score candidate evidence by:

1. relevance
2. rigor
3. specificity of assumptions
4. freshness when the user asks for latest work
5. cross-support from multiple credible sources

Keep sources that are highly relevant plus at least one of rigor, specificity, freshness, or cross-support.

## Freshness-aware ranking rule

- For prompts indicating latest / survey / comparison intent, paper/web ranking increases recency sensitivity before fusion.
- If the pipeline outputs `freshness_intent=true`, prioritize newer items when source quality and relevance are otherwise comparable.
- This priority should not override:
  - theorem-level AG factuality that requires Stacks grounding
  - obvious API/domain mismatches

## Conflict Handling

If sources conflict, do not flatten them into one blended answer.

Check whether the conflict comes from:

- different assumptions
- different terminology
- different categorical level
- historical versus modern formulation
- expository simplification versus theorem-level precision

Prefer primary, canonical, and theorem-level sources for factual claims.

## Degradation Rules

If papers/web are unavailable or unreliable:

- continue with a Stacks-grounded answer
- add a short warning
- do not fabricate paper references
- prefer route `stacks_only_degraded`
- annotate warning/degradation with canonical `degrade_reason` (`tls_restricted` / `timeout` / `parse_error` / `error` / `no_matches`)

If Stacks is unavailable but papers/web are available:

- continue with papers/web evidence
- downgrade certainty for foundational claims
- avoid fabricating theorem IDs or tags
- prefer route `papers_only_degraded`
- annotate warning/degradation with canonical `degrade_reason`

If both sides fail:

- explain the evidence gap
- ask for a narrower target, paper, URL, tag, or assumption set
- add an `Evidence Gaps` block and route `retrieval_unavailable`

When a source returns zero usable hits:

- mark `no_matches` in source-level and pipeline-level diagnostics.
- keep this explicit in warning text and `degradations`.

## Error Contract

- Pipeline errors should be consumed from structured error payloads:
  - `{"code": "...", "message": "...", "details": "...", "source": "..."}`
- Use `code` for deterministic warning language and route notes.
- Also read and preserve `degrade_reason` for stable branching:
  - `tls_restricted`, `timeout`, `parse_error`, `no_matches`, `error`.
- Expected codes include `STACKS_RETRIEVAL_ERROR`, `PAPERS_RETRIEVAL_ERROR`, `CITATION_FORMAT_ERROR`, `RELEVANCE_CLASSIFY_ERROR`, and `PIPELINE_SUBPROCESS_ERROR`.

## Pipeline Observability Fields

- Prefer reading these top-level fields if present:
  - `degradations`
  - `source_confidence` (0~1)
  - `evidence_quality` (`high` / `medium` / `low`)

- If `source_confidence` is low or `evidence_quality` is `low`, explicitly lower certainty and request narrowing before strong claims.
