"""A small, readable implementation of the Raft consensus algorithm.

The core package knows nothing about sockets or wall-clock time: a node is a
state machine driven by two inputs, ``tick()`` and ``receive()``, and it talks
to the world through a single ``send`` callable. That is what lets the
simulator in ``sim/`` run whole clusters deterministically.
"""

from raft.messages import (
    AppendEntries,
    AppendEntriesReply,
    LogEntry,
    PreVote,
    PreVoteReply,
    RequestVote,
    RequestVoteReply,
)
from raft.node import RaftNode, Role
from raft.statemachine import Delete, Get, KeyValueStore, Set
from raft.storage import Storage

__all__ = [
    "AppendEntries",
    "AppendEntriesReply",
    "Delete",
    "Get",
    "KeyValueStore",
    "LogEntry",
    "PreVote",
    "PreVoteReply",
    "RaftNode",
    "RequestVote",
    "RequestVoteReply",
    "Role",
    "Set",
    "Storage",
]
