# Component Inventory

## RaftNode
raft/node.py. Roles FOLLOWER/PRE_CANDIDATE/CANDIDATE/LEADER; election, PreVote, CheckQuorum, replication, commit/apply. Depends on Storage, Messages, KeyValueStore.

## Storage
raft/storage.py. Durable term, vote, log; explicit mutation methods mark fsync points. In-memory object standing in for disk.

## Messages
raft/messages.py. Frozen dataclasses for six RPC messages and LogEntry (command None = no-op).

## KeyValueStore
raft/statemachine.py. Deterministic dict store; Set/Delete/Get commands.

## SimNetwork
sim/network.py. Heap-queued delivery with random delay, drop, duplicate; group partitions and one-way cuts checked at send and delivery.

## Cluster
sim/cluster.py. Lock-step driver; owns nodes, storages, per-node RNGs; crash/restart/pause/resume; client commit/read helpers. Depends on RaftNode, SimNetwork, InvariantChecker.

## InvariantChecker
sim/invariants.py. Checks term monotonicity, election safety, state-machine safety, leader completeness, log matching, applied <= commit each tick.

## FaultInjector
tests/faults.py (and tests/helpers.py node factory). Random fault menu (crash, restart, partition, one_way, pause, resume, heal) with auto-repair when no majority can talk.

## TestSuite
tests/test_*.py. Unit (test_node_unit), scenario (election, replication, failures), directed Figure 8, hardening pairs, chaos (40 seeds x 2 configs), linearizability (25 seeds x 2 configs).

## MutationCheck
tools/mutation_check.py. Copies raft/sim/tests, applies one of 19 text mutants to node.py, runs unit and integration layers, reports caught/survived.

## Demo
examples/demo.py. Narrated stale-leader-and-heal scenario.
