# Business Overview

## Purpose
toyraft (README.md:1-5) is a take-home submission: a from-scratch Raft consensus implementation in Python with a deterministic simulator and a failure-oriented test suite. There is no product, user base or deployment; the "customer" is a reviewer judging reasoning, testability and honesty (including a README note on AI tooling).

## Key Functionality
- Leader election with randomised timeouts and log up-to-date restriction (raft/node.py:171-249).
- Log replication with fast conflict backtracking and the current-term-only commit rule (node.py:336-468).
- Crash recovery by retaining `Storage` and discarding the node (raft/storage.py, sim/cluster.py:81-89).
- Opt-in PreVote and CheckQuorum (node.py:268-332).
- Replicated KV store (Set/Delete/Get; reads go through the log) (raft/statemachine.py).
- Simulator with delay/drop/duplicate/reorder, partitions, one-way cuts, pause and crash (sim/).
- Per-tick safety invariants and a 19-mutant mutation tool (sim/invariants.py, tools/mutation_check.py).

## Out of Scope (stated by the author, README.md:26-34)
Snapshots, membership change, client sessions/dedup, fast reads, real networking and disk.

## Documentation Provenance
README.md:114-147 is the AI-usage note. docs/design-decisions.md states it was reconstructed after the code existed (lines 3-7).

See code-quality-assessment.md for the evaluation against the brief.
