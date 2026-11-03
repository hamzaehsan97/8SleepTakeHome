# Code Generation Plan

## Summary

- Builds: fixes to the mutation tool, new checker and storage tests, packaging and docs corrections, and a reworded linearizability claim
- Touches: tools/mutation_check.py, pyproject.toml, README.md, docs/design-decisions.md, tests/test_linearizable.py, and four new test files; nothing under raft/
- Tests: about 17 new tests across four new files (one per requirement, plus the six checker properties), and the existing suite stays green

## Scope

Brownfield work on the existing `toyraft` package, modified in place. No Units: this is one implementation pass. Requirements are in `inception/requirements-analysis/requirements.md`. The code knowledge base is `aidlc/spaces/default/codekb/8sleep/`.

README.md and docs/design-decisions.md existed before this work. This plan changes them because the owner asked for it (requirements FR5.1 to FR5.4); each change is named in the steps below.

Rules for the build:
- No file under `raft/` is changed (FR7.1). Findings there are reported only.
- No existing test is removed, skipped or weakened (NFR2).
- `tools/mutation_check.py` is never run (Q4: tests only). Its logic is checked with tests that stub the pytest call.
- Nothing is installed. If `mypy` is not already available, the README's mypy claim is dropped instead (FR4.2).

## Steps

- [x] Step 1: Verify the test runner and record the baseline (NFR1, NFR2). Run `python -m pytest -q` once on the untouched tree and record the test count and run time. Record the exact unit-scoped commands in `unit-test-instructions.md`.
- [x] Step 2: Packaging (FR4.1, FR4.2). In `pyproject.toml` declare pytest as a test dependency under `[project.optional-dependencies]`. Add a `[tool.mypy]` section. Run `python -m mypy raft sim` only if mypy is already installed. If it is installed and passes, keep the README's mypy claim; otherwise remove the claim from the README in Step 8.
- [x] Step 3: Mutation tool, implementation (FR2.1, FR2.2). In `tools/mutation_check.py`, have `run_layer` return a result with three outcomes: tests failed (caught), tests passed (survived), and error (syntax or import error, collection error, nothing collected, or timeout). Only a plain test failure counts as caught. Add a baseline run of both layers on unmutated code before any mutant, and exit with a clear message and non-zero status if the baseline does not pass. Print errors separately from caught mutants and keep the existing exit codes for survivors.
- [x] Step 4: Mutation tool, tests (FR2.1, FR2.2). Write `tests/test_mutation_check.py`. It loads the tool by file path and replaces the `subprocess.run` call with stubbed results. Cases: a baseline that fails stops the run before any mutant; exit code 1 counts as caught; exit codes 2 and 5 and a timeout are reported as errors and not as caught; exit code 0 is a survivor. Run it.
- [x] Step 5: Invariant checker, negative tests (FR3.1). Write `tests/test_invariants_negative.py`. For each of the six properties in `sim/invariants.py` build the smallest state that violates it and assert `InvariantViolation` is raised: term goes backwards, two leaders in one term, different entries committed at one index, applied index above commit index, leader missing a committed entry, and logs that diverge despite equal terms. Add one test that a valid state passes. Run it.
- [x] Step 6: Storage, tests (FR3.2). Write `tests/test_storage.py`. Cover: persisted term and vote restored after reopening, append and read back, truncate, and the term guard refusing a lower term. Use a temporary directory and no cluster. Run it.
- [x] Step 7: Linearizability test (FR6.1). In `tests/test_linearizable.py` reword the comment that says retries are harmless so it states the assumption exactly: it holds for one sequential client and one register, and an abandoned attempt could in principle commit after a later write. Make the test fail with a message that says "client-visible anomaly" rather than a Raft failure when a read returns an older value than the last acknowledged write. Run it.
- [x] Step 8: Docs (FR5.1 to FR5.4). In `README.md`: state that the owner made the design decisions, as the owner confirmed; list `docs/` in the layout; remove or keep the mypy claim per Step 2; make the test count and run time match the baseline from Step 1 and the final run in Step 9. Leave the "19 of 19 mutants caught" figure as written, because the tool is not run. In `docs/design-decisions.md` correct D4 and D8 to name the owner as the decision-maker. The record's statement that it was reconstructed after the code is kept, and the README's account of the process is made to agree with it. Everything else in the README's AI-tools note is kept.
- [x] Step 9: Run and compare (NFR1, NFR2). Run `python -m pytest -q` on the finished tree. It must pass, and the test count must be at least the baseline count.
- [ ] Step 10: Documentation and traceability (FR1, NFR3). Write `code-summary.md` with the written review: every finding from `codekb/8sleep/code-quality-assessment.md` with severity, file and line, recommended action, and status (fixed here, reported only, or left for the owner), plus the list of changed files with the requirement each satisfies. Write `traceability.json`.

