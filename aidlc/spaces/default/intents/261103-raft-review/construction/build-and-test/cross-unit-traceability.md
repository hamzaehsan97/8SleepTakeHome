# Cross-Unit Traceability

Verdict: **pass** for the tool's check (every ID has an existing target file). No uncovered IDs. The check confirms a target file exists, not that the requirement's pass criterion is met; the exceptions are listed below.

| ID | Covered | Owning stage | Target file |
|---|---|---|---|
| FR1.1 | yes | code-generation | aidlc/spaces/default/intents/261103-raft-review/construction/code-generation/code-summary.md |
| FR1.2 | yes | code-generation | aidlc/spaces/default/intents/261103-raft-review/construction/code-generation/code-summary.md |
| FR2.1 | yes | code-generation | tests/test_mutation_check.py |
| FR2.2 | yes | code-generation | tests/test_mutation_check.py |
| FR3.1 | yes | code-generation | tests/test_invariants_negative.py |
| FR3.2 | yes | code-generation | tests/test_storage.py |
| FR4.1 | yes | code-generation | pyproject.toml |
| FR4.2 | yes | code-generation | README.md |
| FR5.1 | yes | code-generation | docs/design-decisions.md |
| FR5.2 | yes | code-generation | README.md |
| FR5.3 | yes | code-generation | README.md |
| FR5.4 | yes | code-generation | README.md |
| FR6.1 | yes | code-generation | tests/test_linearizable.py |
| FR7.1 | yes | code-generation | raft/node.py |
| NFR1 | yes | code-generation | tests/test_storage.py |
| NFR2 | yes | code-generation | tests/test_node_unit.py |
| NFR3 | yes | code-generation | tools/mutation_check.py |

## Exceptions to the tool's pass

- FR1.1: the written review does not yet account for every finding in the scan (code review R-01).
- FR5.1: README and the design record still disagree (code review R-02). Not met.
- FR2.1 and FR2.2: checked only against a stubbed pytest call. The mutation tool was not run.
- NFR1, NFR2 and NFR3: the target files named above do not themselves evidence these requirements. The evidence is in `test-results.md` and `code-summary.md` (code review R-03).
