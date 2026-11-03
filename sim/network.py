"""An unreliable network running on logical time.

Messages are queued with a delivery time. Random per-message delay is what
produces reordering; the drop and duplicate rates cover the other two classic
faults. Partitions are checked both when a message is sent *and* when it is
delivered, so a message already in flight when a partition starts is lost,
which is what a real cut cable does.

All randomness comes from the ``random.Random`` passed in, so a failing seed
replays exactly.
"""

from __future__ import annotations

import heapq
import itertools
import random
from typing import Any, Callable, Iterable

from raft.messages import NodeId

Handler = Callable[[NodeId, Any], None]


class SimNetwork:
    def __init__(
        self,
        rng: random.Random,
        *,
        min_delay: int = 1,
        max_delay: int = 3,
        drop_rate: float = 0.0,
        dup_rate: float = 0.0,
    ) -> None:
        # A delay of 0 would let a handler's reply be delivered in the same
        # step, which makes "one tick" ill-defined.
        assert 1 <= min_delay <= max_delay
        self._rng = rng
        self._min_delay = min_delay
        self._max_delay = max_delay
        self.drop_rate = drop_rate
        self.dup_rate = dup_rate

        self.now = 0
        self._queue: list[tuple[int, int, NodeId, NodeId, Any]] = []
        self._seq = itertools.count()  # tie-break so equal times stay deterministic
        self._handlers: dict[NodeId, Handler] = {}
        self._group: dict[NodeId, int] = {}
        self._cut: set[tuple[NodeId, NodeId]] = set()  # one-way: (src, dst)

        self.sent = self.delivered = self.dropped = 0

    # -- membership: a crashed node simply has no handler -------------------

    def attach(self, node_id: NodeId, handler: Handler) -> None:
        self._handlers[node_id] = handler

    def detach(self, node_id: NodeId) -> None:
        self._handlers.pop(node_id, None)

    # -- partitions ---------------------------------------------------------

    def partition(self, *groups: Iterable[NodeId]) -> None:
        """Split the network. Nodes can only talk within their own group;
        any node not listed ends up together in an implicit group 0."""
        self._group = {n: i + 1 for i, g in enumerate(groups) for n in g}

    def isolate(self, node_id: NodeId) -> None:
        self._group[node_id] = max(self._group.values(), default=0) + 1

    def cut(self, src: NodeId, dst: NodeId) -> None:
        """Block ``src -> dst`` only. Asymmetric failures (a broken NIC queue,
        a one-way firewall rule) are nastier than clean partitions: a node can
        keep *sending* requests it will never hear answered."""
        self._cut.add((src, dst))

    def heal(self) -> None:
        self._group = {}
        self._cut = set()

    def can_reach(self, a: NodeId, b: NodeId) -> bool:
        """Can a message currently travel from ``a`` to ``b``?"""
        return self._group.get(a, 0) == self._group.get(b, 0) and (a, b) not in self._cut

    # -- transport ----------------------------------------------------------

    def send(self, src: NodeId, dst: NodeId, msg: Any) -> None:
        self.sent += 1
        if not self.can_reach(src, dst) or self._rng.random() < self.drop_rate:
            self.dropped += 1
            return
        copies = 2 if self._rng.random() < self.dup_rate else 1
        for _ in range(copies):
            delay = self._rng.randint(self._min_delay, self._max_delay)
            heapq.heappush(
                self._queue, (self.now + delay, next(self._seq), src, dst, msg)
            )

    def step(self) -> None:
        """Advance logical time by one tick and deliver everything now due."""
        self.now += 1
        while self._queue and self._queue[0][0] <= self.now:
            _, _, src, dst, msg = heapq.heappop(self._queue)
            handler = self._handlers.get(dst)
            if handler is None or not self.can_reach(src, dst):
                self.dropped += 1
                continue
            self.delivered += 1
            handler(src, msg)
