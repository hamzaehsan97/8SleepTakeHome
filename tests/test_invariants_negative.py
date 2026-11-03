"""The safety checker must actually reject unsafe states.

Every other test runs the checker on correct behaviour, where it can only ever
stay quiet. Here each property gets the smallest state that breaks it, so a
checker that silently stopped checking would fail this file.
"""

import pytest

from raft import LogEntry, Role, Set
from sim.invariants import InvariantChecker, InvariantViolation
from tests.helpers import make_node


def entry(term, key="k", value=1):
    return LogEntry(term, Set(key, value))


def node_with(node_id, *entries, term=1):
    node, _ = make_node(node_id, term=term)
    node.storage.append(entries)
    return node


def test_valid_state_passes():
    leader = node_with(1, entry(1), term=1)
    leader.role = Role.LEADER
    leader.commit_index = leader.last_applied = 1
    follower = node_with(2, entry(1), term=1)
    follower.commit_index = follower.last_applied = 1

    checker = InvariantChecker()
    checker.check([leader, follower])
    checker.check([leader, follower])  # and again: re-checking is idempotent
    assert checker.leaders_by_term == {1: 1}
    assert checker.is_committed(1, 1)


def test_term_going_backwards_is_rejected():
    node, _ = make_node(1, term=3)
    checker = InvariantChecker()
    checker.check([node])
    node.storage._term = 2  # bypasses Storage's own guard, as a corrupt disk would
    with pytest.raises(InvariantViolation, match="term went backwards"):
        checker.check([node])


def test_two_leaders_in_one_term_is_rejected():
    a, _ = make_node(1, term=4)
    b, _ = make_node(2, term=4)
    a.role = b.role = Role.LEADER
    with pytest.raises(InvariantViolation, match="two leaders in term 4"):
        InvariantChecker().check([a, b])


def test_different_entries_committed_at_one_index_is_rejected():
    a = node_with(1, entry(1, value=1))
    b = node_with(2, entry(1, value=2))
    a.commit_index = a.last_applied = 1
    b.commit_index = b.last_applied = 1
    with pytest.raises(InvariantViolation, match="index 1 committed as"):
        InvariantChecker().check([a, b])


def test_applied_beyond_commit_index_is_rejected():
    node = node_with(1, entry(1))
    node.commit_index = 0
    node.last_applied = 1
    with pytest.raises(InvariantViolation, match="applied 1 > commit 0"):
        InvariantChecker().check([node])


def test_leader_missing_a_committed_entry_is_rejected():
    follower = node_with(1, entry(1), term=1)
    follower.commit_index = follower.last_applied = 1
    leader, _ = make_node(2, term=2)  # newer term, empty log
    leader.role = Role.LEADER
    with pytest.raises(InvariantViolation, match="missing committed entry 1"):
        InvariantChecker().check([follower, leader])


def test_logs_with_equal_terms_but_different_entries_are_rejected():
    a = node_with(1, entry(1, value=1), entry(1, value=2))
    b = node_with(2, entry(1, value=1), entry(1, value=3))
    with pytest.raises(InvariantViolation, match="diverge at index 2"):
        InvariantChecker().check([a, b])


def test_matching_entry_after_a_mismatch_is_rejected():
    # Index 1 differs in term, then index 2 looks identical. Equal (index, term)
    # at 2 would imply equal prefixes, which is false here.
    a = node_with(1, entry(1), entry(2, value=9))
    b = node_with(2, entry(2), entry(2, value=9))
    with pytest.raises(InvariantViolation, match="diverge at index 2"):
        InvariantChecker().check([a, b])
