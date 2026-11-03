# Code Quality Assessment

Method: static reading only. Nothing was executed, so README figures (62 tests / 212 cases, 19/19 mutants, mypy) are unverified here; only the 62 test-function count was confirmed by grep. Severity: C = clear defect, S = suspected, O = observation.

## 1. Raft safety and liveness (raft/node.py)
Read line by line against the extended paper. **No clear safety defect found.** Verified correct:
- Term bump and self-vote persisted together before RequestVote leaves (node.py:200); vote persisted before reply (236); voted_for cleared on a newer term (181).
- Up-to-date comparison by (last_term, last_index) (222-225).
- Commit only current-term entries by counting (448-458); no-op on election (264); next_index initialised before the no-op (255).
- Merge truncates only on a real conflict (401-408); follower commit capped at verified prefix (413-415); reply claims only verified prefix (419).
- Stale replies ignored (244, 423); match_index monotone (430); conflict hint never goes below match_index+1 (443).

Items to weigh (none a clear bug):
- O1 node.py:363: a same-term second leader raises AssertionError inside `receive`. Right for a test harness; in a real node it would crash on a protocol-impossible input instead of ignoring it.
- O2 storage.py:45: the monotonic-term guard is an `assert` (removed by `python -O`); also nothing guards `truncate_from` below the commit index (storage.py:71, node.py:406), so a Leader Completeness bug would only surface via the external checker.
- S3 (liveness, by design, documented README:105): in the default config a leader that can send but cannot receive wedges the cluster forever (pinned at tests/test_hardening.py:103-111). The default is intentionally "paper Raft", but the defaults ship the weaker behaviour.
- S4 (hypothesis, unverified): CheckQuorum window equals `election_timeout[0]` (node.py:323), 15 ticks by default, with 5-tick heartbeats; round-trip delays approaching the window could cause spurious step-downs. Chaos uses max_delay up to 6 and is not reported failing.
- O5 Client semantics: no dedup, `Cluster.commit` is at-least-once (sim/cluster.py:207-233); acknowledged in README:32.

