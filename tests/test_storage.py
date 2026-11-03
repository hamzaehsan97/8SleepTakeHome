"""Storage on its own, with no cluster.

``Storage`` is what survives a crash, so its contract (what it keeps, what it
refuses) is pinned directly rather than only through whole-cluster scenarios.
"""

import pytest

from raft import LogEntry, Set, Storage


def entries(*terms):
    return [LogEntry(t, Set(f"k{i}", i)) for i, t in enumerate(terms, start=1)]


def reopen(disk: Storage) -> Storage:
    """A restart: a new Storage built from exactly what the old one persisted."""
    log = [disk.entry(i) for i in range(1, disk.last_index + 1)]
    return Storage(term=disk.current_term, voted_for=disk.voted_for, log=log)


def test_term_and_vote_are_restored_after_reopening():
    disk = Storage()
    disk.save_hard_state(7, 3)
    again = reopen(disk)
    assert (again.current_term, again.voted_for) == (7, 3)


def test_append_then_read_back():
    disk = Storage()
    disk.append(entries(1, 1, 2))
    assert disk.last_index == 3
    assert disk.last_term == 2
    assert disk.entry(2) == LogEntry(1, Set("k2", 2))
    assert disk.term_at(0) == 0 and disk.term_at(3) == 2
    assert [e.term for e in disk.entries_from(2, 5)] == [1, 2]
    assert disk.first_index_of_term(2) == 3 and disk.last_index_of_term(1) == 2
    assert reopen(disk).last_index == 3


def test_truncate_removes_the_index_and_everything_after():
    disk = Storage(log=entries(1, 1, 2, 2))
    disk.truncate_from(3)
    assert disk.last_index == 2
    assert disk.last_term == 1
    with pytest.raises(IndexError):
        disk.entry(3)


def test_lower_term_is_refused_and_leaves_state_untouched():
    disk = Storage(term=5, voted_for=2)
    with pytest.raises(AssertionError):
        disk.save_hard_state(4, None)
    assert (disk.current_term, disk.voted_for) == (5, 2)


def test_same_term_may_change_the_vote():
    disk = Storage(term=5)
    disk.save_hard_state(5, 4)
    assert (disk.current_term, disk.voted_for) == (5, 4)
