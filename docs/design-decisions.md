# Design decisions

> **Provenance.** Reconstructed on 2026-11-02 from the design discussion in a Claude
> Code session, *after* the implementation existed. It records options that were
> genuinely weighed and who made each call, but it was not written before the code and
> it is **not** an AI-DLC engine record (no stage, approval gate or audit trail produced
> it). "Model" below means Claude Code; "Author" means the person submitting this.

Each entry: the options, what was chosen, why, and what it costs.

| # | Decision | Chosen | Rejected | Called by |
|---|---|---|---|---|
| D1 | Algorithm | Raft | Single-decree or Multi-Paxos |
| D2 | Language | Python | Go | Author |
| D3 | Node model | Pure state machine: `tick()`, `receive()`, `send` callback | Threads and sockets; asyncio | Model |
| D4 | Network and time | In-process simulated network on logical time, seeded RNG | Real TCP with wall-clock timers | Author |
| D5 | Durability | A `Storage` object that outlives the node; crash = discard the node | Real files; in-memory state only | Model |
| D6 | Safety checking | Invariants asserted on every tick | End-state assertions only | Model |
| D7 | Scope | Election, replication, commit rule, crash recovery, KV store | Snapshots, membership change |  |
| D8 | Hardening | PreVote and CheckQuorum, **off by default** | Always on; omit | Author, after a design review |
| D9 | Reads | `Get` committed through the log | Serve from leader state; ReadIndex | Model |
| D10 | Verification | Layered tests plus a mutation tool | Example tests only | Model, after a design review |

## D1: Raft over Paxos

Failure behaviour was the goal, and Raft splits the problem (election, replication,
safety) so each failure mode maps to one rule that can be tested in isolation. Paxos is
more flexible but harder to turn into a replicated log and to explain live.
*Cost:* less to say about the Paxos family; the panel may ask how it compares.

## D2: Python

Fastest to write and test; `pytest` is enough tooling. *Cost:* the project does not
exercise real concurrency, and a language with stronger static types would catch more
at compile time. `mypy` was added later to recover some of that.

## D3: A node is a pure state machine

No clock reads, no threads. A cluster therefore runs single-threaded and a failing
scenario replays exactly from its seed. *Cost:* serialisation, real I/O and true
concurrency are not tested; messages are passed as objects, not bytes.

## D4: Simulated network on logical time

Delay, drop, duplicate, reorder and partition (clean groups and one-way cuts) are
available per message, driven by one seeded RNG. A node can also be paused and have its
messages delivered in a burst on resume. *Cost:* every node's clock ticks in lock-step;
only random timeouts differ between nodes.

## D5: Crash means "drop the node, keep the Storage"

Volatile state (role, commit index, state machine) vanishes as in a real crash. Every
durable mutation is an explicit `Storage` method, which marks where a real system would
fsync before replying. *Cost:* writes are atomic and instant; a crash between persisting
and replying is not injected.

## D6: Check safety on every tick

Election Safety, Log Matching, Leader Completeness, State Machine Safety and term
monotonicity are asserted after every tick of every cluster test, so transient
corruption that heals before the test ends still fails. *Cost:* the checker reads node
internals directly, and it can only see violations, not unfairness or slowness.

## D7: What was left out

Snapshots and membership changes are orthogonal to the core safety argument and large on
their own. Client sessions (exactly-once) are also left out; `Cluster.commit` is
at-least-once. *Why it matters:* the brief says a small thing done well beats a big thing
half-done.

## D8: Hardening is opt-in

A design review found two weaknesses in the base algorithm: an isolated node's inflated
term can depose a healthy leader, and a leader that cannot hear replies wedges the
cluster. PreVote and CheckQuorum fix these. They are off by default so the base is
literally the paper's algorithm, and each has a pair of tests: one pinning the base
misbehaviour, one showing the fix.

## D9: Reads go through the log

Simple and obviously linearizable: a deposed leader cannot commit a `Get`, so it cannot
answer one. *Cost:* every read pays a full replication round trip. ReadIndex or leader
leases would be the optimisation.

## D10: Layered verification

Unit tests per subtle rule, scenario tests, a hand-built Figure 8 scenario, random fault
injection over 40 seeds in two configurations, and a client-visible check that a
sequential client always reads its latest acknowledged write. A mutation tool injects 19
classic bugs and reports whether the unit layer, the integration layer, or both catch
each one.

## Decisions changed after review

- **Election timer.** The first version reset it on any higher-term message, which
  deviates from the paper. Changed so a follower resets only on a valid
  `AppendEntries` or a granted vote; covered by a unit test.
- **Mutation analysis.** The first run used `pytest -x` and could not say which layer
  caught a bug. Replaced by the layered tool, which exposed one bug nothing caught and
  eight that only unit tests catch.

## Known gaps carried forward

No snapshots, no membership changes, idealised disk, lock-step clocks, and a fault
injector that repairs the cluster whenever no majority could communicate.
