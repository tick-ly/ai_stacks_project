# AG Gem Citation Policy

## Citation Types

- Stacks citations: `[S1]`, `[S2]`, ...
- Paper/Web citations: `[P1]`, `[P2]`, ...

## Minimum Requirements

- Every theorem-level factual statement should have at least one citation.
- Every nontrivial definition should cite source when available.
- Trend/latest claims should cite papers or multi-source web evidence.
- If papers/web are unavailable or unreliable, do not emit `[P*]` citations.

## Stacks Citation Format

Include:

- tag
- reference number (if available)
- title (if available)
- URL

Example:

- `[S1] Tag 01UA, Lemma 37.12.1, https://stacks.math.columbia.edu/tag/01UA`

## Paper/Web Citation Format

Include:

- title
- authors
- year
- source (`arXiv`, `OpenAlex`, `Semantic Scholar`, `Crossref`, `MathOverflow`, `Math StackExchange`, `Wikipedia`)
- URL
- one short relevance note (recommended)

Example:

- `[P1] Some Result Title, A. Author, 2024, arXiv + OpenAlex, https://arxiv.org/abs/...`
- `[P2] Discussion Title, 2021, MathOverflow, https://mathoverflow.net/questions/...`

## Preference Order

1. Stacks for foundational AG facts.
2. Papers for current research context.
3. MO/MSE for intuition and references, not as sole theorem proof.
4. If evidence is insufficient, explicitly state insufficiency.

## Claim-to-Citation Binding

- Major claims should be followed by at least one matching citation.
- Do not place unrelated references only at the end without mapping to claims.
- When uncertain, mark the sentence as inference and cite supporting context if available.
