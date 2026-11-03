"""Does the test suite actually catch Raft bugs?

Injects one classic bug at a time into a *copy* of the code, runs the suite in
two separate layers, and reports which layer noticed:

  unit         tests/test_node_unit.py: one node driven by hand
  integration  everything else: clusters, faults, invariant checker, chaos

A bug caught only by "unit" means the cluster-level tests (and the safety
checker watching them) would have let it through. That is worth knowing, since
unit tests only cover bugs somebody thought of in advance.

    python tools/mutation_check.py          # exits non-zero if a mutant survives
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NODE = "raft/node.py"

# (description, old text, new text). Each `old` must occur exactly once.
MUTANTS = [
    ("commit old-term entries by counting replicas (Fig. 8)",
     "if self.storage.term_at(n) != self.current_term:\n                break",
     "if False:\n                break"),
    ("commit without a majority",
     "if replicas >= self.quorum:", "if replicas >= 1:"),
    ("quorum off by one",
     "return (len(self.peers) + 1) // 2 + 1", "return (len(self.peers) + 1) // 2"),
    ("skip the log up-to-date check when voting",
     "and can_vote\n            and self._log_is_up_to_date(msg.last_log_term, msg.last_log_index)",
     "and can_vote"),
    ("compare log length before last term when voting",
     "return (last_term, last_index) >= (\n            self.storage.last_term,\n            self.storage.last_index,\n        )",
     "return (last_index, last_term) >= (self.storage.last_index, self.storage.last_term)"),
    ("don't persist the vote",
     "self.storage.save_hard_state(self.current_term, src)", "pass"),
    ("truncate on every AppendEntries",
     "                if store.term_at(index) == entry.term:\n                    continue\n", ""),
    ("commit to own last index, not last verified entry",
     "min(msg.leader_commit, last_new)", "min(msg.leader_commit, store.last_index)"),
    ("acknowledge more than was verified",
     "AppendEntriesReply(self.current_term, True, match_index=last_new)",
     "AppendEntriesReply(self.current_term, True, match_index=store.last_index)"),
    ("accept AppendEntries from a stale term",
     "        if msg.term < self.current_term:\n            self._send(src, AppendEntriesReply(self.current_term, success=False))\n            return\n",
     ""),
    ("match_index may move backwards",
     "self.match_index[src] = max(self.match_index[src], msg.match_index)",
     "self.match_index[src] = msg.match_index"),
    ("don't step down on a higher term",
     "if not isinstance(msg, PreVote) and msg.term > self.current_term:\n            self._become_follower(msg.term)",
     "if False:\n            pass"),
    ("identical election timeouts (no randomisation)",
     "self._election_deadline = self._rng.randint(*self._election_timeout)",
     "self._election_deadline = self._election_timeout[0]"),
    ("reset election timer on any higher term",
     "        if not was_follower:\n            self._trace(\"stepping down to follower\")",
     "        if True:\n            self._trace(\"stepping down to follower\")"),
    ("pre-vote granted despite a live leader",
     "            and not self._leader_seems_alive()\n", ""),
    ("pre-vote counts refusals as grants",
     "        if msg.granted:\n            self._prevotes.add(src)", "        if True:\n            self._prevotes.add(src)"),
    ("pre-vote accepts replies from earlier rounds",
     "        if msg.proposed_term != self.current_term + 1:\n            return  # reply to an earlier round\n", ""),
    ("pre-candidate bumps its term anyway",
     "        self.role = Role.PRE_CANDIDATE\n        self.leader_id = None",
     "        self.role = Role.PRE_CANDIDATE\n        self.storage.save_hard_state(self.current_term + 1, self.id)\n        self.leader_id = None"),
    ("check-quorum never steps the leader down",
     "        if active >= self.quorum:\n            return True\n",
     "        if True:\n            return True\n"),
]


# Outcomes of one pytest layer run.
FAILED = "failed"  # pytest exit 1: a test failed. The only outcome that counts as "caught".
PASSED = "passed"  # pytest exit 0: nothing noticed the change.
ERROR = "error"    # anything else: syntax/import/collection error, nothing collected, timeout.

UNIT_ARGS = ["tests/test_node_unit.py"]
INTEGRATION_ARGS = ["--ignore=tests/test_node_unit.py"]


def run_layer(workdir: Path, args: list[str]) -> str:
    """Run one layer and classify the result as FAILED, PASSED or ERROR.

    A mutant that breaks the import, or a run that collects nothing or hangs,
    has not been *detected* by a test: it is reported as ERROR, not as caught.
    """
    try:
        r = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", *args],
            cwd=workdir, capture_output=True, timeout=300,
        )
    except subprocess.TimeoutExpired:
        return ERROR
    if r.returncode == 1:
        return FAILED
    if r.returncode == 0:
        return PASSED
    return ERROR


def baseline() -> bool:
    """Both layers must pass on the unmutated code, or the results mean nothing."""
    ok = True
    for label, args in (("unit", UNIT_ARGS), ("integration", INTEGRATION_ARGS)):
        outcome = run_layer(ROOT, args)
        if outcome != PASSED:
            print(f"baseline {label} layer did not pass on unmutated code ({outcome})")
            ok = False
    return ok


def check(index: int, mutant: tuple[str, str, str]) -> tuple[str, str, str]:
    name, old, new = mutant
    with tempfile.TemporaryDirectory(prefix=f"mut{index}_") as tmp:
        work = Path(tmp)
        for item in ("raft", "sim", "tests", "pyproject.toml"):
            src = ROOT / item
            if src.is_dir():
                shutil.copytree(src, work / item, ignore=shutil.ignore_patterns("__pycache__"))
            else:
                shutil.copy(src, work / item)
        text = (work / NODE).read_text()
        if text.count(old) != 1:
            raise RuntimeError(f"mutant {name!r}: pattern not found exactly once")
        (work / NODE).write_text(text.replace(old, new))
        unit = run_layer(work, UNIT_ARGS)
        integration = run_layer(work, INTEGRATION_ARGS)
    return name, unit, integration


def _label(outcome: str) -> str:
    return {FAILED: "caught", PASSED: "  -   ", ERROR: "ERROR "}[outcome]


def main() -> int:
    if not baseline():
        print("Refusing to run mutants: fix the unmutated suite first.")
        return 2

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda a: check(*a), enumerate(MUTANTS)))

    width = max(len(n) for n, _, _ in results)
    print(f"{'mutant':<{width}}  unit    integration")
    for name, unit, integ in results:
        print(f"{name:<{width}}  {_label(unit)}  {_label(integ)}")

    caught = [n for n, u, i in results if FAILED in (u, i)]
    survivors = [n for n, u, i in results if u == PASSED and i == PASSED]
    errors = [n for n, u, i in results if FAILED not in (u, i) and ERROR in (u, i)]
    unit_only = [n for n, u, i in results if u == FAILED and i != FAILED]
    print(f"\n{len(caught)}/{len(results)} caught; "
          f"{len(unit_only)} caught only by unit tests; {len(survivors)} survived; "
          f"{len(errors)} errored (not counted as caught)")
    for name in errors:
        print(f"  error: {name}")
    if survivors:
        return 1
    return 3 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