## 2. Gaps between tests and the failure modes that matter
| Failure mode | Where covered | Gap |
|---|---|---|
| Partitions (clean and one-way) | test_failures.py:9, :72; test_hardening.py:78-125; chaos | Only 5-node chaos; sizes 2 and 4 never exercised (test_election.py:7 uses 1,3,5) |
| Crash / restart | test_failures.py:39, :52; test_replication.py:38; chaos | No crash at the persist-then-reply boundary (README:109); crashed nodes' disks are not checked by the checker (it takes `live_nodes`, cluster.py:169) |
| Loss / duplication / reordering | network drop/dup/delay; test_failures.py:119-129; chaos | Delays never exceed 8 ticks in tests read (below election timeout), so very late stale-term messages arrive only via `pause` buffers (cluster.py:91-107); no directed duplicate-RequestVote or late-vote-reply cluster test |
| Stale leaders | test_failures.py:9; test_hardening.py:130, :170 | Good |
| Log divergence | test_failures.py:9; test_figure8.py; unit tests | Figure 8 is driven through private `_start_election` (test_figure8.py:20-26), coupling the test to internals |
| Persistence | unit `test_vote_survives_restart`; whole-cluster restart | `Storage` has no tests of its own; no lost-suffix, torn-write or term-persistence-specific test (term only guarded by the checker's monotonicity rule, invariants.py:48-54) |
| Client-visible correctness | test_linearizable.py | See S6 |

- S6 test_linearizable.py:9-10 says duplicated retries are harmless because they write the same value. That holds only if no later write intervenes: `commit` abandons an attempt after 150 ticks (cluster.py:207, 226) yet that entry may stay in a leader's log; if it commits after a later acknowledged write, a later read returns the older value and the test would fail for a client-semantics reason, not a Raft one. Also single sequential client and one register only (test_linearizable.py:5-11), so it is not a concurrent-history linearizability check.
- O7 Checker blind spots (sim/invariants.py): Leader Append-Only (a Figure 3 property) is not checked; state-machine agreement is compared on logs, not applied results, except at convergence (cluster.py:146-160). The checker itself has no negative tests (no test constructs a violation and expects `InvariantViolation`; the only evidence is the mutation tool). Its checks are O(n^2 x log) per tick (invariants.py:93-108).
- O8 Chaos (tests/test_chaos.py) uses one key and only `Set`, `propose` is fire-and-forget, and the injector auto-repairs whenever no majority can talk (tests/faults.py:47-48), so permanent quorum loss is only covered by test_election.py:33.
- O9 Unit tests (test_node_unit.py) read private state and methods directly (`_advance_commit`, `_start_election`, `_ticks_since_heard`, e.g. lines 141, 117, 206) and hard-code the default timeout 15 (line 241); they pin rules well but break on refactors.

## 3. Mutation-check tooling (tools/mutation_check.py)
- S10 `run_layer` (85-91) calls any non-zero pytest exit "caught": a syntax or import error (rc 2), a collection error, or no tests collected (rc 5) all count as detection, and a timeout also counts (89). There is no unmutated baseline run; if the suite were already red or broken, all 19 mutants would be reported caught.
- O11 All 19 mutants target raft/node.py only (line 26); none touch storage.py, statemachine.py (e.g. Get bypassing the log), or the invariant checker. Plausible missing mutants: not clearing voted_for on a newer term (node.py:181), skipping the leader no-op (264), applying before commit.
- O12 Mutants are exact-text replacements with an assert that each pattern occurs once (105): a refactor of node.py breaks the tool loudly (good) but couples it to formatting.
- O13 Runs 4 workers x two pytest invocations x up to 300s each; not wired to CI (none exists) and not mentioned in pyproject.
- Positive: layered unit vs integration reporting is a genuinely useful design, and the exit code reflects survivors (125).

## 4. Tooling and hygiene
No CI, no linter/formatter config, no mypy config despite README:136, pytest not declared as a dependency (pyproject.toml), no coverage measurement. Code itself is clean, typed, and heavily commented with paper references.

## 5. README and design record
- Trade-offs are well covered: logical-time purity vs real I/O (README:52), crash model (54), per-tick safety (56), fault model (58), limitations (103-112), omissions table (26-34).
- AI-tools note (README:114-147) is specific and candid: what was delegated, what the author decided, how work was verified, six concrete cases where the tool was wrong.
- Omissions / inconsistencies:
  - O14 README:131 says the author decided the logical-time simulated network and which extensions to add, while docs/design-decisions.md:16 and :21 (D4, D8) credit the model.
  - O15 README:118 describes AI-DLC with the model proposing and the author choosing before code exists, while docs/design-decisions.md:3-7 says that record was reconstructed after the implementation and is not an AI-DLC record. A reviewer may read this as overstating the process.
  - O16 docs/design-decisions.md is not listed in the README layout (README:36-50).
  - O17 Verification claims (mypy, multiple PYTHONHASHSEED runs, README:134-137) cannot be reproduced from the repo: no config, script or recorded output.
  - O18 No statement of which parts are AI-written line-for-line versus rewritten by the author, and no mention of the `.claude`/AI-DLC artifacts as part of the submission.
  - README:15 "~730 lines" matches (729 lines in raft/); README:99 "8 caught only by unit" matches the table.

## 6. Overall
Strong design clarity and failure-oriented testing for the scope. The weakest evidence is not the algorithm but the tooling's self-checking (mutation exit-code semantics, unchecked checker) and a few README/design-record inconsistencies. Candidate fixes for the reader to hand back: S10 (baseline + return-code check), O17 (add mypy config or drop the claim), O14/O15/O16 (align docs), S6 (guard or reword the linearizability claim), O7 (negative tests for the checker), pytest declaration in pyproject.toml.
