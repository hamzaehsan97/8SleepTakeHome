import pytest

from raft import Role
from sim import Cluster


@pytest.mark.parametrize("size", [1, 3, 5])
def test_exactly_one_leader_is_elected(size):
    cluster = Cluster(size, seed=1)
    leader = cluster.wait_for_leader()
    cluster.run_until(lambda: all(n.leader_id == leader.id for n in cluster.live_nodes))
    assert [n.role is Role.LEADER for n in cluster.live_nodes].count(True) == 1


def test_leadership_is_stable_while_healthy():
    cluster = Cluster(5, seed=2)
    leader = cluster.wait_for_leader()
    term = leader.current_term
    cluster.tick(500)
    assert cluster.leader is leader and leader.current_term == term


@pytest.mark.parametrize("seed", range(10))
def test_new_leader_emerges_after_leader_crash(seed):
    cluster = Cluster(5, seed=seed)
    old = cluster.wait_for_leader()
    cluster.crash(old.id)
    new = cluster.wait_for_leader()
    assert new.id != old.id
    assert new.current_term > old.current_term


def test_no_leader_without_a_majority():
    cluster = Cluster(3, seed=3)
    leader = cluster.wait_for_leader()
    follower = next(n for n in cluster.live_nodes if n is not leader)
    cluster.crash(leader.id)
    cluster.crash(follower.id)
    survivor = cluster.live_nodes[0]
    cluster.tick(500)
    assert cluster.leader is None
    assert survivor.current_term > leader.current_term  # keeps campaigning, never wins

    cluster.restart(follower.id)  # majority restored
    cluster.wait_for_leader()


def test_split_votes_resolve_across_many_seeds():
    """With randomised timeouts, simultaneous candidates should always sort
    themselves out eventually. Timeouts this narrow force frequent collisions."""
    for seed in range(30):
        cluster = Cluster(5, seed=seed, node_options={"election_timeout": (10, 12)})
        cluster.wait_for_leader(timeout=1000)
