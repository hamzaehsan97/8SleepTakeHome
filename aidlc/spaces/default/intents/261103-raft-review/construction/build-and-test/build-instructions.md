# Build Instructions

## Dependency installation

The package `toyraft` has no runtime dependencies and needs Python 3.10 or newer (the run used Python 3.13.5). The only test dependency is pytest, now declared in `pyproject.toml`:

```
python -m pip install -e ".[test]"
```

This was not run here: pytest was already available, and nothing is installed by this work.

## Environment setup

No environment variables, config files or local services. Run every command from the project root. `pyproject.toml` sets `pythonpath = ["."]` and `testpaths = ["tests"]`.

## Build commands

There is nothing to compile or bundle. The build check is that the packages import:

```
python -c "import raft, sim"
```

## Build verification

The import command above prints `import ok`. Then run the test commands in `test-results.md`.

## Troubleshooting

- `ModuleNotFoundError: pytest`: install the test extra with the command above.
- `ModuleNotFoundError: mypy`: mypy is not a declared dependency. `[tool.mypy]` is configured in `pyproject.toml`, but mypy is not installed and was not run.
- `tests/test_storage.py::test_lower_term_is_refused_and_leaves_state_untouched` fails under `python -O`, because `Storage.save_hard_state` guards the term with an `assert`. Run pytest without `-O`.
- Do not run `python tools/mutation_check.py` expecting a quick result: it runs up to four workers with a limit of 300 seconds per run, and was not run in this work.
