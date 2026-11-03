"""Scenario tests for the failure modes that matter for a replicated log."""

import pytest

from raft import Role, Set
from sim import Cluster, Proposal


def test_stale_leaders_uncommitted_writes_are_overwritten_after_heal():
    """The canonical Raft scenario. A leader is cut off, keeps accepting
    writes it can never commit, and the majority elects a successor and moves
    on. When the partition heals, the old leader's phantom writes must vanish."""
    cluster = Cluster(5, seed=11)
    old = cluster.wait_for_leader()
    cluster.commit(Set("shared", "before"))
    cluster.wait_until_converged()

    others = [i for i in cluster.ids if i != old.id]
    cluster.network.partition([old.id], others)

    ghosts = [old.propose(Set("ghost", n)) for n in range(3)]
    assert all(ghosts)  # a deposed leader happily accepts writes...

    # ...while the majority elects someone else. (The cluster's `leader` is the
    # highest-term one, so wait for it to be somebody other than `old`.)
    cluster.run_until(lambda: cluster.leader is not None and cluster.leader.id != old.id)
    cluster.commit(Set("shared", "after"))
    assert old.role is Role.LEADER  # old leader has no idea yet
    assert not any(cluster.is_committed(Proposal(*g)) for g in ghosts)

    cluster.network.heal()
    cluster.wait_until_converged()
    for node in cluster.live_nodes:
        state = node.state_machine.snapshot()
        assert state == {"shared": "after"}, f"node {node.id}: {state}"
    assert cluster.nodes[old.id].role is Role.FOLLOWER


def test_committed_write_survives_leader_crash():
    cluster = Cluster(5, seed=12)
    leader = cluster.wait_for_leader()
    cluster.commit(Set("durable", 1))
    cluster.crash(leader.id)

    cluster.wait_for_leader()
    cluster.commit(Set("after", 2))
    cluster.wait_until_converged()
    for node in cluster.live_nodes:
        assert node.state_machine.snapshot() == {"durable": 1, "after": 2}


def test_whole_cluster_restart_loses_nothing_committed():
    cluster = Cluster(3, seed=13)
    cluster.wait_for_leader()
    for i in range(5):
        cluster.commit(Set(f"k{i}", i))
    cluster.wait_until_converged()
    expected = {f"k{i}": i for i in range(5)}

    for i in cluster.ids:
        cluster.crash(i)
    for i in cluster.ids:
        cluster.restart(i)
    # Volatile state is gone: nothing is applied until a leader re-commits.
    assert all(n.state_machine.snapshot() == {} for n in cluster.live_nodes)

    cluster.wait_for_leader()
    cluster.wait_until_converged()
    assert [n.state_machine.snapshot() for n in cluster.live_nodes] == [expected] * 3


def test_minority_partition_cannot_make_progress_but_majority_can():
    cluster = Cluster(5, seed=14)
    cluster.wait_for_leader()
    cluster.commit(Set("k", "v0"))
    cluster.wait_until_converged()

    minority, majority = [1, 2], [3, 4, 5]
    cluster.network.partition(minority, majority)
    cluster.run_until(lambda: cluster.leader is not None and cluster.leader.id in majority)
    cluster.commit(Set("k", "v1"))

    for i in minority:
        assert cluster.nodes[i].state_machine.get("k") == "v0"

    cluster.network.heal()
    cluster.wait_until_converged()
    assert all(n.state_machine.get("k") == "v1" for n in cluster.live_nodes)


def test_rejoining_node_with_inflated_term_costs_availability_not_safety():
    """Without PreVote, an isolated node keeps incrementing its term, and its
    first message after healing deposes a perfectly healthy leader. That is a
    known cost of base Raft. This test pins the behaviour (and the fact that
    no data is lost) so adding PreVote later shows up as a deliberate change."""
    cluster = Cluster(3, seed=15)
    leader = cluster.wait_for_leader()
    loner = next(n for n in cluster.live_nodes if n is not leader)
    cluster.commit(Set("k", 1))
    cluster.wait_until_converged()

    cluster.network.isolate(loner.id)
    cluster.tick(300)
    assert loner.current_term > leader.current_term + 3

    inflated = loner.current_term
    cluster.network.heal()
    # Logs already match, so "converged" would be true instantly; wait for the
    # disruption to play out: everyone adopts one term and a leader emerges.
    cluster.run_until(
        lambda: cluster.leader is not None
        and len({n.current_term for n in cluster.live_nodes}) == 1
    )
    cluster.wait_until_converged()
    assert cluster.leader.current_term >= inflated  # the healthy term was dragged up
    assert all(n.state_machine.get("k") == 1 for n in cluster.live_nodes)


@pytest.mark.parametrize("seed", range(10))
def test_lossy_duplicating_reordering_network(seed):
    cluster = Cluster(
        5, seed=seed, drop_rate=0.2, dup_rate=0.1, min_delay=1, max_delay=8
    )
    cluster.wait_for_leader(timeout=2000)
    for i in range(15):
        cluster.commit(Set("k", i), timeout=2000)
    cluster.wait_until_converged(timeout=2000)
    assert all(n.state_machine.get("k") == 14 for n in cluster.live_nodes)
    assert cluster.network.dropped > 0  # make sure we really injected faults
