# Technology Stack

| Item | Value | Evidence |
|---|---|---|
| Language | Python >= 3.10 (uses `X | Y` unions at runtime, node.py:35-38) | pyproject.toml:5 |
| Runtime dependencies | none (standard library only) | README.md:3 |
| Test framework | pytest (version not declared) | pyproject.toml:7-10 |
| Type checking | mypy claimed, not configured in repo | README.md:136 |
| Formatter / linter | none configured | repo root |
| CI | none | no pipeline files |
| Packaging | `[project]` metadata only, no build backend | pyproject.toml |
| Concurrency | none by design (single-threaded; ThreadPoolExecutor only in tools/mutation_check.py:113) | |
