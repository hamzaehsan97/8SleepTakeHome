"""Shared test helpers."""

from __future__ import annotations

import random

from raft import LogEntry, RaftNode, Set, Storage


def make_node(
    node_id: int = 1,
    peers: tuple[int, ...] = (1, 2, 3),
    *,
    term: int = 0,
    voted_for: int | None = None,
    log_terms: tuple[int, ...] = (),
    storage: Storage | None = None,
    **options,
):
    """A node wired to an outbox list, for unit tests that drive it by hand.

    ``log_terms=(1, 1, 2)`` builds a log with three entries in those terms.
    Returns ``(node, outbox)`` where outbox collects ``(dst, message)``.
    """
    outbox: list[tuple[int, object]] = []
    if storage is None:
        storage = Storage(
            term=term,
            voted_for=voted_for,
            log=[LogEntry(t, Set(f"k{i}", i)) for i, t in enumerate(log_terms, start=1)],
        )
    node = RaftNode(
        node_id,
        peers,
        storage,
        send=lambda dst, msg: outbox.append((dst, msg)),
        rng=random.Random(0),
        **options,
    )
    return node, outbox


def terms(node: RaftNode) -> list[int]:
    return [node.storage.term_at(i) for i in range(1, node.storage.last_index + 1)]
