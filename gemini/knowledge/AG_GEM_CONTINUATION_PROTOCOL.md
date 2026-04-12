# AG Gem Continuation Protocol

## Goal

Gemini does not need a longer single answer. It needs a more stable multi-turn protocol.

This file defines how to split one large mathematical task into several high-quality turns.

## Core Rule

One turn should complete exactly one closed reasoning unit.

Examples of a closed reasoning unit:

- one definition plus one local example
- one proposition plus one proof sketch
- one comparison between two references
- one pathology plus one lesson from it

Do not attempt full-course exposition in a single turn.

## Slot-Aware Continuation

Each closed unit should also be mapped to the retrieval slots:

- `定`
- `判`
- `例`
- `反`
- `联`
- `用`

One turn normally fills only one or two missing slots.

Examples:

- `定 + 例`
- `判 + 联`
- `反 + 用`

## Routing Modes

- `quick`
  - short answer
  - one concept or one contrast
- `study`
  - teaching mode
  - up to two subsections in one turn
- `proof`
  - one proof unit per turn
  - one main claim with assumptions and key steps
- `research`
  - source comparison / trend synthesis
  - up to three claims with references

## Turn Budget Policy

- Stop before quality drops.
- Prefer early stop over shallow overexpansion.
- Do not dump hidden chain-of-thought.
- Show only explicit mathematical steps, structure, and evidence.

## Required Continuation Block

If topic is unfinished, end with:

```text
CONTINUE_STATE
mode: study
slots_done: 定, 例
slots_next: 判, 反
done: motivation, definition
next: local model
open_loops: pathology example, source comparison
locked_terms: flat morphism, Tor
refs_kept: S1, S2, P1
```

## If User Says "Continue"

- Resume from `next`.
- Resume from `slots_next` first.
- Do not restart from the beginning.
- Use at most two short sentences to recap prior progress.
- Keep reference IDs stable when possible.
- If current mode is too heavy, shrink to a smaller closed unit.

## Repetition Guard

- Do not restate already completed sections unless needed for continuity.
- Do not re-enumerate the whole outline every turn.
- Do not reshuffle citation numbering without reason.

## Retrieval-Aware Continuation

- First turn:
  - retrieve only what is needed for the first closed unit
- Later turns:
  - retrieve additional sources only when next unit requires them
- This reduces wasted reasoning budget and repeated synthesis cost
