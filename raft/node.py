"""A single Raft node.

The node is a deterministic state machine with two entry points:

* ``tick()``            - one unit of logical time has passed
* ``receive(src, msg)`` - a message arrived from another node

and one exit point, the ``send(dst, msg)`` callable it was constructed with.
No threads, no sockets, no wall clock. Section references (§5.x) are to the
extended Raft paper (Ongaro & Ousterhout).
"""

from __future__ import annotations

import logging
import random
from enum import Enum
from typing import Any, Callable, Iterable, Optional

from raft.messages import (
    AppendEntries,
    AppendEntriesReply,
    LogEntry,
    NodeId,
    PreVote,
    PreVoteReply,
    RequestVote,
    RequestVoteReply,
)
from raft.statemachine import KeyValueStore
from raft.storage import Storage

log = logging.getLogger(__name__)

Message = (
    PreVote | PreVoteReply | RequestVote | RequestVoteReply
    | AppendEntries | AppendEntriesReply
)


class Role(Enum):
    FOLLOWER = "follower"
    PRE_CANDIDATE = "pre-candidate"
    CANDIDATE = "candidate"
    LEADER = "leader"


class RaftNode:
    def __init__(
        self,
        node_id: NodeId,
        peers: Iterable[NodeId],
        storage: Storage,
        send: Callable[[NodeId, Message], None],
        rng: random.Random,
        *,
        election_timeout: tuple[int, int] = (15, 30),
        heartbeat_interval: int = 5,
        max_batch: int = 32,
        state_machine: Optional[KeyValueStore] = None,
        pre_vote: bool = False,
        check_quorum: bool = False,
        on_apply: Optional[Callable[[int, LogEntry, Any], None]] = None,
    ) -> None:
        """``pre_vote`` and ``check_quorum`` are the two standard hardening
        extensions (thesis §9.6, §6.2). Both are off by default so the base
        algorithm is exactly the paper's; ``on_apply(index, entry, result)``
        lets a client layer observe results of applied commands."""
        self.id = node_id
        self.peers = tuple(p for p in peers if p != node_id)
        self.storage = storage
        self.state_machine = state_machine or KeyValueStore()

        self._send = send
        self._rng = rng
        self._election_timeout = election_timeout
        self._heartbeat_interval = heartbeat_interval
        self._max_batch = max_batch
        self._pre_vote = pre_vote
        self._check_quorum = check_quorum
        self._on_apply = on_apply

        # Volatile state. All of it is rebuilt after a crash: the commit index
        # is re-learned from the leader and the state machine is re-derived by
        # replaying committed entries.
        self.role = Role.FOLLOWER
        self.leader_id: Optional[NodeId] = None
        self.commit_index = 0
        self.last_applied = 0

        # Leader-only, reinitialised on every election win.
        self.next_index: dict[NodeId, int] = {}
        self.match_index: dict[NodeId, int] = {}

        self._votes: set[NodeId] = set()
        self._prevotes: set[NodeId] = set()
        self._heard_from: set[NodeId] = set()  # leader: peers that replied this window
        self._ticks_since_quorum_check = 0
        self._ticks_since_heard = 0
        self._election_deadline = 0
        self._ticks_since_heartbeat = 0
        self._reset_election_timer()

    # ------------------------------------------------------------------ API

    @property
    def current_term(self) -> int:
        return self.storage.current_term

    @property
    def quorum(self) -> int:
        return (len(self.peers) + 1) // 2 + 1

    def propose(self, command) -> Optional[tuple[int, int]]:
        """Ask to replicate ``command``.

        Returns ``(index, term)`` if this node is the leader and accepted the
        command, else ``None``. Acceptance is *not* commitment: the caller
        must watch for the entry to be committed, and for the term at that
        index to change (which means it was overwritten).
        """
        if self.role is not Role.LEADER:
            return None
        self.storage.append([LogEntry(self.current_term, command)])
        index = self.storage.last_index
        self._advance_commit()  # only matters for a single-node cluster
        self._broadcast_append()
        return index, self.current_term

    def tick(self) -> None:
        if self.role is Role.LEADER:
            if self._check_quorum and not self._still_has_quorum():
                return
            self._ticks_since_heartbeat += 1
            if self._ticks_since_heartbeat >= self._heartbeat_interval:
                self._broadcast_append()
        else:
            self._ticks_since_heard += 1
            if self._ticks_since_heard >= self._election_deadline:
                if self._pre_vote:
                    self._start_pre_vote()
                else:
                    self._start_election()

    def receive(self, src: NodeId, msg: Message) -> None:
        # §5.1: any message carrying a newer term makes us a follower of that
        # term, whatever we were doing. Doing this once, up front, means the
        # individual handlers only have to think about "same term" and "stale".
        # The one exception is PreVote, whose term is hypothetical: it must
        # not move anybody's real term.
        if not isinstance(msg, PreVote) and msg.term > self.current_term:
            self._become_follower(msg.term)

        if isinstance(msg, PreVote):
            self._on_pre_vote(src, msg)
        elif isinstance(msg, PreVoteReply):
            self._on_pre_vote_reply(src, msg)
        elif isinstance(msg, RequestVote):
            self._on_request_vote(src, msg)
        elif isinstance(msg, RequestVoteReply):
            self._on_request_vote_reply(src, msg)
        elif isinstance(msg, AppendEntries):
            self._on_append_entries(src, msg)
        elif isinstance(msg, AppendEntriesReply):
            self._on_append_entries_reply(src, msg)
        else:
            raise TypeError(f"unexpected message {msg!r}")

    # ------------------------------------------------------------- elections

    def _reset_election_timer(self) -> None:
        # Randomised per reset (§5.2) so that split votes resolve themselves.
        self._ticks_since_heard = 0
        self._election_deadline = self._rng.randint(*self._election_timeout)

    def _become_follower(self, term: int) -> None:
        was_follower = self.role is Role.FOLLOWER
        if term > self.current_term:
            # New term: any vote we cast belongs to an older term, and any
            # leader we knew belonged to an older term too.
            self.storage.save_hard_state(term, None)
            self.leader_id = None
        if not was_follower:
            self._trace("stepping down to follower")
            self.leader_id = None
            # A former leader/candidate has a stale timer, so it needs a fresh
            # one. A follower does NOT get its timer reset merely because it
            # saw a higher term (§5.2: only a valid AppendEntries or a granted
            # vote counts as hearing from a viable leader). Otherwise a
            # candidate that can never win could keep everyone else's
            # election timers from ever firing.
            self._reset_election_timer()
        self.role = Role.FOLLOWER
        self._votes.clear()
        self._prevotes.clear()

    def _start_election(self) -> None:
        # Term bump and self-vote hit disk together, before any RequestVote
        # leaves the node (otherwise a crash could let us vote twice).
        self.storage.save_hard_state(self.current_term + 1, self.id)
        self.role = Role.CANDIDATE
        self.leader_id = None
        self._votes = {self.id}
        self._reset_election_timer()
        self._trace("starting election")

        if len(self._votes) >= self.quorum:  # single-node cluster
            self._become_leader()
            return
        request = RequestVote(
            self.current_term, self.storage.last_index, self.storage.last_term
        )
        for peer in self.peers:
            self._send(peer, request)

    def _log_is_up_to_date(self, last_term: int, last_index: int) -> bool:
        """§5.4.1: is a candidate's log at least as up to date as ours?

        Compare the term of the last entry first, and only on a tie compare
        length. This is what guarantees a winner holds every committed entry.
        """
        return (last_term, last_index) >= (
            self.storage.last_term,
            self.storage.last_index,
        )

    def _on_request_vote(self, src: NodeId, msg: RequestVote) -> None:
        can_vote = self.storage.voted_for in (None, src)
        grant = (
            msg.term == self.current_term
            and can_vote
            and self._log_is_up_to_date(msg.last_log_term, msg.last_log_index)
        )
        if grant:
            # Persist the vote before the reply can be observed by anyone.
            self.storage.save_hard_state(self.current_term, src)
            self._reset_election_timer()
        self._trace(f"vote for {src}: {'granted' if grant else 'denied'}")
        self._send(src, RequestVoteReply(self.current_term, grant))

    def _on_request_vote_reply(self, src: NodeId, msg: RequestVoteReply) -> None:
        # Replies from an older election round (or when we are no longer
        # campaigning) are ignored; the network may deliver them arbitrarily late.
        if self.role is not Role.CANDIDATE or msg.term != self.current_term:
            return
        if msg.granted:
            self._votes.add(src)
            if len(self._votes) >= self.quorum:
                self._become_leader()

    def _become_leader(self) -> None:
        self._trace(f"won election with votes {sorted(self._votes)}")
        self.role = Role.LEADER
        self.leader_id = self.id
        self.next_index = {p: self.storage.last_index + 1 for p in self.peers}
        self.match_index = {p: 0 for p in self.peers}
        self._heard_from.clear()
        self._ticks_since_quorum_check = 0
        # §5.4.2: a leader may only commit entries from its *own* term by
        # counting replicas. Entries inherited from earlier terms become
        # committed indirectly, once a current-term entry lands after them.
        # Appending a no-op straight away means that happens without waiting
        # for a client write.
        self.storage.append([LogEntry(self.current_term, None)])
        self._advance_commit()
        self._broadcast_append()

    # ------------------------------------------------------------- pre-vote

    def _leader_seems_alive(self) -> bool:
        """Have we heard from a working leader within the shortest possible
        election timeout? If so, a challenger is probably just partitioned."""
        if self.role is Role.LEADER:
            return True
        return (
            self.leader_id is not None
            and self._ticks_since_heard < self._election_timeout[0]
        )

    def _start_pre_vote(self) -> None:
        # Note what does NOT happen here: no term bump, no vote recorded. If
        # we are the isolated one, the cluster never sees our term grow.
        self.role = Role.PRE_CANDIDATE
        self.leader_id = None
        self._prevotes = {self.id}
        self._reset_election_timer()
        self._trace("starting pre-vote")
        if len(self._prevotes) >= self.quorum:  # single-node cluster
            self._start_election()
            return
        request = PreVote(
            self.current_term + 1, self.storage.last_index, self.storage.last_term
        )
        for peer in self.peers:
            self._send(peer, request)

    def _on_pre_vote(self, src: NodeId, msg: PreVote) -> None:
        # Stateless on purpose: answering a PreVote changes nothing about us.
        grant = (
            msg.term > self.current_term
            and self._log_is_up_to_date(msg.last_log_term, msg.last_log_index)
            and not self._leader_seems_alive()
        )
        self._send(src, PreVoteReply(self.current_term, grant, msg.term))

    def _on_pre_vote_reply(self, src: NodeId, msg: PreVoteReply) -> None:
        if self.role is not Role.PRE_CANDIDATE:
            return
        if msg.proposed_term != self.current_term + 1:
            return  # reply to an earlier round
        if msg.granted:
            self._prevotes.add(src)
            if len(self._prevotes) >= self.quorum:
                self._start_election()

    # --------------------------------------------------------- check-quorum

    def _still_has_quorum(self) -> bool:
        """§6.2: a leader that hasn't heard from a majority for a whole
        election timeout is probably cut off, and should stop acting like one.
        Safety never needed this; it bounds how long clients can be misled."""
        self._ticks_since_quorum_check += 1
        if self._ticks_since_quorum_check < self._election_timeout[0]:
            return True
        active = 1 + len(self._heard_from)
        self._heard_from.clear()
        self._ticks_since_quorum_check = 0
        if active >= self.quorum:
            return True
        self._trace("lost contact with a majority; stepping down")
        self._become_follower(self.current_term)
        return False

    # ----------------------------------------------------------- replication

    def _broadcast_append(self) -> None:
        self._ticks_since_heartbeat = 0
        for peer in self.peers:
            self._send_append(peer)

    def _send_append(self, peer: NodeId) -> None:
        prev_index = self.next_index[peer] - 1
        self._send(
            peer,
            AppendEntries(
                term=self.current_term,
                prev_log_index=prev_index,
                prev_log_term=self.storage.term_at(prev_index),
                entries=self.storage.entries_from(
                    self.next_index[peer], self._max_batch
                ),
                leader_commit=self.commit_index,
            ),
        )

    def _on_append_entries(self, src: NodeId, msg: AppendEntries) -> None:
        if msg.term < self.current_term:
            self._send(src, AppendEntriesReply(self.current_term, success=False))
            return
        if self.role is Role.LEADER:
            # Two leaders in one term would break Election Safety. Treat it as
            # a bug in this implementation rather than something to tolerate.
            raise AssertionError(f"node {self.id}: second leader {src} in term {msg.term}")

        # A valid AppendEntries for our term: this is the leader. A candidate
        # that sees one gives up its own campaign (§5.2).
        self.role = Role.FOLLOWER
        self.leader_id = src
        self._reset_election_timer()

        store = self.storage
        prev = msg.prev_log_index

        # Consistency check (§5.3): do we hold the entry the leader says
        # precedes the new ones?
        if prev > store.last_index:
            self._send(
                src,
                AppendEntriesReply(
                    self.current_term, False, conflict_index=store.last_index + 1
                ),
            )
            return
        if store.term_at(prev) != msg.prev_log_term:
            conflict_term = store.term_at(prev)
            self._send(
                src,
                AppendEntriesReply(
                    self.current_term,
                    False,
                    conflict_index=store.first_index_of_term(conflict_term),
                    conflict_term=conflict_term,
                ),
            )
            return

        # Merge the entries. Only truncate at the first genuine conflict: a
        # delayed or duplicated AppendEntries can carry a *prefix* of what we
        # already hold, and deleting the suffix in that case would throw away
        # entries that may already be committed.
        for offset, entry in enumerate(msg.entries):
            index = prev + 1 + offset
            if index <= store.last_index:
                if store.term_at(index) == entry.term:
                    continue
                store.truncate_from(index)
            store.append(msg.entries[offset:])
            break

        # Advance the commit index, but only as far as the part of the log we
        # *know* matches the leader's. Using our own last index here would be
        # wrong: we might still hold stale, unverified entries beyond it.
        last_new = prev + len(msg.entries)
        if msg.leader_commit > self.commit_index:
            self.commit_index = min(msg.leader_commit, last_new)
            self._apply_committed()

        self._send(
            src, AppendEntriesReply(self.current_term, True, match_index=last_new)
        )

    def _on_append_entries_reply(self, src: NodeId, msg: AppendEntriesReply) -> None:
        if self.role is not Role.LEADER or msg.term != self.current_term:
            return
        self._heard_from.add(src)

        if msg.success:
            # max(): replies can arrive out of order, and a stale one must not
            # move match_index backwards.
            self.match_index[src] = max(self.match_index[src], msg.match_index)
            self.next_index[src] = self.match_index[src] + 1
            self._advance_commit()
            return

        # Rejected: back next_index up using the follower's hint.
        if msg.conflict_term:
            ours = self.storage.last_index_of_term(msg.conflict_term)
            target = ours + 1 if ours else msg.conflict_index
        else:
            target = msg.conflict_index
        # Never below what the follower has already acknowledged, and never
        # forwards: a stale rejection must not undo progress.
        target = max(target, self.match_index[src] + 1)
        if target < self.next_index[src]:
            self.next_index[src] = target
            self._send_append(src)  # retry right away rather than next heartbeat

    def _advance_commit(self) -> None:
        """Commit the highest index replicated on a majority (§5.3, §5.4.2)."""
        for n in range(self.storage.last_index, self.commit_index, -1):
            # Only entries from the current term are counted; see _become_leader.
            if self.storage.term_at(n) != self.current_term:
                break
            replicas = 1 + sum(1 for p in self.peers if self.match_index[p] >= n)
            if replicas >= self.quorum:
                self.commit_index = n
                self._apply_committed()
                return

    def _apply_committed(self) -> None:
        while self.last_applied < self.commit_index:
            self.last_applied += 1
            entry = self.storage.entry(self.last_applied)
            if entry.command is None:  # no-op
                continue
            result = self.state_machine.apply(entry.command)
            if self._on_apply is not None:
                self._on_apply(self.last_applied, entry, result)

    # ----------------------------------------------------------------- misc

    def _trace(self, text: str) -> None:
        log.debug("[node %s | term %s | %s] %s", self.id, self.current_term,
                  self.role.value, text)

    def __repr__(self) -> str:
        return (
            f"<RaftNode {self.id} {self.role.value} term={self.current_term} "
            f"log={self.storage.last_index} commit={self.commit_index}>"
        )
