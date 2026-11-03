# toyraft

A from-scratch implementation of [Raft](https://raft.github.io/raft.pdf) in Python (standard library only; `pytest` for tests), plus a deterministic simulator for hurting it in ways that are hard to arrange with real processes.

I chose Raft over Paxos because I wanted to spend the day on *failure behaviour*, and Raft's decomposition (election / replication / safety) maps each failure mode to one specific rule I can test in isolation.

```
python -m pytest                  # 82 tests / 233 cases, ~11s, fully deterministic
python tools/mutation_check.py    # injects 19 classic Raft bugs; see "Do the tests catch bugs?"
python -m examples.demo           # narrated stale-leader-and-partition scenario
```

## What's implemented

**The algorithm (`raft/`, ~730 lines)**
- Leader election with randomised timeouts and the log up-to-date voting restriction (§5.2, §5.4.1)
- Log replication: consistency check, conflict resolution, and fast backtracking via a conflict term/index hint (§5.3)
- Commit rule: majority replication, **current-term entries only** (§5.4.2), with a no-op appended on election
- Crash recovery: `currentTerm`, `votedFor` and the log are durable; commit index and state machine are rebuilt
- Replicated key-value store as the state machine. Reads (`Get`) go through the log.

**Opt-in hardening** (off by default, so the base algorithm is exactly the paper's)
- `pre_vote`: a dry-run election round that cannot change anyone's term or vote (thesis §9.6)
- `check_quorum`: a leader that hears from no majority for an election timeout steps down (§6.2)

## What I deliberately left out

| Not done | Why / what it would take |
|---|---|
| Log compaction / snapshots | Biggest gap for real use. `Storage` is the only code that touches the log, so snapshots are local to it plus an `InstallSnapshot` RPC. |
| Membership changes | Orthogonal to the core safety argument; joint consensus is a large chunk on its own. |
| Client sessions / dedup | `Cluster.commit` is at-least-once. Exactly-once needs client IDs and a dedup table in the state machine. |
| Fast reads | Reads are linearizable but pay a full log round trip. ReadIndex or leader leases would fix that. |
| Real networking, real disk | The protocol is independent of both; see below. |

## Design

```
raft/   the algorithm. No threads, no sockets, no clock.
  node.py          RaftNode: tick() + receive() in, send() out
  storage.py       the durable state (term, vote, log)
  messages.py      frozen dataclasses
  statemachine.py  KV store
sim/    the test world
  network.py       delay / drop / duplicate / reorder / partition / one-way cuts
  cluster.py       lock-step driver: crash, restart, pause, commit, read
  invariants.py    Raft's safety properties, asserted on every tick
tests/  unit, scenario, directed (Figure 8), hardening, chaos, linearizability
tools/  mutation_check.py
docs/   design-decisions.md: the options weighed, what was chosen and why
```

**Time is logical and the node is a pure state machine.** A node never reads a clock or spawns a thread; it is advanced by `tick()` and `receive()`. A whole cluster therefore runs single-threaded and reproducibly: a failing chaos seed replays exactly, and there are no sleeps and no flaky tests. The cost is that it doesn't exercise real concurrency, serialisation or I/O. For a consensus algorithm, whose hard part is the protocol rather than the plumbing, I think that is the right trade.

**A crash is "drop the `RaftNode`, keep the `Storage`".** Volatile state vanishes as it would for real; the tests check that a restarted node can't double-vote, rebuilds its state machine from the log, and re-learns its commit index.

**Safety is checked on every tick, not just at the end.** `sim/invariants.py` asserts Election Safety, Log Matching, Leader Completeness, State Machine Safety and term monotonicity throughout every test. A bug that corrupts a log and heals before the test ends still fails. Liveness can only be tested with timeouts, so those tests use generous ones.

**Fault model.** Messages can be delayed, reordered, dropped and duplicated. Nodes can crash and restart, and can be *paused* (frozen, with messages buffered, then a burst delivered on resume: the way to meet a leader that doesn't know it was replaced). Partitions can be clean groups or **one-way** (a node that can talk but not listen).

## How I tested it

| Layer | What it's for |
|---|---|
| `test_node_unit.py` | One node driven by hand, pinning individual rules where implementations are *almost* right: vote persistence, the Figure 8 commit rule, the commit-index cap, not truncating on a stale duplicate `AppendEntries`, backtracking hints, PreVote semantics, election-timer policy. |
| `test_election.py`, `test_replication.py`, `test_failures.py` | Scenarios: leader crash, stale leader overwritten on heal, whole-cluster restart, minority partition, lossy network. |
| `test_figure8.py` | The paper's Figure 8 reproduced end to end on a real cluster by forcing elections and arranging message loss. |
| `test_hardening.py` | For each extension, a pair of tests: one pins how base Raft misbehaves, one shows the extension fixing it. Also pause and one-way partition scenarios. |
| `test_chaos.py` | 40 seeds x {base, hardened}: random crash / restart / partition / one-way cut / pause / write histories, then "repair everything and demand convergence". |
| `test_linearizable.py` | 25 seeds x {base, hardened}: a client under faults must always read exactly its latest acknowledged write. |

82 distinct tests; the case count (233) is inflated by seed parametrisation. The newer files `test_mutation_check.py` (the mutation tool's classification logic, with pytest stubbed), `test_invariants_negative.py` (a violating state for each safety property, so the checker is shown to reject bad states) and `test_storage.py` (durable state on its own) are not in the table above.

### Do the tests catch bugs?

`tools/mutation_check.py` copies the code, injects one classic bug at a time, and runs the suite in two layers: **unit** (`test_node_unit.py`) and **integration** (everything else, which is where the invariant checker is watching). Latest run:

| Injected bug | unit | integration |
|---|:-:|:-:|
| Commit old-term entries by counting replicas (Fig. 8) | caught | caught |
| Commit without a majority | caught | caught |
| Quorum off by one | caught | caught |
| Skip the log up-to-date check when voting | caught | caught |
| Compare log length before last term when voting | caught | - |
| Don't persist the vote | caught | caught |
| Truncate on every `AppendEntries` | caught | caught |
| Commit to own last index, not last verified entry | caught | - |
| Acknowledge more than was verified | caught | - |
| Accept `AppendEntries` from a stale term | caught | caught |
| `match_index` may move backwards | caught | - |
| Don't step down on a higher term | caught | caught |
| Identical election timeouts (no randomisation) | - | caught |
| Reset election timer on any higher term | caught | - |
| Pre-vote granted despite a live leader | caught | - |
| Pre-vote counts refusals as grants | caught | - |
| Pre-vote accepts replies from earlier rounds | caught | - |
| Pre-candidate bumps its term anyway | caught | caught |
| Check-quorum never steps the leader down | - | caught |

**19/19 caught, 0 survived. 8 are caught only by unit tests.** I read that last number as the honest limit of random testing: chaos plus an invariant checker finds *gross* violations, but subtle rules (vote ordering, the commit cap, `match_index` monotonicity) need a test written by someone who knows the rule exists. Figure 8 is the one case I upgraded to a directed integration test, because it's the best-known trap and a unit test alone only proves the arithmetic, not that the cluster stays correct.

History of this table, since it explains some of the tests: my first, ad-hoc mutation run used `pytest -x` and so couldn't say *which* layer caught what; it missed the `match_index` mutant (now covered), and later splitting the layers exposed "acknowledge more than was verified" as completely uncaught (now covered by a unit test).

## Known limitations

- **Base Raft pays for asymmetric failures; the extensions fix it.** An isolated node inflates its term and deposes a healthy leader on rejoin; a leader that can send but not receive wedges the cluster. Both are pinned in `test_hardening.py` for the base configuration and shown fixed with `pre_vote` + `check_quorum`. The linearizability test therefore only asks base Raft to survive faults that don't wedge it.
- **PreVote and CheckQuorum are off by default.** That keeps the base algorithm literal, but a production system would turn both on.
- **Reads are slow by design.** `Get` is committed through the log; correct and simple, not fast.
- **No flow control or pipelining.** Each `AppendEntries` carries at most `max_batch` entries and the leader waits for a reply before the next batch.
- **The disk is idealised.** Writes are atomic and instant. I don't model torn writes, fsync failures, or a crash between persisting and replying (the "persist before reply" rule is documented, and the mutation `don't persist the vote` shows it is tested, but a crash *at* that boundary is not injected).
- **Clocks tick in lock-step.** Nodes differ only in their random timeouts, not in clock rate or skew; `pause` is the only timing fault.
- **The checker trusts node internals.** It reads `commit_index` and logs directly; it does not check anything about the wire format, since messages are passed as objects, not bytes.
- **Chaos keeps a majority reachable.** The fault injector repairs the cluster if no majority could talk, so it doesn't explore permanent quorum loss (where the correct behaviour is simply to stall).

## How I worked with AI

I built this with Claude Code, partly through a structured workflow and partly in direct conversation.

**AI-DLC.** A decent chunk of the development ran through a fork of AWS's AI-DLC workflows: [hamzaehsan97/aidlc-workflows](https://github.com/hamzaehsan97/aidlc-workflows). It turns the coding assistant into a staged workflow with human approval gates and an audit trail, instead of free-form prompting. For this project the flow was: project context first, then design ideas generated by the model, then my design choices among those ideas, then implementation, then testing. The point of that ordering is that the model proposes and I choose *before* code exists, rather than reviewing code after the fact. One caveat on the record: `docs/design-decisions.md` was reconstructed afterwards, from the design discussion in a Claude Code session, once the implementation existed. It is not an AI-DLC engine record (no stage, approval gate or audit trail produced it), so it documents the decisions but is not evidence of when they were made.

**The direct Claude Code session.** The rest of the work, including the hardening pass, was with Claude Code that happened to fall into similar stages:

1. *Context.* I pasted the assignment and asked the model what the interviewers actually want and what the simplest version that still scores well would be. It restated the grading signals (reasoning over volume, failure-mode tests, AI-usage honesty) and proposed a minimal scope.
2. *Design options.* It recommended Raft over Paxos, a simulated network on logical time, and a short list of what to include and skip, with a test plan.
3. *My direction.* I chose Python and asked for the strongest submission that was still reasonable for one day. I set the goal and constraints; the model made most of the detailed design calls inside them.
4. *Implementation.* It wrote the node, simulator, invariant checker and first tests.
5. *Critique, then a second pass.* I reviewed the design choices and say where better ones existed. I found real problems (an untested timer deviation, an unproven claim about what the checker catches, a harness that was too kind). I then asked it to make the changes that would most improve the submission, and that produced PreVote, CheckQuorum, harsher faults, the Figure 8 scenario and the mutation tool.
6. *Verification.* The checks listed below.

**What I delegated.** The first full rough draft of everything after the design choices were confirmed: the node, the simulator, the invariant checker, and the tests. Later I reviewed the design again and then asked it to make the changes that would most strengthen the submission (PreVote, CheckQuorum, harsher fault models, a client-visible correctness test, a mutation tool).

**What I decided.** I made the design decisions; `docs/design-decisions.md` lists each one with the options weighed and who proposed it. Among them: Raft over Paxos, Python, a simulated network on logical time instead of real sockets, which extensions were worth adding, and what to leave out (snapshots, membership changes). 

**How I checked the work rather than trusting it.**
- Ran the suite across several `PYTHONHASHSEED` values to make sure nothing depends on dict or set ordering.
- Injected bugs on purpose (`tools/mutation_check.py`, 19 of them) to see whether the tests notice. This was the most useful check, because green tests only tell you the code agrees with the tests.
- Whenever a new test failed, dumped the cluster state at the failure and looked at it before touching any code.

**Where the tool got it wrong, and how it was caught.**
- *Tests that couldn't fail for the right reason.* In the stale-leader test, `wait_for_leader()` returned instantly because the isolated old leader still believed it was in charge. Another test used `converged()` right after healing a partition, which is trivially true because the logs already match. Both showed up as assertions that should have been unreachable. Fix: wait on the actual condition.
- *A client bug that looked like a Raft bug.* The linearizability test timed out on 20 seeds. Dumping state showed a healthy majority with a leader, while my test client sat waiting on a stale minority leader. Real clients have per-request timeouts, so I gave the harness one.
- *A real Raft weakness that looked like a test bug.* Seven failures remained after that. I printed the network cuts for each seed before changing anything: all seven were a leader that can send but not receive, a known wedge in base Raft. I pinned it in `test_hardening.py` and scoped that test accordingly instead of hiding it.
- *Over-claiming from a weak experiment.* The first mutation run used `pytest -x` and reported "caught", but couldn't say which layer did the catching. Splitting unit and integration layers showed 8 bugs that only the unit tests catch, and one that nothing caught ("acknowledge more than was verified"), which is now tested.
- *A deviation I didn't notice at first.* The initial node reset its election timer on any higher-term message, which differs from the paper. It surfaced when I asked the model to critique its own design; it's now fixed and has a test.
- *Smaller things.* `mypy` flagged a `NamedTuple` field called `index` shadowing `tuple.index`; my first unit-test helper built log entries the state machine couldn't apply.

**What I'd still want to be able to defend live:** the Figure 8 commit rule (`_advance_commit` and `test_figure8.py`), the conflict-hint backtracking in `_on_append_entries_reply`, and why PreVote requires "no live leader" before granting.
