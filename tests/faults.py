"""A random fault injector shared by the chaos and linearizability tests."""

from __future__ import annotations

import random

from sim import Cluster

FAULTS = ("crash", "restart", "partition", "one_way", "pause", "resume", "heal")


def repair_all(cluster: Cluster) -> None:
    cluster.network.heal()
    for node_id in cluster.paused:
        cluster.resume(node_id)
    for node_id in cluster.ids:
        if cluster.nodes[node_id] is None:
            cluster.restart(node_id)


def inject(cluster: Cluster, rng: random.Random, fault: str) -> None:
    """Apply one fault. If that leaves no majority able to talk to itself,
    undo everything: tests that need progress can't wait on a dead cluster."""
    active = [n.id for n in cluster.active_nodes]
    down = [i for i in cluster.ids if cluster.nodes[i] is None]

    if fault == "crash" and active:
        cluster.crash(rng.choice(active))
    elif fault == "restart" and down:
        cluster.restart(rng.choice(down))
    elif fault == "partition":
        order = rng.sample(cluster.ids, len(cluster.ids))
        cut = rng.randint(1, 2)
        cluster.network.partition(order[:cut], order[cut:])
    elif fault == "one_way":
        victim = rng.choice(cluster.ids)
        for other in cluster.ids:
            if other != victim:
                cluster.network.cut(other, victim)
    elif fault == "pause" and active:
        cluster.pause(rng.choice(active))
    elif fault == "resume" and cluster.paused:
        cluster.resume(rng.choice(cluster.paused))
    elif fault == "heal":
        cluster.network.heal()

    if not cluster.has_quorum():
        repair_all(cluster)
