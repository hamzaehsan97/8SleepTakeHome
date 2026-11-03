"""Wire messages and log entries.

Everything is a frozen dataclass so messages can be duplicated or reordered by
the simulated network without anyone being able to mutate a message another
node is still holding. The sender is not part of the message; the transport
supplies it (as a real RPC layer would).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

NodeId = int


@dataclass(frozen=True)
class LogEntry:
    term: int
    # ``None`` marks a no-op, which a new leader appends to commit entries
    # left over from earlier terms (see RaftNode._become_leader).
    command: Any = None


@dataclass(frozen=True)
class RequestVote:
    term: int
    last_log_index: int
    last_log_term: int


@dataclass(frozen=True)
class RequestVoteReply:
    term: int
    granted: bool


@dataclass(frozen=True)
class PreVote:
    """A dry run of an election (Raft thesis §9.6).

    ``term`` is the term the sender *would* campaign in. Nobody changes their
    term or vote because of one, which is the point: a node that can't win
    can't disturb anyone either.
    """

    term: int
    last_log_index: int
    last_log_term: int


@dataclass(frozen=True)
class PreVoteReply:
    term: int  # the responder's real current term
    granted: bool
    proposed_term: int  # echoes PreVote.term so late replies can be matched


@dataclass(frozen=True)
class AppendEntries:
    term: int
    prev_log_index: int
    prev_log_term: int
    entries: tuple[LogEntry, ...]
    leader_commit: int


@dataclass(frozen=True)
class AppendEntriesReply:
    term: int
    success: bool
    # On success: the highest log index the follower now shares with the leader.
    match_index: int = 0
    # On failure: a hint that lets the leader skip back over a whole
    # conflicting term instead of probing one index at a time.
    conflict_index: int = 0
    conflict_term: int = 0
