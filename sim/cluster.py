"""Drives a whole cluster in lock-step on logical time.

One ``tick()`` delivers due messages, ticks every live node, then runs the
safety checker. Tests therefore read like scenarios ("crash the leader, write,
heal") and never sleep.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Callable, Optional

from raft.messages import NodeId
from raft.node import RaftNode, Role
from raft.statemachine import Get, KeyValueStore
from raft.storage import Storage
from sim.invariants import InvariantChecker
from sim.network import SimNetwork


@dataclass(frozen=True)
class Proposal:
    """Where a command landed in the leader's log: (index, term) identifies
    an entry uniquely, so it is committed iff that exact pair is."""

    index: int
    term: int


class Cluster:
    def __init__(
        self,
        size: int = 3,
        seed: int = 0,
        *,
        node_options: Optional[dict] = None,
        **network_options,
    ) -> None:
        self.ids: list[NodeId] = list(range(1, size + 1))
        self.network = SimNetwork(random.Random(seed), **network_options)
        self.checker = InvariantChecker()
        self._node_options = node_options or {}

        # Disks and per-node RNGs outlive crashes. Giving each node its own
        # stream keeps runs reproducible without nodes perturbing each other.
        self.storages = {i: Storage() for i in self.ids}
        self._rngs = {i: random.Random(seed * 1_000_003 + i) for i in self.ids}
        self.nodes: dict[NodeId, Optional[RaftNode]] = {}
        # Messages held for paused nodes, replayed on resume.
        self._paused: dict[NodeId, list] = {}
        # What each node's state machine returned, per log index: volatile
        # like the state machine itself, so it is reset on restart.
        self.results: dict[NodeId, dict[int, tuple[int, Any]]] = {}
        for i in self.ids:
            self._boot(i)

    # -- lifecycle ----------------------------------------------------------

    def _boot(self, node_id: NodeId) -> None:
        self.results[node_id] = {}
        def send(dst, msg):
            self.network.send(node_id, dst, msg)

        def record(index, entry, result):
            self.results[node_id][index] = (entry.term, result)

        node = RaftNode(
            node_id,
            self.ids,
            self.storages[node_id],
            send=send,
            rng=self._rngs[node_id],
            state_machine=KeyValueStore(),
            on_apply=record,
            **self._node_options,
        )
        self.nodes[node_id] = node
        self.network.attach(node_id, node.receive)

    def crash(self, node_id: NodeId) -> None:
        """Lose all volatile state; the disk (Storage) is kept."""
        self._paused.pop(node_id, None)
        self.network.detach(node_id)
        self.nodes[node_id] = None

    def restart(self, node_id: NodeId) -> None:
        assert self.nodes[node_id] is None, f"node {node_id} is already running"
        self._boot(node_id)

    def pause(self, node_id: NodeId) -> None:
        """Freeze a process (think: a long GC pause or a VM migration). It
        neither runs nor loses state; messages sent to it pile up unread and
        are all delivered at once on resume. The classic way to meet a leader
        that doesn't know it has been replaced."""
        assert self.nodes[node_id] is not None and node_id not in self._paused
        buffer: list = []
        self._paused[node_id] = buffer
        self.network.attach(node_id, lambda src, msg: buffer.append((src, msg)))

    def resume(self, node_id: NodeId) -> None:
        buffered = self._paused.pop(node_id)
        node = self.nodes[node_id]
        assert node is not None
        self.network.attach(node_id, node.receive)
        for src, msg in buffered:
            node.receive(src, msg)

    # -- inspection ---------------------------------------------------------

    @property
    def live_nodes(self) -> list[RaftNode]:
        return [n for n in self.nodes.values() if n is not None]

    @property
    def paused(self) -> list[NodeId]:
        return list(self._paused)

    @property
    def active_nodes(self) -> list[RaftNode]:
        """Running and not frozen."""
        return [n for n in self.live_nodes if n.id not in self._paused]

    @property
    def leader(self) -> Optional[RaftNode]:
        """The active leader with the highest term. A deposed leader on the far
        side of a partition may still think it leads; the highest term wins."""
        leaders = [n for n in self.active_nodes if n.role is Role.LEADER]
        return max(leaders, key=lambda n: n.current_term, default=None)

    def has_quorum(self) -> bool:
        """Could *some* node currently exchange messages, in both directions,
        with a majority (itself included)? Fault injectors use this to avoid
        making progress impossible."""
        active = self.active_nodes
        need = len(self.ids) // 2 + 1
        return any(
            1 + sum(
                1 for m in active
                if m is not n and self.network.can_reach(n.id, m.id)
                and self.network.can_reach(m.id, n.id)
            ) >= need
            for n in active
        )

    def converged(self) -> bool:
        """Every live node has the same log, has committed all of it, and has
        applied it to an identical state machine."""
        live = self.live_nodes
        if not live or self.leader is None:
            return False
        last = live[0].storage.last_index
        state = live[0].state_machine.snapshot()
        return all(
            n.storage.last_index == last
            and n.commit_index == last
            and n.last_applied == last
            and n.state_machine.snapshot() == state
            for n in live
        )

    # -- time ---------------------------------------------------------------

    def tick(self, n: int = 1) -> None:
        for _ in range(n):
            self.network.step()
            for node in self.active_nodes:
                node.tick()
            self.checker.check(self.live_nodes)

    def run_until(self, predicate: Callable[[], bool], timeout: int = 500) -> int:
        """Tick until ``predicate()`` holds; fail loudly if it never does."""
        start = self.network.now
        while not predicate():
            if self.network.now - start >= timeout:
                raise TimeoutError(
                    f"condition not met within {timeout} ticks; "
                    f"nodes: {self.nodes}"
                )
            self.tick()
        return self.network.now - start

    def wait_for_leader(self, timeout: int = 500) -> RaftNode:
        self.run_until(lambda: self.leader is not None, timeout)
        return self.leader  # type: ignore[return-value]

    def wait_until_converged(self, timeout: int = 500) -> None:
        self.run_until(self.converged, timeout)

    # -- client -------------------------------------------------------------

    def _try_propose(self, command) -> Optional[tuple[RaftNode, Proposal]]:
        leader = self.leader
        result = leader.propose(command) if leader else None
        if leader is None or result is None:
            return None
        return leader, Proposal(*result)

    def propose(self, command) -> Optional[Proposal]:
        """One attempt at the current leader. No retry, no waiting."""
        attempt = self._try_propose(command)
        return attempt[1] if attempt else None

    def is_committed(self, proposal: Proposal) -> bool:
        return self.checker.is_committed(proposal.index, proposal.term)

    def commit(self, command, timeout: int = 500, attempt_timeout: int = 150) -> Proposal:
        """Submit ``command`` and block until it is committed.

        Like a real client, each attempt has its own timeout and the command is
        re-sent to whoever the leader is now. A leader that is cut off from a
        majority never gives a verdict (base Raft has no way to tell it to stop
        leading), so waiting on it indefinitely would just be a client bug.

        This gives at-least-once semantics: if an attempt commits after the
        client gave up on it, the retry commits a second copy. That's fine for
        idempotent commands (Set, Get); real systems dedupe with client IDs.
        """
        deadline = self.network.now + timeout
        while self.network.now < deadline:
            attempt = self._try_propose(command)
            if attempt is None:
                self.tick()
                continue
            leader, proposal = attempt
            give_up = min(deadline, self.network.now + attempt_timeout)
            while self.network.now < give_up:
                self.tick()
                if self.is_committed(proposal):
                    return proposal
                if leader is not self.nodes[leader.id] or self.leader is not leader:
                    break  # it crashed, was deposed, or a higher-term leader appeared
        raise TimeoutError(f"could not commit {command!r} within {timeout} ticks")

    def read(self, key: str, timeout: int = 500) -> Any:
        """A linearizable read: the Get is committed through the log, so it is
        ordered after every write acknowledged before it and cannot be served
        by a leader that has been deposed (it can't commit anything). Slower
        than ReadIndex or leader leases, but obviously correct."""
        proposal = self.commit(Get(key), timeout)

        def answer():
            for table in self.results.values():
                hit = table.get(proposal.index)
                if hit and hit[0] == proposal.term:
                    return hit
            return None

        self.run_until(lambda: answer() is not None, timeout)
        return answer()[1]  # type: ignore[index]
