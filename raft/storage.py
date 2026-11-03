"""The part of a node that must survive a crash.

Raft only requires three things to be durable: ``current_term``, ``voted_for``
and the log. Everything else (commit index, role, the state machine) is
rebuilt after a restart.

In this toy the "disk" is a Python object that outlives the node instance, so
a crash is modelled as "throw the RaftNode away, keep the Storage". Every
mutation below is a point where a real implementation would have to fsync
*before* replying to anyone; keeping them as explicit methods (rather than
poking attributes) makes those points easy to see and to audit.
"""

from __future__ import annotations

from typing import Iterable, Optional

from raft.messages import LogEntry, NodeId


class Storage:
    def __init__(
        self,
        term: int = 0,
        voted_for: Optional[NodeId] = None,
        log: Iterable[LogEntry] = (),
    ) -> None:
        self._term = term
        self._voted_for = voted_for
        self._log: list[LogEntry] = list(log)

    # -- hard state ---------------------------------------------------------

    @property
    def current_term(self) -> int:
        return self._term

    @property
    def voted_for(self) -> Optional[NodeId]:
        return self._voted_for

    def save_hard_state(self, term: int, voted_for: Optional[NodeId]) -> None:
        # Term and vote are written together: persisting a new term without
        # clearing the old vote (or vice versa) would allow a double vote.
        assert term >= self._term, "terms never go backwards"
        self._term = term
        self._voted_for = voted_for

    # -- log (1-indexed, like the paper; index 0 is a virtual empty entry) --

    @property
    def last_index(self) -> int:
        return len(self._log)

    @property
    def last_term(self) -> int:
        return self._log[-1].term if self._log else 0

    def entry(self, index: int) -> LogEntry:
        return self._log[index - 1]

    def term_at(self, index: int) -> int:
        return 0 if index == 0 else self._log[index - 1].term

    def entries_from(self, index: int, limit: int) -> tuple[LogEntry, ...]:
        return tuple(self._log[index - 1 : index - 1 + limit])

    def append(self, entries: Iterable[LogEntry]) -> None:
        self._log.extend(entries)

    def truncate_from(self, index: int) -> None:
        """Delete ``index`` and everything after it."""
        del self._log[index - 1 :]

    def first_index_of_term(self, term: int) -> int:
        for i, e in enumerate(self._log, start=1):
            if e.term == term:
                return i
        return 0

    def last_index_of_term(self, term: int) -> int:
        for i in range(len(self._log), 0, -1):
            if self._log[i - 1].term == term:
                return i
        return 0
