<!-- INVARIANT: examples are single-line HTML comments so a fresh template parses to total=0 (MEMORY_EMPTY). Do NOT un-comment or split across lines. t100 guards this. -->
> This file is kept up to date automatically while the stage runs. Add observations at the review step, not by editing here directly.

## Interpretations
<!-- example: 2026-05-29T10:14:32Z — chose REST over GraphQL; the consuming team only needs CRUD, revisit if subscriptions land -->

- 2026-11-02T00:00:00Z — mutation tool: exit codes beyond 0/1 are ERROR; main() returns 2 on failing baseline, 1 on survivors, 3 on errors only. The tool itself was never run.

## Deviations
- 2026-11-02T00:00:00Z — mypy is not installed, so it was not run; the README's "Ran mypy" claim was removed and [tool.mypy] config added to pyproject.toml. README line about a mypy NamedTuple finding and design-decisions D2 ("mypy was added later") were left as historical text.
<!-- example: 2026-05-29T10:14:32Z — skipped the optional caching layer the stage prose suggested; the dataset is small enough that it adds risk -->

## Tradeoffs
<!-- example: 2026-05-29T10:14:32Z — picked TDD over BDD this run; the team is unit-first and the domain is well-understood -->

## Open questions
- 2026-11-02T00:00:00Z — Storage.save_hard_state guards terms with `assert`, which `python -O` strips (raft/ untouched, reported only). Baseline 212 passed in 11.30s; final 233 passed in 11.27s.
- 2026-11-02T00:00:00Z — README line 124 ("the model made most of the detailed design calls") sits uneasily with the owner's statement that they made the design decisions; left as written since no instruction covered it.
<!-- example: 2026-05-29T10:14:32Z — confirm the retention window with compliance before the next stage hardens the schema -->
