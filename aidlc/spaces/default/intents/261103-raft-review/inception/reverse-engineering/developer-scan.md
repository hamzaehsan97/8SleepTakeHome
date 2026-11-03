## Developer Code Scan Results

### Scan Coverage
- **Analyzed deeply**:
  - raft/ (node.py, storage.py, messages.py, statemachine.py, __init__.py)
  - sim/ (cluster.py, network.py, invariants.py, __init__.py)
  - tests/ (all 11 files: faults.py, helpers.py, test_chaos.py, test_election.py, test_failures.py, test_figure8.py, test_hardening.py, test_linearizable.py; test_node_unit.py and test_replication.py read at test-name level only, bodies not read)
  - tools/mutation_check.py
  - examples/demo.py
  - README.md, docs/design-decisions.md, pyproject.toml
- **Skimmed only**: tests/test_node_unit.py and tests/test_replication.py (test names and docstrings, not bodies)
- **Left out**: .claude/, aidlc/ (AI-DLC install and workspace), .git/, __pycache__/.pytest_cache/.venv/.mypy_cache (ignored, none opened). Nothing was executed: no tests, mutation run, or demo.

### Packages Found
- raft — library package — Python — the Raft node (election, replication, commit rule, PreVote, CheckQuorum), durable storage, wire messages, KV state machine
- sim — test-support package — Python — deterministic network, lock-step cluster driver, per-tick invariant checker
- tests — pytest suite — Python — 62 test functions (grep count; README claims 212 parametrized cases, unverified)
- tools — script — Python — mutation_check.py (19 mutants)
- examples — script — Python — narrated demo

### Build System
- **Type**: none (pure Python, no packaging backend); pytest config only
- **Config Files**: pyproject.toml (`[project]` name toyraft 0.1.0, requires-python >=3.10; `[tool.pytest.ini_options]` pythonpath ".", testpaths "tests")
- **Build Dependencies**: no dependencies declared (pytest not listed, no extras)

### APIs Discovered
- In-process Python API — raft/node.py — RaftNode: propose, tick, receive (3 public entry points) plus properties current_term, quorum
- Wire messages (in-process dataclasses, no serialization) — raft/messages.py — 6 RPC types plus LogEntry
- Client command set — raft/statemachine.py — Set, Delete, Get
- Test harness API — sim/cluster.py — Cluster: crash, restart, pause, resume, tick, run_until, commit, read, propose; sim/network.py — partition, isolate, cut, heal

### Frameworks & Libraries
- Python standard library only (dataclasses, enum, heapq, random, logging, subprocess, concurrent.futures) — runtime and tooling
- pytest — version unpinned/undeclared — tests and mutation tool
- mypy — claimed by README:136 — no config or declaration in repo

### Test Coverage
- **Test Directories**: tests/
- **Test Frameworks**: pytest (parametrized seeds)
- **Coverage Config**: absent (no coverage tooling; README claims no coverage numbers)

### Code Quality Indicators
- **Linting**: none configured (no ruff/flake8/mypy config)
- **CI/CD**: none (no .github or other pipeline files)
- **Documentation**: README.md (147 lines, includes limitations and AI-use note), docs/design-decisions.md (reconstructed after the fact, says so), good module/docstring comments with paper section references

### Technical Debt Signals
- tools/mutation_check.py:85-91 treats any non-zero pytest exit as "caught" (syntax error, collection error, no-tests all count); no unmutated baseline run.
- Invariant checker (sim/invariants.py) has no direct negative tests (grep of tests/ finds no InvariantViolation use).
- tests/test_figure8.py:20-26 drives private `_start_election` directly.
- raft/storage.py:45 uses `assert` for the term-monotonic guard (stripped under python -O).
- No pyproject dependency declaration for pytest; mypy usage unverifiable from repo.

## Handoff Summary
- **Intent-relevant finding**: Raft core (raft/node.py, 480 lines) read line by line against the paper; no clear safety or liveness defect found. Commit rule (node.py:448-458), vote persistence (node.py:200, 236), log-up-to-date check (node.py:216-225), prefix-safe merge (node.py:397-408) and commit cap (node.py:413-415) are all correct. Weaknesses are in test/tooling evidence: mutation tool (tools/mutation_check.py:85-91, :98-105), unchecked checker, single-client linearizability test with at-least-once retries (tests/test_linearizable.py:46, sim/cluster.py:207-233).
- **Risks / follow-up**: Counts and results in README (62 tests / 212 cases, 19/19 mutants, mypy clean) are unverified because nothing was run. README:118 describes an AI-DLC staged flow while docs/design-decisions.md:3-7 says the record was reconstructed after the code and is not an AI-DLC record; worth reconciling. docs/ is not listed in the README layout.
