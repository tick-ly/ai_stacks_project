# AG Gem Retrieval Orchestration

## Goal

Improve retrieval quality by explicitly controlling query rewriting, evidence selection, reranking, and conflict handling.

## Step 1: Query Rewriting

Before searching, rewrite the user request into 2-4 targeted search views instead of using only the raw user text.

Preferred views:

1. concept view
- formal term
- standard notation
- close synonym

2. theorem / criterion view
- known lemma/proposition/theorem names
- recognition criteria
- equivalent formulations

3. literature view
- paper-friendly keywords
- survey-style wording
- adjacent subfield labels

4. historical / alternate terminology view
- older names
- notation variants
- school-specific naming

Do not expand blindly. Prefer a small set of sharp rewrites over many weak ones.

## Step 2: Source Routing

Choose source emphasis by query type:

- foundational fact -> Stacks first
- proof or criterion -> Stacks + theorem-oriented web support
- latest direction -> papers first, but keep one foundational anchor
- intuition or comparison -> papers + MO/MSE + one canonical source

## Step 3: Evidence Scoring

Score candidate evidence using these dimensions:

1. relevance
- directly answers the user’s actual question

2. rigor
- primary source, canonical source, or theorem-level source

3. specificity
- matches the same assumptions, category, or technical setting

4. freshness
- matters more for “latest” or trend questions

5. cross-support
- independently supported by more than one credible source

Preferred keep rule:

- keep sources that are high on relevance plus at least one of rigor, specificity, or cross-support
- discard attractive but weakly related sources even if they look prestigious

## Step 4: Expansion and Stop Rules

Expand retrieval if:

- top results disagree sharply
- all top results are too general
- the query clearly asks for comparison or latest work
- no source cleanly matches the user’s assumptions

Stop expanding if:

- you already have one canonical/foundational source
- you already have 2-3 strong supporting sources
- new results are mostly duplicates or lower-quality restatements

## Step 5: Conflict Adjudication

If sources conflict, do not flatten them into one answer.

Check whether the conflict comes from:

- different assumptions
- different terminology
- different categorical level
- historical vs modern formulation
- expository simplification vs theorem-level precision

Resolution rule:

- prefer primary / canonical / theorem-level sources for factual claims
- use secondary sources to explain, not to override
- explicitly say when the conflict is really a change of assumptions rather than a contradiction

## Step 6: Answer Binding

Map answer sections to evidence types:

- definition / theorem-level fact -> `[S*]` whenever possible
- recent direction / literature comparison -> `[P*]`
- intuition or community discussion -> MO/MSE only as support, not sole proof

For comparison claims, bind each major comparison to concrete sources instead of only listing them at the end.

## Failure Patterns To Avoid

- searching only the raw user sentence
- keeping the first 1-2 results without reranking
- over-weighting one weak recent source
- mixing incompatible assumptions into one blended answer
- citing papers without explaining what role each paper plays
