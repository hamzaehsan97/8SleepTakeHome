import pytest

from raft import Delete, Set
from sim import Cluster, Proposal


def states(cluster):
    return [n.state_machine.snapshot() for n in cluster.live_nodes]


def test_single_node_cluster_commits_on_its_own():
    cluster = Cluster(1)
    cluster.wait_for_leader()
    cluster.commit(Set("a", 1))
    assert states(cluster) == [{"a": 1}]


@pytest.mark.parametrize("size", [3, 5])
def test_command_reaches_every_state_machine(size):
    cluster = Cluster(size, seed=4)
    cluster.wait_for_leader()
    cluster.commit(Set("color", "blue"))
    cluster.wait_until_converged()
    assert states(cluster) == [{"color": "blue"}] * size


def test_commands_apply_in_log_order_everywhere():
    cluster = Cluster(3, seed=5)
    cluster.wait_for_leader()
    for i in range(20):
        cluster.commit(Set("x", i))
    cluster.commit(Set("y", "keep"))
    cluster.commit(Delete("x"))
    cluster.wait_until_converged()
    assert states(cluster) == [{"y": "keep"}] * 3


def test_restarted_follower_catches_up():
    cluster = Cluster(3, seed=6)
    leader = cluster.wait_for_leader()
    follower = next(n for n in cluster.live_nodes if n is not leader)
    cluster.crash(follower.id)
    for i in range(10):
        cluster.commit(Set(f"k{i}", i))

    cluster.restart(follower.id)
    cluster.wait_until_converged()
    assert cluster.nodes[follower.id].state_machine.get("k9") == 9


def test_follower_far_behind_catches_up_in_few_round_trips():
    """Catch-up should be bounded by batch size, not by probing back one
    index at a time. 300 entries at batch 32 needs ~10 messages, not 300."""
    cluster = Cluster(3, seed=7)
    leader = cluster.wait_for_leader()
    follower = next(n for n in cluster.live_nodes if n is not leader)
    cluster.crash(follower.id)
    for i in range(300):
        cluster.commit(Set("n", i))

    cluster.restart(follower.id)
    took = cluster.run_until(
        lambda: cluster.nodes[follower.id].state_machine.get("n") == 299, timeout=200
    )
    assert took < 100


def test_leader_cannot_commit_without_a_majority():
    cluster = Cluster(3, seed=8)
    leader = cluster.wait_for_leader()
    cluster.wait_until_converged()
    cluster.network.isolate(leader.id)

    index, term = leader.propose(Set("lonely", True))
    cluster.tick(300)
    assert leader.commit_index < index
    assert not cluster.is_committed(Proposal(index, term))
