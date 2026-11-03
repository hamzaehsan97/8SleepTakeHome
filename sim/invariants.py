"""Safety properties from Figure 3 of the Raft paper, checked on every tick.

Liveness ("a leader is eventually elected") can only be tested with timeouts,
but *safety* can be asserted continuously, and that is much stronger than
checking end states: a bug that corrupts a log and then happens to heal itself
before the test finishes would still be caught here.
"""

from __future__ import annotations

from typing import Iterable

from raft.messages import LogEntry, NodeId
from raft.node import RaftNode, Role


class InvariantViolation(AssertionError):
    pass


class InvariantChecker:
    def __init__(self) -> None:
        # term -> the only node that has ever been leader in that term
        self.leaders_by_term: dict[int, NodeId] = {}
        # index -> the entry that was committed there. Grows as nodes commit.
        self.committed: dict[int, LogEntry] = {}
        self._last_term: dict[NodeId, int] = {}

    def is_committed(self, index: int, term: int) -> bool:
        entry = self.committed.get(index)
        return entry is not None and entry.term == term

    def check(self, nodes: Iterable[RaftNode]) -> None:
        nodes = list(nodes)
        for node in nodes:
            self._terms_never_decrease(node)
            self._election_safety(node)
            self._state_machine_safety(node)
            if node.last_applied > node.commit_index:
                raise InvariantViolation(
                    f"node {node.id} applied {node.last_applied} > commit {node.commit_index}"
                )
        for node in nodes:
            self._leader_completeness(node)
        self._log_matching(nodes)

    # Terms are durable, so this must hold even across crash and restart.
    def _terms_never_decrease(self, node: RaftNode) -> None:
        previous = self._last_term.get(node.id, 0)
        if node.current_term < previous:
            raise InvariantViolation(
                f"node {node.id} term went backwards: {previous} -> {node.current_term}"
            )
        self._last_term[node.id] = node.current_term

    # At most one leader per term.
    def _election_safety(self, node: RaftNode) -> None:
        if node.role is not Role.LEADER:
            return
        first = self.leaders_by_term.setdefault(node.current_term, node.id)
        if first != node.id:
            raise InvariantViolation(
                f"two leaders in term {node.current_term}: {first} and {node.id}"
            )

    # Nobody ever commits something different at the same index.
    def _state_machine_safety(self, node: RaftNode) -> None:
        for index in range(1, node.commit_index + 1):
            entry = node.storage.entry(index)
            known = self.committed.setdefault(index, entry)
            if known != entry:
                raise InvariantViolation(
                    f"index {index} committed as {known} but node {node.id} "
                    f"committed {entry}"
                )

    # A leader holds every entry committed in its term or earlier. (A stale
    # leader from an older term legitimately lacks later commits.)
    def _leader_completeness(self, node: RaftNode) -> None:
        if node.role is not Role.LEADER:
            return
        for index, entry in self.committed.items():
            if entry.term > node.current_term:
                continue
            if index > node.storage.last_index or node.storage.entry(index) != entry:
                raise InvariantViolation(
                    f"leader {node.id} (term {node.current_term}) is missing "
                    f"committed entry {index}: {entry}"
                )

    # If two logs agree on (index, term) they agree on everything before it.
    # Checked inductively: each matching position must follow a matching one.
    def _log_matching(self, nodes: list[RaftNode]) -> None:
        for i, a in enumerate(nodes):
            for b in nodes[i + 1 :]:
                shared = min(a.storage.last_index, b.storage.last_index)
                prev_matched = True
                for index in range(1, shared + 1):
                    ea, eb = a.storage.entry(index), b.storage.entry(index)
                    if ea.term != eb.term:
                        prev_matched = False
                        continue
                    if ea != eb or (index > 1 and not prev_matched):
                        raise InvariantViolation(
                            f"logs of {a.id} and {b.id} diverge at index {index} "
                            f"despite equal terms"
                        )
                    prev_matched = True
