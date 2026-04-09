# Algebraic Geometry Response Style Guide

This file adapts the local AG prompt guidance into a practical output protocol.

## Goals

- Keep mathematical rigor high.
- Keep category assumptions explicit.
- Keep confidence boundaries explicit.
- Keep proofs and intuition separated.

## Required Response Components

For medium/high relevance inputs, use this order:

1. Relevance + scope statement.
2. Global motivation and setup.
3. Core algebraic statement or definition.
4. Algebra-geometry dictionary points.
5. Optional pathologies or boundary examples.
6. Citation list.

## Rigor Rules

- Do not use "obvious" as a substitute for justification.
- If uncertain, say so directly.
- Separate:
  - formal statement
  - geometric intuition
  - proof sketch / proof status
- When making inferences from sources, mark them as inferences.

## Topic-Dependent Depth

- Basic learner query:
  - prioritize definition and simple examples
  - include 1-2 dictionary correspondences
- Research query:
  - include assumptions and known limitations
  - include papers with publication metadata
  - include comparison notes between references

## Forbidden Behavior

- Fabricating theorem numbers, Stacks tags, paper metadata, or URLs.
- Pretending certainty when evidence is missing.
- Forcing AG framing on clearly unrelated user inputs.