## Testing Contract

```json
{
  "version": 1,
  "methodology": "test-after",
  "source": "org",
  "ordering": "implement each applicable testable layer, then write and run that layer's tests.",
  "scope": "poc",
  "test_strategy": "minimal",
  "project_type": "brownfield",
  "applicable_notes": [
    {
      "layer": "org",
      "text": "We treat tests as a first-class deliverable in every Bolt. The specific\nmethodology (TDD, BDD, ATDD, or classic test-after) is affirmed at\npractices-discovery and recorded in `team.md` under this heading with explicit\n`Methodology` and `Ordering` fields; Code Generation resolves those fields\nindependently from coverage, tooling, and scope notes.\n\nWhen no posture has been affirmed, our default per scope is:\n- **Methodology**: test-after\n- **Ordering**: implement each applicable testable layer, then write and run\n  that layer's tests.\n- `mvp`, `enterprise`, `feature`, `infra`, `classic` add an 80% line-coverage\n  floor and CI execution before merge.\n- `bugfix`, `security-patch` add a targeted regression for the specific\n  bug/vulnerability and require the existing suite to remain green.\n- `express` uses the Minimal strategy: requirement-driven unit tests (one per\n  requirement, with a happy-path floor per component); existing tests remain\n  green.\n- `poc`, `refactor`, `workshop` add no extra new-test floor and require the\n  existing suite to remain green.\n\nThe active `Test Strategy` still applies in every scope and determines test\nvolume/types. Scope floors are additive; they never reduce or replace the\nselected strategy.\n\nBuild and Test verifies defined coverage floors and affirmed quality targets;\nthey may not be weakened to make a step pass.\n\nAffirm a stricter posture in `team.md` if the team commits to one."
    }
  ],
  "obligations": {
    "strategy": "minimal",
    "strategy_volume": [
      "One verifiable test per requirement at the narrowest effective level.",
      "At least one happy-path unit test per component.",
      "Unit tests are the default; a bugfix/security scope floor may require an integration or E2E regression when that is the narrowest level that reproduces the defect."
    ],
    "scope_floor": [
      "Keep the existing test suite green.",
      "This scope adds no extra new-test floor beyond the selected test strategy."
    ],
    "combination_rule": "Apply every selected-strategy obligation and every scope-floor obligation; neither replaces the other, and a targeted scope regression may add the narrowest necessary test type beyond the strategy default."
  },
  "plan_profile": {
    "methodology": "test-after",
    "runner_step": "Verify the existing test runner/configuration and record the exact unit-scoped command.",
    "runner_ready_before_first_test": true,
    "testable_layers": [
      "Data model / database behavior",
      "Repository / data access",
      "Business logic",
      "API / endpoint",
      "Frontend behavior"
    ],
    "steps": [
      "Project structure and production configuration skeleton.",
      "Verify the existing test runner/configuration and record the exact unit-scoped command.",
      "Data model / database behavior - implement.",
      "Data model / database behavior - write and run its tests after implementation.",
      "Repository / data access - implement.",
      "Repository / data access - write and run its tests after implementation.",
      "Business logic - implement.",
      "Business logic - write and run its tests after implementation.",
      "API / endpoint - implement.",
      "API / endpoint - write and run its tests after implementation.",
      "Frontend behavior - implement.",
      "Frontend behavior - write and run its tests after implementation.",
      "Environment/build configuration.",
      "Documentation and traceability."
    ]
  },
  "input_sha256": "sha256:ddd208517f68585f816e80821872bd21e26dc15e7bf545c6a78ec96b6afc20da",
  "contract_sha256": "sha256:8780c9b6738d34215859c7d0d02b149a16944cf2942a43d2c2dee67268c80df0"
}
```
