# Requirements

Inputs: the intent statement (`ideation/intent-capture/intent-statement.md`), the business overview, architecture and code structure in the code knowledge base (`aidlc/spaces/default/codekb/8sleep/`), and the answers in `requirements-analysis-questions.md` (Q1 to Q4).

## Intent Analysis

The submission is a toy Raft implementation with a simulator and tests, written for a take-home that values polish, reasoning, testability and an honest README note on AI tool use over completeness. The owner wants it reviewed and the clear defects fixed before sending it. The scan found no clear safety defect in the Raft core. The gaps are in the tests, the mutation tool, the packaging and the docs.

## Functional Requirements

### FR1. Written review
- FR1.1 A written review lists every finding from the scan with a severity, a file and line, and a recommended action. Pass: each finding in `code-quality-assessment.md` appears in the review or is explicitly marked as not worth acting on, with a reason.
- FR1.2 The review states for each finding whether it is fixed in this work, left as reported, or left for the owner. Pass: no finding has an empty status.

### FR2. Mutation tool (tools/mutation_check.py)
- FR2.1 The tool runs the test layers once on unmutated code before any mutant, and stops with a clear message if that run does not pass. Pass: with the suite deliberately broken, the tool exits without reporting any mutant as caught.
- FR2.2 A mutant counts as caught only when pytest reports test failures. A syntax error, import error, collection error, no tests collected, or timeout is reported separately and does not count as caught. Pass: a mutant that makes `node.py` unimportable is reported as an error, not as caught.

### FR3. Tests
- FR3.1 Negative tests show that the invariant checker in `sim/invariants.py` raises `InvariantViolation` when given a violation of each property it claims to check. Pass: one test per checked property fails if the property's check is removed.
- FR3.2 Storage has tests of its own covering persisted term and vote, log append and truncate, and reload after a restart. Pass: the tests run without a cluster and fail if the persisted term or vote is not restored.

### FR4. Packaging
- FR4.1 `pyproject.toml` declares pytest as a dependency for running the tests. Pass: a fresh environment installed from `pyproject.toml` can run the suite.
- FR4.2 The README's mypy claim is backed by a mypy configuration in the repo, or the claim is removed. Pass: either `mypy` runs from the repo's own configuration, or the README no longer mentions mypy.

### FR5. Docs
- FR5.1 `README.md` and `docs/design-decisions.md` give the same account of who decided what. Pass: no statement in one contradicts the other.
- FR5.2 The README states that the owner made the design decisions, as the owner confirmed. `docs/design-decisions.md` entries D4 and D8 are corrected to agree. Pass: README and D4 and D8 name the same decision-maker.
- FR5.3 The README layout lists `docs/`. Pass: the layout section includes `docs/design-decisions.md`.
- FR5.4 The README's figures for test count and run time match a run of the suite. Pass: each figure matches the output of the run in NFR1, or is changed to match it. The figure for mutants caught is not changed, because the mutation tool is not run (see Out of Scope).

### FR6. Linearizability test (tests/test_linearizable.py)
- FR6.1 The test either prevents an abandoned retry from committing after a later acknowledged write, or its comment is reworded so it does not claim that retries are harmless in general. Pass: the test's stated claim is true for every history it can produce.

### FR7. Raft source
- FR7.1 No file under `raft/` is changed. Findings about `raft/` (node.py:363, storage.py:45, storage.py:71 and node.py:406, CheckQuorum window) are reported only. Pass: `git diff` shows no change under `raft/`.

## Non-Functional Requirements

- NFR1 Verification. The test suite is run before the fixes and after them, and both runs pass. Pass: pytest exits 0 both times, and its test count and time are recorded in the review. The mutation tool is not run.
- NFR2 No regressions in what exists. Existing tests are not removed, skipped or weakened to make a run pass. Pass: the test count after the fixes is at least the count before.
- NFR3 Traceability. Each change links to the requirement ID it satisfies. Pass: the review's change list cites an FR for every changed file.

## Constraints

- The Raft implementation must stay written from scratch with no consensus or replication library, as the take-home requires. Source: intent statement.
- The work stays within the proof-of-concept plan chosen for this review: the next stage is Code Generation, then Build and Test.

## Assumptions

- The owner's confirmation that they made the decisions credited to the model in D4 and D8 is accepted as stated and recorded in Q2. The README note on how AI tools were used keeps all its other content as written. [assumption]
- Requirement FR5.4 is met by comparing against the output of one run of the suite on this machine. [assumption]

## Out of Scope

- Any change to `raft/`. Findings there are reported only (Q3).
- Running `tools/mutation_check.py` (Q4). The README's "19 of 19 mutants caught" figure stays as the owner wrote it and is not verified here.
- Adding CI, a linter or coverage measurement. These were noted in the scan but not selected in Q1.
- Adding mutants for storage, state machine or checker, and adding the Leader Append-Only check to the invariant checker. Noted in the scan, not selected in Q1.

## Open Questions

- Which wording should the README use for the owner's decisions, given that the design record described the AI-DLC record as reconstructed after the code? FR5.1 and FR5.2 require the two files to agree, and the Code Generation plan will propose the exact text for the owner to check.
