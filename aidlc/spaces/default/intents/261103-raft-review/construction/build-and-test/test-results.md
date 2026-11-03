# Test Results

## Build status

Success. `python -c "import raft, sim"` printed `import ok` (Python 3.13.5).

## Commands run (each once)

| Command | Exit | Result |
|---|---|---|
| `python -m pytest -q tests/test_mutation_check.py tests/test_invariants_negative.py tests/test_storage.py tests/test_linearizable.py` | 0 | 71 passed in 2.51s |
| `python -m pytest -q` | 0 | 233 passed in 11.87s |
| `python -m pytest --collect-only -q` | 0 | 233 tests collected |

Totals for the full suite: 233 total, 233 passed, 0 failed, 0 skipped.

Baseline before the changes (recorded in the build step): 212 passed in 11.30s. After: 233 passed. No test was removed, skipped or weakened.

## Failure details

None.

## Coverage report

Not measured. The proof-of-concept scope adds no coverage floor and the project has no coverage configuration.

## Not run

- `python tools/mutation_check.py`: not run, by the owner's choice. The README's "19 of 19 mutants caught" figure is therefore unverified. The tool's new logic is covered only by tests that stub the pytest call.
- `python -m mypy raft sim`: mypy is not installed.
- The README's `PYTHONHASHSEED` claim: no script or output exists to run.

## Target Verification Matrix

See `build-and-test-summary.md`.
