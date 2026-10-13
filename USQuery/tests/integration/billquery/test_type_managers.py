"""Bill.type_objects / Vote.type_objects: id-range arithmetic over the encoded
primary keys."""

import datetime

import pytest
from django.utils import timezone

from BillQuery.models import Bill, Vote
from tests.factories import bill_id, make_bill, make_membership, make_congress, make_vote, vote_id

pytestmark = pytest.mark.django_db

IN_WINDOW = datetime.date(2026, 1, 15)
OUT_OF_WINDOW = datetime.date(2020, 1, 15)
START, END = datetime.date(2025, 1, 1), datetime.date(2026, 12, 31)


@pytest.fixture
def bills():
    """One narrow-id bill per (congress, type) and one wide-id bill per type in 118."""
    created = {}
    for congress in (110, 117, 118, 119):
        sponsor = make_membership(congress=make_congress(congress))
        for code in range(8):
            created[(congress, code, 7)] = make_bill(congress, code, 7, sponsor=sponsor,
                                                     latest_action=IN_WINDOW)
    sponsor = make_membership(congress=make_congress(118))
    for code in range(8):
        created[(118, code, 10007)] = make_bill(118, code, 10007, sponsor=sponsor,
                                                latest_action=IN_WINDOW)
    return created


def _ids(qs):
    return set(qs.values_list('id', flat=True))


def _expected(bills, codes):
    return {b.id for (_, code, _), b in bills.items() if code in codes}


class TestBillTypeManager:
    @pytest.mark.parametrize('type_str, code', [
        ('s', 0), ('sres', 1), ('sjres', 2), ('sconres', 3),
        ('hr', 4), ('hres', 5), ('hjres', 6), ('hconres', 7),
    ])
    def test_single_type(self, bills, type_str, code):
        got = _ids(Bill.type_objects.get_from_type(type_str, START, END))
        assert got == _expected(bills, {code})

    def test_senate_types(self, bills):
        got = _ids(Bill.type_objects.get_from_type('!S', START, END))
        assert got == _expected(bills, {0, 1, 2, 3})

    def test_house_types(self, bills):
        got = _ids(Bill.type_objects.get_from_type('!H', START, END))
        assert got == _expected(bills, {4, 5, 6, 7})

    @pytest.mark.parametrize('wildcard', ['!', ''])
    def test_all_types(self, bills, wildcard):
        assert _ids(Bill.type_objects.get_from_type(wildcard, START, END)) == {b.id for b in bills.values()}

    def test_date_window_applies(self, bills):
        old = make_bill(119, 4, 9, latest_action=OUT_OF_WINDOW)
        assert old.id not in _ids(Bill.type_objects.get_from_type('hr', START, END))
        assert old.id not in _ids(Bill.type_objects.get_from_type('!', START, END))

    @pytest.mark.parametrize('congress', [100, 109, 119, 121, 125])
    @pytest.mark.parametrize('num', [1, 9999, 10000, 10001, 99999])
    def test_every_congress_and_width(self, congress, num):
        # Was hard-coded to congresses 110-120, wide ids only for 118.
        target = make_bill(congress, 4, num, latest_action=IN_WINDOW)
        decoy = make_bill(congress, 5, num, latest_action=IN_WINDOW)  # same number, H.Res.
        assert _ids(Bill.type_objects.get_from_type('hr', START, END)) == {target.id}
        assert _ids(Bill.type_objects.get_from_type('!H', START, END)) == {target.id, decoy.id}
        assert _ids(Bill.type_objects.get_from_type('!S', START, END)) == set()

    def test_composes_with_annotate_and_order(self, bills):
        from django.db.models import Count
        qs = (Bill.type_objects.get_from_type('hr', START, END)
              .annotate(n=Count('subjects')).order_by('-latest_action', '-id'))
        assert set(qs.values_list('id', flat=True)) == _expected(bills, {4})


class TestVoteTypeManager:
    @pytest.fixture
    def votes(self):
        when = timezone.make_aware(datetime.datetime(2026, 1, 15, 12))
        created = {}
        for congress in (110, 118, 119):
            for house in (True, False):
                for session in (1, 2):
                    v = make_vote(congress=congress, house=house, session=session, num=5, when=when)
                    created[v.id] = v
        return created

    def _window(self):
        return (timezone.make_aware(datetime.datetime(2025, 1, 1)),
                timezone.make_aware(datetime.datetime(2026, 12, 31)))

    def test_house(self, votes):
        got = _ids(Vote.type_objects.get_from_type('h', *self._window()))
        assert got == {i for i, v in votes.items() if v.house}
        assert all(Vote(id=i).inHouse() for i in got)

    def test_senate(self, votes):
        got = _ids(Vote.type_objects.get_from_type('s', *self._window()))
        assert got == {i for i, v in votes.items() if not v.house}

    def test_all(self, votes):
        assert _ids(Vote.type_objects.get_from_type('!', *self._window())) == set(votes)

    def test_congresses_outside_old_window(self):
        when = timezone.make_aware(datetime.datetime(2026, 1, 15, 12))
        house = make_vote(congress=125, house=True, session=1, num=5, when=when)
        senate = make_vote(congress=105, house=False, session=2, num=5, when=when)
        assert _ids(Vote.type_objects.get_from_type('h', *self._window())) == {house.id}
        assert _ids(Vote.type_objects.get_from_type('s', *self._window())) == {senate.id}

    def test_vote_id_encoding(self):
        assert vote_id(119, True, 2, 345) == 119_1_2_00345
        assert Vote(id=vote_id(119, True, 1, 1)).inHouse()
        assert not Vote(id=vote_id(119, False, 1, 1)).inHouse()
