# Unit Test Instructions

## Test framework

pytest, already configured in `pyproject.toml` (`pythonpath = ["."]`, `testpaths = ["tests"]`). Run every command from the project root.

## Baseline (before any change)

```
python -m pytest -q
```

Record the test count and run time. The README says 212 cases in about 12 seconds; the baseline run replaces that claim with what was measured.

## Commands for this work

New and changed tests, scoped by exact file path:

```
python -m pytest -q tests/test_mutation_check.py tests/test_invariants_negative.py tests/test_storage.py tests/test_linearizable.py
```

Per file, as each is written:

```
python -m pytest -q tests/test_mutation_check.py
python -m pytest -q tests/test_invariants_negative.py
python -m pytest -q tests/test_storage.py
python -m pytest -q tests/test_linearizable.py
```

Final check (the existing suite must stay green, and the count must not drop below the baseline):

```
python -m pytest -q
```

Not run: `python tools/mutation_check.py`. The owner chose to run the tests only. Its logic is covered by `tests/test_mutation_check.py`, which stubs the pytest call.

## Expected coverage

Minimal strategy: one test per requirement and at least one happy-path test per component touched. About 17 new tests:

- mutation tool: 5 or 6 (baseline stops the run, caught on exit code 1, error on exit codes 2 and 5, error on timeout, survivor on exit code 0)
- invariant checker: 7 (one per property, plus a valid state that passes)
- storage: 4 or 5 (term and vote survive a reopen, append and read, truncate, term guard)
- linearizability: the existing test, reworded, with a clearer failure message

No line-coverage floor applies to the proof-of-concept scope, and none is measured.

## Mocking and stubbing

- Mutation tool tests replace `subprocess.run` with a function that returns objects carrying a `returncode`, and one that raises `subprocess.TimeoutExpired`. No real pytest process is started and no file is mutated.
- Invariant checker tests build the smallest `RaftNode` states that violate each property, using the helpers already in `tests/` and `sim/`. Do not mock the checker itself.
- Storage tests use `tmp_path`. No cluster is started.

## Test data

All state is built inside each test. Nothing is shared between tests, and nothing outside the temporary directory is written.
