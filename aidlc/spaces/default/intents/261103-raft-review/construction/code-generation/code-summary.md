# Code Summary

## Result

- Baseline `python -m pytest -q` on the untouched tree: 212 passed in 11.30s.
- Final `python -m pytest -q`: 233 passed in 11.27s (21 new cases, 82 distinct tests, up from 62). Re-run by the conductor after the build: 233 passed in 11.59s.
- Nothing under `raft/` was changed (FR7.1).
- `tools/mutation_check.py` was edited but never run (Q4). Its logic is covered by tests that stub the pytest call.

## Files created or modified

| File | Change | Requirement |
|---|---|---|
| tools/mutation_check.py | `run_layer` returns failed, passed or error; only pytest exit code 1 counts as caught; exit codes 2 and 5 and a timeout are errors; a baseline run of both layers on unmutated code happens first and a failing baseline stops the run with exit 2; survivors exit 1, errors without survivors exit 3; the "pattern not found exactly once" `assert` became a `RuntimeError` | FR2.1, FR2.2 |
| tests/test_mutation_check.py (new) | 7 test functions, 8 cases, with `subprocess.run` stubbed | FR2.1, FR2.2 |
| tests/test_invariants_negative.py (new) | 8 tests: a valid state, one per checked property (six), and a prefix-mismatch case | FR3.1 |
| tests/test_storage.py (new) | 5 tests: term and vote restored after reopening, append and read, truncate, term guard | FR3.2 |
| pyproject.toml | pytest declared under `[project.optional-dependencies] test`; `[tool.mypy]` section added | FR4.1, FR4.2 |
| tests/test_linearizable.py | docstring states the one-client, one-register assumption and that an abandoned attempt could commit late; failure message says "client-visible anomaly (not a Raft invariant failure)" | FR6.1 |
| README.md | states the owner made the design decisions; notes the design record was reconstructed after the code and is not an AI-DLC record; lists `docs/` in the layout; test figures now 82 tests / 233 cases, about 11s; the "Ran mypy" claim removed because mypy is not installed here; the "19 of 19 mutants" figure and the rest of the AI-tools note unchanged | FR5.1 to FR5.4, FR4.2 |
| docs/design-decisions.md | D4 and D8 name the author (the owner) as decision-maker | FR5.1, FR5.2 |

## Key decisions

- The README's account of the process was made to agree with the design record, which says it was reconstructed after the code. You gave no instruction to say the AI-DLC flow came before the code, and the two files now agree.
- mypy was not installed, so it was not run and nothing was installed. The claim was removed and a `[tool.mypy]` section was added for later use.

## For you to decide

- README.md line 124 says "the model made most of the detailed design calls". That sits against your statement that you made the design decisions. It was left as written.
- README.md line 145 (a mypy `NamedTuple` finding) and D2 in docs/design-decisions.md ("mypy was added later") still mention mypy as history.
- The storage test relies on the `assert` in `Storage.save_hard_state` being active, so it fails under `python -O` (see finding F2).
- The negative tests match each property's violation message. A removal check (delete a check in `sim/invariants.py` and see the test fail) was not run, because it would mean editing `sim/`.

## Written review

Status: **fixed** = changed in this work; **reported** = left as it is, in `raft/` (not changed by your choice in Q3) or not selected; **owner** = needs your decision.

| ID | Severity | Location | Finding | Recommended action | Status |
|---|---|---|---|---|---|
| F1 | Observation | raft/node.py:363 | A second leader in the same term raises `AssertionError` inside `receive` instead of being ignored | Keep for a test harness; if this becomes a real node, ignore the message and log it | reported |
| F2 | Observation | raft/storage.py:45 | The monotonic-term guard is an `assert`, which `python -O` removes | Replace with an explicit `if` and `raise` | reported |
| F3 | Observation | raft/storage.py:71, raft/node.py:406 | Nothing guards a log truncation below the commit index | Add a guard that refuses to truncate committed entries | reported |
| F4 | Suspected | tests/test_hardening.py:103-111, README:105 | In the default configuration a leader that can send but not receive wedges the cluster; this is documented and pinned by a test | Say plainly in the README that the defaults ship the weaker behaviour | reported |
| F5 | Hypothesis | raft/node.py:323 | The CheckQuorum window (15 ticks) might cause spurious step-downs if round-trip delays approach it | Add a test with delays near the window | reported |
| F6 | Observation | sim/cluster.py:207-233, README:32 | Client commits are at-least-once, with no dedup | Keep; already acknowledged | reported |
| F7 | Suspected | tests/test_linearizable.py:9-10 | The claim that retries are harmless is weaker than stated; one client, one register | Claim reworded and failure message made explicit | fixed |
| F8 | Observation | sim/invariants.py | The Leader Append-Only property is not checked | Add the property and a negative test | reported |
| F9 | Observation | sim/invariants.py | The checker had no negative tests | Added one per checked property | fixed |
| F10 | Observation | storage.py | Storage had no tests of its own | Added `tests/test_storage.py` | fixed |
| F11 | Suspected | tools/mutation_check.py:85-91 | Any non-zero pytest exit counted as caught, and there was no baseline run | Baseline added; only exit code 1 counts as caught | fixed |
| F12 | Observation | tools/mutation_check.py:26 | All 19 mutants target node.py | Add mutants for storage, the state machine and the checker | reported |
| F13 | Observation | tools/mutation_check.py | Not wired to CI; no CI exists | Add CI when wanted | reported |
| F14 | Observation | tests/test_figure8.py:20-26, tests/test_node_unit.py | Tests drive private methods and state | Accept, or move to public hooks | reported |
| F15 | Observation | tests/ (delays) | Delays never exceed 8 ticks and no test crashes between persisting and replying | Add tests for large delays and for that crash point | reported |
| F16 | Observation | tests (sizes) | Cluster sizes 2 and 4 are never exercised | Add them | reported |
| F17 | Observation | tests/test_chaos.py, tests/faults.py:47-48 | Chaos uses one key and only `Set`, and repairs whenever no majority can talk | Widen the workload | reported |
| F18 | Observation | README:131 vs docs/design-decisions.md D4, D8 | README and design record disagreed about who decided what | README and D4 and D8 now name you | fixed |
| F19 | Observation | README:118 vs docs/design-decisions.md:3-7 | README described an AI-DLC flow before the code; the record says it was reconstructed after | README now agrees with the record | fixed |
| F20 | Observation | README layout | `docs/design-decisions.md` was not listed | Listed | fixed |
| F21 | Observation | README:134-137 | The mypy and PYTHONHASHSEED claims could not be reproduced; no mypy config, pytest not declared | pytest declared; mypy config added; mypy claim removed. The PYTHONHASHSEED claim was not addressed | owner |
| F22 | Observation | README:124 | "the model made most of the detailed design calls" against your statement | Decide the wording | owner |

## Tests written but not executed

None. All new tests were run in the build step. `tools/mutation_check.py` itself was not run, by your choice.

## Deviations from the plan

None. Step 10 is this file and `traceability.json`.
