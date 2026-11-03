"""Unit tests that drive a single node by hand.

The cluster tests show that things work end to end; these pin down the specific
rules where Raft implementations tend to be subtly wrong. Each one corresponds
to a sentence in the paper that is easy to implement slightly differently.
"""

from raft import (
    AppendEntries, AppendEntriesReply, Get, LogEntry, PreVote, PreVoteReply,
    RequestVote, RequestVoteReply, Role, Set, Storage,
)
from tests.helpers import make_node, terms


# -- voting -----------------------------------------------------------------

def test_vote_survives_restart():
    """A node that voted, crashed and came back must not vote again that term."""
    disk = Storage()
    node, outbox = make_node(1, storage=disk)
    node.receive(2, RequestVote(term=5, last_log_index=0, last_log_term=0))
    assert outbox[-1] == (2, RequestVoteReply(5, True))

    rebooted, outbox2 = make_node(1, storage=disk)  # same disk, fresh process
    rebooted.receive(3, RequestVote(term=5, last_log_index=0, last_log_term=0))
    assert outbox2[-1] == (3, RequestVoteReply(5, False))


def test_vote_is_idempotent_for_the_same_candidate():
    """A retransmitted RequestVote from the candidate we already backed is fine."""
    node, outbox = make_node(1)
    for _ in range(2):
        node.receive(2, RequestVote(term=1, last_log_index=0, last_log_term=0))
    assert [m for _, m in outbox] == [RequestVoteReply(1, True)] * 2


def test_denies_candidate_with_older_last_term_even_if_log_is_longer():
    node, outbox = make_node(1, term=3, log_terms=(1, 3))
    node.receive(2, RequestVote(term=4, last_log_index=10, last_log_term=2))
    assert outbox[-1][1].granted is False


def test_grants_candidate_with_same_last_term_and_longer_log():
    node, outbox = make_node(1, term=3, log_terms=(1, 3))
    node.receive(2, RequestVote(term=4, last_log_index=3, last_log_term=3))
    assert outbox[-1][1].granted is True


def test_denies_vote_for_stale_term():
    node, outbox = make_node(1, term=5)
    node.receive(2, RequestVote(term=4, last_log_index=0, last_log_term=0))
    assert outbox[-1][1] == RequestVoteReply(5, False)


# -- append entries: log repair --------------------------------------------

def test_conflicting_suffix_is_replaced():
    node, _ = make_node(2, term=1, log_terms=(1, 1, 1))
    node.receive(1, AppendEntries(
        term=2, prev_log_index=1, prev_log_term=1,
        entries=(LogEntry(2, Set("a", 1)), LogEntry(2, Set("b", 2))), leader_commit=0,
    ))
    assert terms(node) == [1, 2, 2]


def test_stale_prefix_does_not_truncate_a_longer_matching_log():
    """A delayed AppendEntries carrying only the first two entries must not
    delete the two we've since received."""
    node, _ = make_node(2, term=2, log_terms=(1, 1, 2, 2))
    node.receive(1, AppendEntries(
        term=2, prev_log_index=0, prev_log_term=0,
        entries=node.storage.entries_from(1, 2), leader_commit=0,
    ))
    assert terms(node) == [1, 1, 2, 2]


def test_commit_index_is_capped_at_last_verified_entry():
    """leader_commit may exceed what this message proves we share with the
    leader; our extra tail entries are unverified and must not be committed."""
    node, _ = make_node(2, term=2, log_terms=(1, 1, 2, 2))
    node.receive(1, AppendEntries(
        term=2, prev_log_index=1, prev_log_term=1, entries=(), leader_commit=4,
    ))
    assert node.commit_index == 1


def test_rejection_when_log_is_too_short_hints_at_our_length():
    node, outbox = make_node(2, term=1, log_terms=(1,))
    node.receive(1, AppendEntries(
        term=1, prev_log_index=5, prev_log_term=1, entries=(), leader_commit=0,
    ))
    reply = outbox[-1][1]
    assert not reply.success and reply.conflict_index == 2 and reply.conflict_term == 0


def test_rejection_on_term_mismatch_hints_at_start_of_conflicting_term():
    node, outbox = make_node(2, term=3, log_terms=(1, 2, 2, 2))
    node.receive(1, AppendEntries(
        term=3, prev_log_index=4, prev_log_term=3, entries=(), leader_commit=0,
    ))
    reply = outbox[-1][1]
    assert (reply.success, reply.conflict_term, reply.conflict_index) == (False, 2, 2)


