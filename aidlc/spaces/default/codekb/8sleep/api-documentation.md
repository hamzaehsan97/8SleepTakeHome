# API Documentation

No external (network/HTTP/RPC) API exists. All surfaces are in-process Python.

## Node API (raft/node.py)
| Member | Contract |
|---|---|
| `RaftNode(node_id, peers, storage, send, rng, *, election_timeout=(15,30), heartbeat_interval=5, max_batch=32, state_machine=None, pre_vote=False, check_quorum=False, on_apply=None)` | node.py:49-64 |
| `propose(command) -> (index, term) or None` | Leader only; acceptance is not commitment (node.py:114-128) |
| `tick()` | One logical time unit (node.py:130) |
| `receive(src, msg)` | Deliver a message; raises TypeError on unknown type (node.py:145-167) |
| `current_term`, `quorum` | Read-only properties |

## Wire messages (raft/messages.py)
RequestVote, RequestVoteReply, PreVote, PreVoteReply(proposed_term), AppendEntries(prev_log_index, prev_log_term, entries, leader_commit), AppendEntriesReply(success, match_index, conflict_index, conflict_term). Sender id is supplied by the transport. No serialization.

## Storage (raft/storage.py)
`current_term`, `voted_for`, `save_hard_state(term, voted_for)`, `last_index`, `last_term`, `entry`, `term_at`, `entries_from`, `append`, `truncate_from`, `first_index_of_term`, `last_index_of_term`.

## State machine (raft/statemachine.py)
Commands `Set(key, value)`, `Delete(key)`, `Get(key)`; `KeyValueStore.apply/get/snapshot`.

## Harness API (internal to tests)
- `Cluster`: `crash`, `restart`, `pause`, `resume`, `tick`, `run_until`, `wait_for_leader`, `wait_until_converged`, `propose`, `commit` (at-least-once, retries), `read` (Get via log), `is_committed`, `has_quorum`.
- `SimNetwork`: `partition`, `isolate`, `cut(src,dst)`, `heal`, `can_reach`, drop/dup rates, delay range.
- `InvariantChecker.check(nodes)`.
