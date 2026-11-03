"""Randomised fault injection.

Each seed is a different, fully reproducible history of crashes, restarts,
partitions (clean and one-way), frozen processes and heals, interleaved with
client writes. The InvariantChecker runs on every tick, so a safety violation
anywhere in the run fails the test at the tick it happens; the seed is in the
test id, so replaying it is a one-liner.

Everything runs against both the plain algorithm and the PreVote+CheckQuorum
variant: the extensions must not cost any safety.
"""

import random

import pytest

from raft import Set
from sim import Cluster
from tests.faults import FAULTS, inject, repair_all

CONFIGS = {
    "base": {},
    "hardened": {"pre_vote": True, "check_quorum": True},
}


@pytest.mark.parametrize("config", CONFIGS)
@pytest.mark.parametrize("seed", range(40))
def test_safety_holds_under_random_faults(seed, config):
    rng = random.Random(seed)
    cluster = Cluster(
        5, seed=seed, node_options=CONFIGS[config],
        drop_rate=0.05, dup_rate=0.05, max_delay=6,
    )
    next_value = 0

    for _ in range(80):
        if rng.random() < 0.4:
            # Fire and forget: the write may well be lost, and that's allowed.
            cluster.propose(Set("k", next_value))
            next_value += 1
        else:
            inject(cluster, rng, rng.choice(FAULTS))
        cluster.tick(rng.randint(1, 40))

    # Recover everything and demand convergence.
    repair_all(cluster)
    cluster.network.drop_rate = cluster.network.dup_rate = 0
    cluster.wait_for_leader(timeout=2000)
    cluster.commit(Set("final", True), timeout=2000)
    cluster.wait_until_converged(timeout=2000)

    # Every entry anyone ever committed is in everyone's final log, in place.
    assert cluster.checker.committed
    for node in cluster.live_nodes:
        for index, entry in cluster.checker.committed.items():
            assert node.storage.entry(index) == entry