def test_stale_leader_is_rejected_and_told_the_new_term():
    node, outbox = make_node(2, term=7)
    node.receive(1, AppendEntries(
        term=3, prev_log_index=0, prev_log_term=0, entries=(LogEntry(3, Set("x", 1)),),
        leader_commit=0,
    ))
    assert outbox[-1][1] == AppendEntriesReply(7, False)
    assert node.storage.last_index == 0


def test_candidate_steps_down_on_append_entries_from_current_term_leader():
    node, _ = make_node(2, term=0)
    node._start_election()  # now a candidate in term 1
    assert node.role is Role.CANDIDATE
    node.receive(3, AppendEntries(
        term=1, prev_log_index=0, prev_log_term=0, entries=(), leader_commit=0,
    ))
    assert node.role is Role.FOLLOWER and node.leader_id == 3


# -- leader: commitment rules ----------------------------------------------

def _leader_with_log(log_terms, term):
    node, outbox = make_node(1, term=term, log_terms=log_terms)
    node.role = Role.LEADER
    node.next_index = {2: 1, 3: 1}
    node.match_index = {2: 0, 3: 0}
    return node, outbox


def test_leader_never_commits_old_term_entry_by_counting_replicas():
    """Figure 8: an entry from an older term that sits on a majority can still
    be overwritten, so a leader must not commit it by counting. It becomes
    committed only when a current-term entry after it is."""
    node, _ = _leader_with_log(log_terms=(2,), term=4)
    node.match_index = {2: 1, 3: 1}  # entry 1 (term 2) is on all three nodes
    node._advance_commit()
    assert node.commit_index == 0

    node.storage.append([LogEntry(4, Set("now", 1))])
    node.match_index = {2: 2, 3: 0}
    node._advance_commit()
    assert node.commit_index == 2  # commits the term-4 entry and, with it, entry 1


def test_leader_needs_a_majority_to_commit():
    node, _ = _leader_with_log(log_terms=(4,), term=4)
    node._advance_commit()
    assert node.commit_index == 0  # only the leader has it: 1 of 3
    node.match_index[2] = 1
    node._advance_commit()
    assert node.commit_index == 1


def test_leader_uses_conflict_hint_to_skip_a_whole_term():
    node, outbox = _leader_with_log(log_terms=(1, 1, 3, 3, 3), term=3)
    node.next_index[2] = 6
    # Follower says: I have term-2 entries starting at index 2 and you don't
    # have any term 2, so resume from where its term-2 run began.
    node.receive(2, AppendEntriesReply(term=3, success=False, conflict_index=2, conflict_term=2))
    assert node.next_index[2] == 2
    assert outbox[-1][0] == 2  # and it retries immediately


def test_stale_rejection_cannot_move_next_index_forward_or_below_match():
    node, _ = _leader_with_log(log_terms=(3, 3, 3), term=3)
    node.match_index[2] = 2
    node.next_index[2] = 3
    node.receive(2, AppendEntriesReply(term=3, success=False, conflict_index=1))
    assert node.next_index[2] == 3  # clamped to match_index + 1, i.e. unchanged


def test_newly_elected_leader_appends_noop_in_its_own_term():
    node, _ = make_node(1, term=2, log_terms=(1, 2))
    node._start_election()
    node.receive(2, RequestVoteReply(term=3, granted=True))
    assert node.role is Role.LEADER
    last = node.storage.entry(node.storage.last_index)
    assert (last.term, last.command) == (3, None)


def test_out_of_order_success_reply_cannot_regress_match_index():
    """Replies can be reordered. An old 'matched up to 1' arriving after
    'matched up to 3' must not make the leader forget the later progress."""
    node, _ = _leader_with_log(log_terms=(3, 3, 3), term=3)
    node.receive(2, AppendEntriesReply(term=3, success=True, match_index=3))
    node.receive(2, AppendEntriesReply(term=3, success=True, match_index=1))
    assert node.match_index[2] == 3
    assert node.next_index[2] == 4


# -- election timer policy --------------------------------------------------

def test_denied_higher_term_vote_request_does_not_reset_election_timer():
    """A candidate that can't win (stale log) must not be able to postpone
    everyone else's election by merely asking for votes."""
    node, _ = make_node(1, term=1, log_terms=(1, 1))
    for _ in range(5):
        node.tick()
    node.receive(2, RequestVote(term=2, last_log_index=0, last_log_term=0))
    assert node.current_term == 2  # adopted the term...
    assert node._ticks_since_heard == 5  # ...but the timer kept running


