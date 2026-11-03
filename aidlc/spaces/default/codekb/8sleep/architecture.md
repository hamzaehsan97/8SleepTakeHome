# Architecture

## Architecture Analysis

### System Overview
A library (`raft/`) containing a pure, single-threaded Raft state machine, and a test world (`sim/`) that drives clusters of nodes on logical time. Nodes expose `tick()`, `receive(src, msg)` and `propose()`, and emit messages through an injected `send` callable (raft/node.py:1-11, 49-64). Durable state lives in an injected `Storage`.

### Architectural Style
Deterministic, event-driven state machine behind ports (send, storage, rng), driven by a discrete-event simulator. Not a networked service: no sockets, threads, clock or serialisation exist anywhere.

### Component Relationships
```mermaid
flowchart LR
  T[tests/*] --> C[sim.Cluster]
  T --> F[tests.faults]
  F --> C
  C --> N[sim.SimNetwork]
  C --> K[sim.InvariantChecker]
  C --> R[raft.RaftNode]
  R --> S[raft.Storage]
  R --> M[raft.messages]
  R --> SM[raft.KeyValueStore]
  N -- deliver --> R
  R -- send --> N
  MU[tools/mutation_check.py] -. mutates copy of .-> R
  MU -. runs .-> T
```
Text fallback: tests drive Cluster; Cluster owns SimNetwork, InvariantChecker and RaftNodes; RaftNode uses Storage, messages and KeyValueStore; the network delivers to nodes and nodes send back via the network; the mutation tool mutates a copy of node.py and runs the tests.

### Data Flow
Client command -> `Cluster.commit` -> leader `propose` -> log append -> AppendEntries via SimNetwork -> follower merge -> success reply -> leader `_advance_commit` -> `_apply_committed` -> `on_apply` records results; `InvariantChecker.is_committed` is how the harness decides a command is acknowledged (sim/cluster.py:204-205, 229).

### Key Design Decisions
- Logical time, node as pure state machine (D3/D4 in docs/design-decisions.md): reproducible seeds, no real concurrency tested.
- Crash = drop node, keep Storage (D5): persistence order is only documented, never interrupted.
- Reads go through the log (D9): linearizable, slow.
- PreVote/CheckQuorum off by default (D8).
- Safety asserted every tick by an external checker that reads node internals (D6).

### Improvement Opportunities
See code-quality-assessment.md (single place for findings).

## Interaction Diagrams

### Leader election (base, no PreVote)
```mermaid
sequenceDiagram
  participant A as Node A (follower)
  participant S as Storage A
  participant B as Node B
  participant C as Node C
  A->>A: tick() deadline reached (node.py:139)
  A->>S: save_hard_state(term+1, self) (node.py:200)
  A->>B: RequestVote(term, lastIdx, lastTerm)
  A->>C: RequestVote
  B->>B: receive: term newer -> become_follower (node.py:151)
  B->>B: log up-to-date and can_vote (node.py:228-233)
  B->>B: save_hard_state(term, A) (node.py:236)
  B-->>A: RequestVoteReply(granted)
  A->>A: votes >= quorum -> become_leader (node.py:248)
  A->>A: append no-op in own term (node.py:264)
  A->>B: AppendEntries (broadcast)
  A->>C: AppendEntries
```
Text fallback: candidate persists term+vote, requests votes; voters step up their term, check log freshness, persist the vote, reply; majority makes the candidate leader, which appends a no-op and broadcasts AppendEntries.

### Log replication and commit
```mermaid
sequenceDiagram
  participant Cl as Cluster client
  participant L as Leader
  participant F as Follower
  participant K as InvariantChecker
  Cl->>L: propose(cmd) (node.py:114)
  L->>L: storage.append(entry current term)
  L->>F: AppendEntries(prev, entries, leader_commit)
  F->>F: term check, prev consistency check (node.py:357-395)
  F->>F: merge, truncate only on conflict (node.py:401-408)
  F->>F: commit = min(leader_commit, last_new) (node.py:415)
  F-->>L: Reply(success, match_index)
  L->>L: match_index = max(..), advance_commit current-term only (node.py:430, 448)
  L->>L: apply to KeyValueStore, on_apply
  Cl->>K: is_committed(index, term)
```
Text fallback: leader appends and sends AppendEntries; follower checks the previous entry, merges without needless truncation, caps its commit index at the verified prefix and replies; the leader advances match_index and commits only current-term entries; the harness learns commitment from the checker.

### Rejection and backtracking
Follower reply carries conflict_index/conflict_term (node.py:376-395); leader jumps next_index using the last index of that term (node.py:435-446) and resends immediately.
