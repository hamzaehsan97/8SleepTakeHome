"""PreVote and CheckQuorum, and the nastier fault models they exist for.

Each extension is introduced with a pair of tests: one pinning how the base
algorithm misbehaves, and one showing the extension fixing it. If you break
the extension, the second fails; if you ever change the base behaviour, the
first one tells you deliberately.
"""

import pytest

from raft import Get, Role, Set
from sim import Cluster, Proposal

HARDENED = {"pre_vote": True, "check_quorum": True}


def cut_inbound(cluster, victim):
    """Everyone can still hear the victim, but the victim hears no one."""
    for other in cluster.ids:
        if other != victim:
            cluster.network.cut(other, victim)


def a_follower(cluster, leader):
    return next(n for n in cluster.live_nodes if n is not leader)


# -- check-quorum -----------------------------------------------------------

def test_base_raft_leaves_an_isolated_leader_in_charge():
    cluster = Cluster(5, seed=21)
    old = cluster.wait_for_leader()
    cluster.wait_until_converged()
    cluster.network.isolate(old.id)
    cluster.tick(400)
    assert old.role is Role.LEADER  # safe, but it will mislead any client that asks


def test_check_quorum_deposes_an_isolated_leader():
    cluster = Cluster(5, seed=21, node_options=HARDENED)
    old = cluster.wait_for_leader()
    cluster.wait_until_converged()
    cluster.network.isolate(old.id)
    cluster.run_until(lambda: old.role is not Role.LEADER, timeout=100)


def test_check_quorum_does_not_depose_a_healthy_leader():
    cluster = Cluster(5, seed=22, node_options=HARDENED)
    leader = cluster.wait_for_leader()
    term = leader.current_term
    cluster.tick(1000)
    assert cluster.leader is leader and leader.current_term == term


# -- pre-vote ---------------------------------------------------------------

def test_pre_vote_stops_an_isolated_node_inflating_its_term():
    cluster = Cluster(3, seed=15, node_options={"pre_vote": True})
    leader = cluster.wait_for_leader()
    loner = a_follower(cluster, leader)
    cluster.commit(Set("k", 1))
    cluster.wait_until_converged()
    term = leader.current_term

    cluster.network.isolate(loner.id)
    cluster.tick(300)
    assert loner.current_term == term  # contrast: base Raft reaches 15+
    assert loner.role is Role.PRE_CANDIDATE

    cluster.network.heal()
    cluster.tick(200)
    # Nobody was disturbed: same leader, same term, loner is a follower again.
    assert cluster.leader is leader and leader.current_term == term
    assert loner.role is Role.FOLLOWER
    cluster.wait_until_converged()


def test_one_way_partition_churns_leadership_in_base_raft():
    """A node that can talk but not listen keeps campaigning, and each
    RequestVote it sends is heard, forcing the real leader to step down."""
    cluster = Cluster(5, seed=31)
    leader = cluster.wait_for_leader()
    cluster.wait_until_converged()
    start = leader.current_term
    cut_inbound(cluster, a_follower(cluster, leader).id)

    cluster.tick(400)
    assert max(n.current_term for n in cluster.live_nodes) >= start + 3


def test_one_way_partition_is_harmless_with_pre_vote():
    cluster = Cluster(5, seed=31, node_options=HARDENED)
    leader = cluster.wait_for_leader()
    cluster.wait_until_converged()
    start = leader.current_term
    cut_inbound(cluster, a_follower(cluster, leader).id)

    cluster.tick(400)
    assert cluster.leader is leader and leader.current_term == start
    cluster.commit(Set("still", "available"))


def test_leader_that_cannot_hear_replies_wedges_base_raft():
    """The leader's heartbeats reach everyone, so nobody ever times out, yet
    it never sees an acknowledgement and so can never commit anything."""
    cluster = Cluster(5, seed=32)
    old = cluster.wait_for_leader()
    cluster.wait_until_converged()
    cut_inbound(cluster, old.id)
    with pytest.raises(TimeoutError):
        cluster.commit(Set("k", 1), timeout=300)


def test_check_quorum_unwedges_a_leader_that_cannot_hear_replies():
    cluster = Cluster(5, seed=32, node_options=HARDENED)
    old = cluster.wait_for_leader()
    cluster.wait_until_converged()
    cut_inbound(cluster, old.id)

    cluster.run_until(
        lambda: cluster.leader is not None and cluster.leader.id != old.id, timeout=300
    )
    cluster.commit(Set("k", 1))
    assert old.role is not Role.LEADER


# -- paused (GC-stalled) processes -----------------------------------------

@pytest.mark.parametrize("options", [{}, HARDENED], ids=["base", "hardened"])
def test_paused_leader_learns_it_was_replaced_when_it_wakes_up(options):
    cluster = Cluster(5, seed=41, node_options=options)
    old = cluster.wait_for_leader()
    cluster.commit(Set("a", 1))
    cluster.wait_until_converged()

    cluster.pause(old.id)
    cluster.run_until(lambda: cluster.leader is not None and cluster.leader.id != old.id)
    cluster.commit(Set("a", 2))
    assert old.role is Role.LEADER  # frozen: it has no idea

    cluster.resume(old.id)  # a burst of stale-to-it, newer-than-it messages
    assert old.role is Role.FOLLOWER
    cluster.wait_until_converged()
    assert all(n.state_machine.get("a") == 2 for n in cluster.live_nodes)


def test_crashing_a_paused_node_discards_its_buffered_messages():
    cluster = Cluster(3, seed=42)
    cluster.wait_for_leader()
    victim = cluster.live_nodes[0].id
    cluster.pause(victim)
    cluster.tick(50)
    cluster.crash(victim)
    cluster.restart(victim)
    cluster.wait_until_converged()


# -- reads go through the log ----------------------------------------------

def test_read_returns_latest_acknowledged_write():
    cluster = Cluster(3, seed=51)
    cluster.wait_for_leader()
    assert cluster.read("k") is None
    cluster.commit(Set("k", "v1"))
    assert cluster.read("k") == "v1"
    cluster.commit(Set("k", "v2"))
    assert cluster.read("k") == "v2"


def test_deposed_leader_cannot_answer_a_read():
    """The reason reads go through the log. This isolated leader still
    believes it leads, holds a stale value, and would happily serve it if
    reads bypassed consensus. Routed through the log, the Get never commits."""
    cluster = Cluster(5, seed=52)
    old = cluster.wait_for_leader()
    cluster.commit(Set("k", "old"))
    cluster.wait_until_converged()
    cluster.network.isolate(old.id)

    stale_read = Proposal(*old.propose(Get("k")))
    cluster.run_until(lambda: cluster.leader is not None and cluster.leader.id != old.id)
    cluster.commit(Set("k", "new"))
    cluster.tick(100)

    assert not cluster.is_committed(stale_read)
    assert stale_read.index not in cluster.results[old.id]  # never answered
    assert cluster.read("k") == "new"

