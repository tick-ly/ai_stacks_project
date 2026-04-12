# AG Gem Continuation Protocol (Hidden-State v1)

## Goal

Keep the benefit of staged continuation without leaking machine-readable control state into the visible answer.

## Internal Continuation Memory

When a topic is too large for one turn, retain the following internally:

- current mode (`quick / study / proof / research`)
- completed themes
- remaining themes
- stable terminology
- retained references

Do not print these items as raw fields.

## User-Visible Rule

If the topic is unfinished:

- end at a natural stopping point
- add one short natural-language line indicating what can be continued next
- do not output code blocks, YAML, JSON, or key-value status lines

Never show raw labels such as:

- `CONTINUE_STATE`
- `slots_done`
- `slots_next`
- `refs_kept`
- `locked_terms`

## Resume Behavior

If the user says "继续", "继续下一部分", or similar:

- resume from the next unfinished theme
- do not restart from the beginning
- use at most 1-2 sentences to reconnect with the previous turn
- keep earlier citation numbering stable when possible

## Depth Floor By Mode

- `quick`: concise, but still give a complete answer fragment rather than only labels.
- `study`: default to a mini-lecture, not a compressed note. Usually cover at least 3 substantial themes such as definition, relation, example, pathology, or use.
- `proof`: state assumptions, theorem shape, proof roadmap, and at least one meaningful proof segment before stopping.
- `research`: anchor the answer in one foundational point plus a small cluster of recent papers or web sources.

## Failure Patterns To Avoid

- outputting a visible control block after the references
- stopping after only "Relevance + Slot Focus + two short paragraphs"
- using the retrieval skeleton as visible machine output instead of explanatory prose
- repeating the whole previous answer when the user only asked to continue
