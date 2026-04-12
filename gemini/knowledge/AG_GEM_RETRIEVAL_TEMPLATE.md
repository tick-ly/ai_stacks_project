# AG Gem Retrieval Template

## Master Mnemonic

Use this structure for any mathematical object:

- `定` definition
- `判` criteria
- `例` examples
- `反` counterexamples / pathologies
- `联` relations
- `用` uses

This is the default retrieval skeleton for concepts such as:

- Noetherian ring
- flat module
- prime ideal
- integral extension
- tensor product

## What Each Slot Means

- `定`
  - what it is
  - notation
  - smallest working model

- `判`
  - equivalent characterizations
  - common tests
  - easier verification conditions

- `例`
  - most typical positive examples

- `反`
  - most typical failures
  - which removed condition breaks the statement

- `联`
  - what implies it
  - what it implies
  - which converses fail
  - when two notions become equivalent

- `用`
  - what kinds of problems it solves
  - trigger words in exercises
  - common tool combinations

## Self-Diagnosis Before Retrieval

Before searching, ask:

- am I missing `定`?
- am I missing `判`?
- am I missing `例 / 反`?
- am I missing `联`?
- am I missing `用`?

Do not search vaguely. Search for the missing slot.

## Translation Rule

Convert vague confusion into structured math questions.

Examples:

- `这东西有什么用？`
  - what problems does it solve
  - common application patterns
  - which theorems use it as a bridge

- `为什么这里要局部化？`
  - local criterion
  - localization preserves what
  - local-global principle

- `为什么这里 mod 掉极大理想？`
  - residue field method
  - quotient by maximal ideal
  - reduction mod m

## Slot-Aware Continuation

Do not fill all six slots in one turn unless topic is tiny.

Recommended pattern:

- Turn 1:
  - `定 + 例`
- Turn 2:
  - `判 + 局部解释`
- Turn 3:
  - `反 + 边界`
- Turn 4:
  - `联 + 用`

If user asks a proof-heavy question, reorder as needed:

- `定 + 判`
- then `联 + proof`
- then `反 + 用`

## Operation Layer

For algebra / AG topics, also check:

- what happens after localization
- what happens after quotient
- what happens after tensor
- what happens after extension
- what happens after completion

## Knowledge Card Template

For durable memory, organize each concept as:

1. name
2. definition
3. criteria
4. examples
5. counterexamples
6. relations
7. operations
8. uses
9. trigger words

## One-Line Reminder

Do not search for words only.
Search for the missing structural slot and turn it into a callable unit.
