"""A narrated walk through the headline scenario.

    python -m examples.demo

Five nodes elect a leader and commit a write. The leader is then cut off from
the rest of the cluster but keeps accepting writes it can never commit. The
majority elects a new leader and carries on. When the partition heals, the old
leader's phantom writes are overwritten and every node converges.
"""

from raft import Set
from sim import Cluster, Proposal


def show(cluster, title):
    print(f"\n-- {title} (t={cluster.network.now})")
    for i in cluster.ids:
        n = cluster.nodes[i]
        if n is None:
            print(f"   node {i}: DOWN")
        else:
            print(
                f"   node {i}: {n.role.value:<9} term={n.current_term:<2} "
                f"log={n.storage.last_index:<2} commit={n.commit_index:<2} "
                f"kv={n.state_machine.snapshot()}"
            )


def main():
    cluster = Cluster(5, seed=11)
    old = cluster.wait_for_leader()
    cluster.commit(Set("shared", "before"))
    cluster.wait_until_converged()
    show(cluster, f"healthy; node {old.id} leads")

    others = [i for i in cluster.ids if i != old.id]
    cluster.network.partition([old.id], others)
    ghosts = [old.propose(Set("ghost", n)) for n in range(3)]
    cluster.run_until(lambda: cluster.leader and cluster.leader.id != old.id)
    cluster.commit(Set("shared", "after"))
    show(cluster, f"node {old.id} isolated, 3 writes stuck on it; majority moved on")
    assert not any(cluster.is_committed(Proposal(*g)) for g in ghosts)

    cluster.network.heal()
    cluster.wait_until_converged()
    show(cluster, "healed: ghost writes overwritten, all nodes agree")
    print(f"\nmessages: sent={cluster.network.sent} "
          f"delivered={cluster.network.delivered} dropped={cluster.network.dropped}")


if __name__ == "__main__":
    main()
