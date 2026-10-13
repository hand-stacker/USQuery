"""_create_or_update_vote: turning House (clerk XML) and Senate (LIS XML)
roll-call payloads into Vote rows with member sets. Idempotency matters: the
pipeline re-processes the same roll calls on every run."""

import datetime
from zoneinfo import ZoneInfo

import pytest
from asgiref.sync import sync_to_async

from app.utils import _create_or_update_vote
from BillQuery.models import Vote
from tests.factories import make_bill, make_congress, make_member, make_membership, vote_id

pytestmark = [pytest.mark.slow, pytest.mark.django_db(transaction=True)]

UTC = datetime.timezone.utc
EASTERN = ZoneInfo('America/New_York')


def house_payload(time='14:15', votes=(('A000001', 'Yea'), ('B000002', 'No'), ('C000003', 'Not Voting'))):
    return {'rollcall-vote': {
        'vote-metadata': {'action-date': '23-Jul-2026', 'action-time': {'@time-etz': time},
                          'vote-question': 'On Passage', 'vote-desc': 'Clean Water Act', 'vote-result': 'Passed'},
        'vote-data': {'recorded-vote': [{'legislator': {'@name-id': mid}, 'vote': v} for mid, v in votes]},
    }}


def senate_payload(votes=(('Smith', 'CA', 'Yea'), ('Jones', 'TX', 'Nay'), ('Brown', 'OH', 'Present'))):
    return {'roll_call_vote': {
        'vote_date': 'July 23, 2026,  02:15 PM', 'question': 'On Passage of the Bill',
        'vote_title': 'A bill to protect water', 'vote_result': 'Bill Passed',
        'members': {'member': [{'last_name': ln, 'state': st, 'vote_cast': v} for ln, st, v in votes]},
    }}


@pytest.fixture
def world():
    congress = make_congress(119)
    house = {mid: make_membership(congress=congress, member=make_member(mid), house=True)
             for mid in ('A000001', 'B000002', 'C000003')}
    senate = {ln: make_membership(congress=congress, member=make_member(last=ln), house=False, state=st)
              for ln, st in (('Smith', 'CA'), ('Jones', 'TX'), ('Brown', 'OH'))}
    make_membership(congress=congress, member=make_member(last='Smith'), house=False, state='NV')
    return {'congress': congress, 'bill': make_bill(119, 4, 1), 'house': house, 'senate': senate}


async def _members(vote, field):
    return set(await sync_to_async(list)(getattr(vote, field).values_list('id', flat=True)))


async def _create(world, payload, in_house, vid, ignore_exists=True, exists=False):
    return await _create_or_update_vote(
        vid, world['congress'], in_house, world['bill'], payload, ignore_exists, exists,
        Vote.objects.filter(id=vid))


class TestHouse:
    async def test_creates_vote_and_member_sets(self, world):
        vid = vote_id(119, True, 2, 245)
        vote, created = await _create(world, house_payload(), 1, vid)
        assert created
        assert (vote.question, vote.title, vote.result, vote.house) == ('On Passage', 'Clean Water Act', 'Passed', True)
        assert await _members(vote, 'yeas') == {world['house']['A000001'].id}
        assert await _members(vote, 'nays') == {world['house']['B000002'].id}
        assert await _members(vote, 'novt') == {world['house']['C000003'].id}
        assert vote.bill_id == world['bill'].id

    async def test_reprocessing_is_idempotent(self, world):
        vid = vote_id(119, True, 2, 245)
        await _create(world, house_payload(), 1, vid)
        flipped = house_payload(votes=(('A000001', 'No'), ('B000002', 'No'), ('C000003', 'Aye')))
        vote, created = await _create(world, flipped, 1, vid, ignore_exists=False, exists=True)
        assert not created
        assert await Vote.objects.acount() == 1
        assert await _members(vote, 'yeas') == {world['house']['C000003'].id}
        assert len(await _members(vote, 'nays')) == 2

    async def test_ignore_exists_leaves_members(self, world):
        vid = vote_id(119, True, 2, 245)
        await _create(world, house_payload(), 1, vid)
        vote, _ = await _create(world, house_payload(votes=()), 1, vid, ignore_exists=True, exists=True)
        assert len(await _members(vote, 'yeas')) == 1

    async def test_eastern_time_stored_correctly(self, world):
        vid = vote_id(119, True, 2, 246)
        vote, _ = await _create(world, house_payload(time='21:30'), 1, vid)
        await vote.arefresh_from_db()
        assert vote.dateTime == datetime.datetime(2026, 7, 23, 21, 30, tzinfo=EASTERN)
        assert vote.dateTime == datetime.datetime(2026, 7, 24, 1, 30, tzinfo=UTC)
        assert vote.getDate() == '2026-07-23'


class TestSenate:
    async def test_matches_by_last_name_and_state(self, world):
        vid = vote_id(119, False, 2, 300)
        vote, created = await _create(world, senate_payload(), 0, vid)
        assert created and vote.house is False
        assert await _members(vote, 'yeas') == {world['senate']['Smith'].id}  # not the NV Smith
        assert await _members(vote, 'nays') == {world['senate']['Jones'].id}
        assert await _members(vote, 'pres') == {world['senate']['Brown'].id}
        await vote.arefresh_from_db()
        assert vote.dateTime == datetime.datetime(2026, 7, 23, 14, 15, tzinfo=EASTERN)

    async def test_no_votes_in_a_category(self, world):
        vid = vote_id(119, False, 2, 301)
        vote, _ = await _create(world, senate_payload(votes=(('Smith', 'CA', 'Yea'),)), 0, vid)
        assert await _members(vote, 'nays') == set()
