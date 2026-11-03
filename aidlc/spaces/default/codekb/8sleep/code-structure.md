# Code Structure

## Layout (tracked files, excluding AI-DLC)
| Path | Lines | Role |
|---|---|---|
| raft/node.py | 480 | RaftNode: roles, election, PreVote, CheckQuorum, replication, commit/apply |
| raft/storage.py | 85 | Durable term, vote and log (1-indexed) |
| raft/messages.py | 77 | Frozen dataclass messages and LogEntry |
| raft/statemachine.py | 50 | KeyValueStore and Set/Delete/Get |
| raft/__init__.py | 37 | Public re-exports |
| sim/network.py | 109 | Seeded unreliable network on logical time |
| sim/cluster.py | 250 | Lock-step driver, fault verbs, client commit/read |
| sim/invariants.py | 108 | Per-tick safety checker |
| tests/ | ~1,280 | 11 files, 62 test functions |
| tools/mutation_check.py | 129 | 19-mutant, two-layer mutation runner |
| examples/demo.py | 52 | Narrated stale-leader scenario |
| docs/design-decisions.md | 105 | Post-hoc decision record |
| README.md, pyproject.toml | 147, 9 | Docs, pytest config |

## Patterns
- Ports and adapters: `send`, `Storage`, `rng`, `on_apply` injected into RaftNode (node.py:49-64).
- Message-type dispatch via isinstance chain (node.py:154-167).
- Term handling centralised in `receive` (node.py:151), PreVote excepted.
- Frozen dataclasses for messages and commands (shareable across logs).
- Seeded RNG per node and per network for replayable histories (sim/cluster.py:45-48).

## Classification
Source: raft/. Test infrastructure: sim/, tests/faults.py, tests/helpers.py. Tests: tests/test_*.py. Tooling: tools/. Docs/examples: README.md, docs/, examples/.
