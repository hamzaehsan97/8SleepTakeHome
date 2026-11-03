"""What a client can observe, under faults.

Safety invariants talk about logs. Clients only see request/response pairs, so
this checks the property they actually care about, in the simplest setting
where it's cheap to be exact: one sequential client talking to a single
register whose values only ever increase.

For a sequential client, linearizability collapses to: every read returns
exactly the value of the most recent acknowledged write.

Assumption, stated exactly: retries are harmless here only because there is one
sequential client and one register. A retry re-sends the same value, so a
duplicate of an acknowledged write changes nothing. An abandoned attempt (one
the client gave up on after a timeout) could in principle still commit later,
after a newer write, and overwrite it with an older value. That would be a
client-visible anomaly, and it is not ruled out in general; it is only not
observed under this workload. With several clients or several keys this
argument does not hold and a real linearizability checker would be needed.
"""

import random

import pytest

from raft import Set
from sim import Cluster
from tests.faults import FAULTS, inject
from tests.test_chaos import CONFIGS


@pytest.mark.parametrize("config", CONFIGS)
@pytest.mark.parametrize("seed", range(25))
def test_sequential_client_always_reads_its_own_latest_write(seed, config):
    rng = random.Random(1000 + seed)
    # This test needs *availability* as well as safety, since the client waits
    # for every operation. Base Raft is known to wedge when a leader can send
    # but not receive (test_hardening pins that), so it isn't asked to survive
    # it here; test_chaos still throws that fault at it and demands safety.
    faults = FAULTS if config == "hardened" else tuple(f for f in FAULTS if f != "one_way")
    cluster = Cluster(
        5, seed=seed, node_options=CONFIGS[config],
        drop_rate=0.05, dup_rate=0.05, max_delay=5,
    )
    cluster.wait_for_leader()

    acknowledged = None
    reads_checked = 0
    for step in range(1, 41):
        if rng.random() < 0.5:
            inject(cluster, rng, rng.choice(faults))
            cluster.tick(rng.randint(1, 30))

        if rng.random() < 0.5:
            cluster.commit(Set("reg", step), timeout=3000)
            acknowledged = step
        else:
            observed = cluster.read("reg", timeout=3000)
            assert observed == acknowledged, (
                f"client-visible anomaly (not a Raft invariant failure): read "
                f"{observed!r} at step {step} but the last acknowledged write "
                f"was {acknowledged!r} (seed={seed}, config={config})"
            )
            reads_checked += 1

    assert reads_checked > 0