def test_granted_vote_resets_election_timer():
    node, outbox = make_node(1, term=1)
    for _ in range(5):
        node.tick()
    node.receive(2, RequestVote(term=2, last_log_index=0, last_log_term=0))
    assert outbox[-1][1].granted and node._ticks_since_heard == 0


# -- pre-vote ---------------------------------------------------------------

def _heartbeat(term, leader_commit=0):
    return AppendEntries(term=term, prev_log_index=0, prev_log_term=0,
                         entries=(), leader_commit=leader_commit)


def test_pre_vote_grant_leaves_voter_state_untouched():
    node, outbox = make_node(1, term=1)
    node.receive(2, PreVote(term=2, last_log_index=0, last_log_term=0))
    assert outbox[-1][1] == PreVoteReply(term=1, granted=True, proposed_term=2)
    assert (node.current_term, node.storage.voted_for, node.role) == (1, None, Role.FOLLOWER)


def test_pre_vote_denied_while_a_leader_is_alive():
    node, outbox = make_node(1, term=1)
    node.receive(3, _heartbeat(term=1))  # we have a leader
    node.receive(2, PreVote(term=2, last_log_index=0, last_log_term=0))
    assert outbox[-1][1].granted is False


def test_pre_vote_granted_again_once_the_leader_goes_quiet():
    node, outbox = make_node(1, term=1)
    node.receive(3, _heartbeat(term=1))
    node._ticks_since_heard = 15  # the shortest possible election timeout
    node.receive(2, PreVote(term=2, last_log_index=0, last_log_term=0))
    assert outbox[-1][1].granted is True


def test_pre_vote_denied_for_stale_log_or_non_advancing_term():
    node, outbox = make_node(1, term=3, log_terms=(1, 3))
    node.receive(2, PreVote(term=4, last_log_index=9, last_log_term=2))
    assert outbox[-1][1].granted is False
    node.receive(2, PreVote(term=3, last_log_index=2, last_log_term=3))
    assert outbox[-1][1].granted is False


def test_leader_never_grants_pre_vote():
    node, outbox = _leader_with_log(log_terms=(3,), term=3)
    node.receive(2, PreVote(term=4, last_log_index=1, last_log_term=3))
    assert outbox[-1][1].granted is False
    assert node.role is Role.LEADER and node.current_term == 3


def test_pre_candidate_keeps_its_term_until_a_majority_agrees():
    node, outbox = make_node(1, term=2, pre_vote=True)
    while node.role is Role.FOLLOWER:
        node.tick()
    assert node.role is Role.PRE_CANDIDATE and node.current_term == 2
    assert {type(m) for _, m in outbox} == {PreVote}

    outbox.clear()
    node.receive(2, PreVoteReply(term=2, granted=False, proposed_term=3))
    assert node.role is Role.PRE_CANDIDATE  # a refusal doesn't count

    node.receive(3, PreVoteReply(term=2, granted=True, proposed_term=3))
    assert node.role is Role.CANDIDATE and node.current_term == 3
    assert {type(m) for _, m in outbox} == {RequestVote}


def test_late_pre_vote_reply_from_an_earlier_round_is_ignored():
    node, _ = make_node(1, term=2, pre_vote=True)
    while node.role is Role.FOLLOWER:
        node.tick()
    node.receive(2, PreVoteReply(term=2, granted=True, proposed_term=2))  # wrong round
    assert node.role is Role.PRE_CANDIDATE


def test_single_node_cluster_still_elects_itself_with_pre_vote():
    node, _ = make_node(1, peers=(1,), pre_vote=True)
    while node.role is not Role.LEADER:
        node.tick()
    assert node.current_term == 1


# -- applying results to the client layer ----------------------------------

def test_apply_callback_reports_results_and_skips_noops():
    seen = []
    node, _ = make_node(
        2, term=1, on_apply=lambda i, e, r: seen.append((i, r))
    )
    node.receive(1, AppendEntries(
        term=1, prev_log_index=0, prev_log_term=0,
        entries=(LogEntry(1, None), LogEntry(1, Set("k", 7)), LogEntry(1, Get("k"))),
        leader_commit=3,
    ))
    assert seen == [(2, None), (3, 7)]  # the no-op at index 1 is invisible


def test_success_reply_claims_only_the_prefix_the_leader_verified():
    """Our unverified tail must not be advertised as matching: the leader
    counts match_index toward commitment."""
    node, outbox = make_node(2, term=2, log_terms=(1, 1, 2, 2))
    node.receive(1, AppendEntries(
        term=2, prev_log_index=1, prev_log_term=1, entries=(), leader_commit=0,
    ))
    assert outbox[-1][1] == AppendEntriesReply(2, True, match_index=1)
