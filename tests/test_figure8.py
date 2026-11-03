"""Figure 8 of the Raft paper, played out on a real cluster.

The trap: an entry from an *earlier* term can sit on a majority of servers and
still be overwritten by a later leader. A leader that counts replicas to commit
such an entry will acknowledge a write that then vanishes.

Random fault injection is very unlikely to hit this interleaving, so it's built
by hand. Elections are forced (timeouts are effectively infinite) and message
loss is arranged precisely. The cluster-level safety checker is what turns a
wrong implementation into a failure here, with no extra assertions on the
outcome needed beyond the one that states the rule directly.

Servers S1..S5 are node ids 1..5.
"""

from raft import Role, Set
from sim import Cluster


def campaign(cluster, node_id):
    """Force node_id to run for election in a term higher than any it can see."""
    highest = max(n.current_term for n in cluster.live_nodes)
    node = cluster.nodes[node_id]
    while node.current_term <= highest:
        node._start_election()


def silence(cluster, node_id):
    """Cut every outbound link, dropping messages already in flight, then
    crash the node. Models a process that dies right after deciding."""
    for other in cluster.ids:
        if other != node_id:
            cluster.network.cut(node_id, other)
    cluster.crash(node_id)


def test_old_term_entry_on_a_majority_is_not_committed_and_may_be_overwritten():
    cluster = Cluster(
        5, seed=0,
        node_options={"election_timeout": (10**6, 10**6 + 1), "max_batch": 1},
    )
    node = lambda i: cluster.nodes[i]  # noqa: E731  (nodes are replaced on restart)

    # Term 1: S1 leads and everyone holds its no-op at index 1.
    campaign(cluster, 1)
    cluster.run_until(lambda: node(1).role is Role.LEADER)
    cluster.wait_until_converged()

    # (a) S1 is cut off with S2 alone, takes a write, and replicates it to S2.
    cluster.network.partition([1, 2], [3, 4, 5])
    node(1).propose(Set("x", "written-by-S1"))
    cluster.run_until(lambda: node(2).storage.last_index == 2)
    assert node(1).commit_index == 1

    # (b) S1 crashes. S5 wins term 2 using S3 and S4, appends a term-2 no-op
    # at index 2, and dies before telling anyone.
    cluster.crash(1)
    cluster.network.partition([2], [3, 4, 5])
    campaign(cluster, 5)
    cluster.run_until(lambda: node(5).role is Role.LEADER)
    silence(cluster, 5)

    # (c) S1 returns and wins term 3 (S3 and S4 agree its log is newer). It
    # re-replicates its term-1 entry to S3 and S4. As soon as one of them has
    # it, it is on S1, S2 and that node: a majority. Stop the moment that
    # happens, before the term-3 no-op (index 3) reaches anyone but S2.
    cluster.network.heal()
    cluster.restart(1)
    campaign(cluster, 1)
    cluster.run_until(lambda: node(1).role is Role.LEADER)
    cluster.run_until(lambda: max(node(1).match_index[3], node(1).match_index[4]) >= 2)

    # THE RULE: it is on a majority, but it is from term 1 and S1 leads term 3,
    # so S1 must not call it committed. (A leader that counts replicas does.)
    assert node(1).storage.term_at(2) == 1
    assert node(1).commit_index < 2
    silence(cluster, 1)

    # (d) S5 returns and wins a later term. S3 and S4 vote for it because its
    # last entry (term 2) beats theirs (term 1); S2 refuses (its log ends in
    # term 3). S5 overwrites index 2 everywhere.
    cluster.network.heal()
    cluster.restart(5)
    campaign(cluster, 5)
    cluster.run_until(lambda: node(5).role is Role.LEADER)
    cluster.restart(1)
    cluster.wait_until_converged()

    # S1's write was never acknowledged, so losing it is legal. Had S1 counted
    # replicas, it would have committed it, and the checker would have failed
    # the run above when S5's entry was committed at the same index.
    assert all(n.state_machine.get("x") is None for n in cluster.live_nodes)
