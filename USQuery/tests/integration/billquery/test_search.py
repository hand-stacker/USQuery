"""Bill / vote search: date-range search, keyword search (real Postgres FTS +
pg_trgm via the migration-0033 trigger), bill-reference pinning, pagination."""

import datetime

import pytest
from django.core.paginator import Page
from django.test import RequestFactory
from django.utils import timezone
from freezegun import freeze_time

from BillQuery import views as BQviews
from BillQuery.models import Subject
from tests.factories import bill_id, make_bill, make_congress, make_membership, make_vote

pytestmark = pytest.mark.django_db

JAN = datetime.date(2026, 1, 15)
WINDOW = {'start_date': '2026-01-01', 'end_date': '2026-01-31'}


def _bill_ids(resp):
    return [b['bill_id'] for b in resp.context['bills_json']]


def _vote_ids(resp):
    return [v['vote_id'] for v in resp.context['votes_json']]


def _failed(resp):
    return 'BillQuery/search_failed.html' in [t.name for t in resp.templates]


@pytest.fixture
def corpus():
    make_congress(118, start_year=2023, end_year=2025)
    make_congress(119, start_year=2025)
    sponsor = make_membership(congress=make_congress(119))
    water = Subject.objects.create(name='Water quality')
    veterans = Subject.objects.create(name='Veterans medical care')
    b = {
        'water_hr': make_bill(119, 4, 101, sponsor=sponsor, title='Clean Water Infrastructure Act',
                              latest_action=datetime.date(2026, 1, 20)),
        'water_s': make_bill(119, 0, 102, sponsor=sponsor, title='Water Rights Protection Act',
                             latest_action=datetime.date(2026, 1, 10)),
        'vets': make_bill(119, 0, 202, sponsor=sponsor, title='Veterans Health Care Expansion Act',
                          latest_action=JAN),
        'ref': make_bill(119, 4, 303, sponsor=sponsor, title='A bill to rename a post office',
                         latest_action=JAN),
        'old': make_bill(119, 4, 404, sponsor=sponsor, title='Water Old Act',
                         latest_action=datetime.date(2025, 3, 1)),
    }
    b['water_hr'].subjects.add(water)
    b['vets'].subjects.add(veterans)
    b['subjects'] = {'water': water, 'veterans': veterans}
    return b


class TestBillRangeSearch:
    def test_window_and_ordering(self, client, corpus):
        resp = client.get('/bill/search/', {**WINDOW, 'bill_type': '!'})
        ids = _bill_ids(resp)
        assert corpus['old'].id not in ids
        assert ids[0] == corpus['water_hr'].id  # newest latest_action first
        assert set(ids) == {corpus[k].id for k in ('water_hr', 'water_s', 'vets', 'ref')}

    def test_type_filter(self, client, corpus):
        ids = _bill_ids(client.get('/bill/search/', {**WINDOW, 'bill_type': 'hr'}))
        assert set(ids) == {corpus['water_hr'].id, corpus['ref'].id}

    def test_chamber_filter(self, client, corpus):
        ids = _bill_ids(client.get('/bill/search/', {**WINDOW, 'bill_type': '!S'}))
        assert set(ids) == {corpus['water_s'].id, corpus['vets'].id}

    def test_subject_filter(self, client, corpus):
        water = corpus['subjects']['water']
        resp = client.get('/bill/search/', {**WINDOW, 'bill_type': '!', 'bill_subjects': str(water.id)})
        assert _bill_ids(resp) == [corpus['water_hr'].id]
        assert resp.context['bills_json'][0]['subjects'] == [{'id': water.id, 'name': 'Water quality'}]
        assert f'bill_subjects={water.id}&' in resp.context['url_params']

    def test_dates_out_of_order(self, client, corpus):
        resp = client.get('/bill/search/', {'start_date': '2026-02-01', 'end_date': '2026-01-01', 'bill_type': '!'})
        assert _failed(resp)
        assert 'End date' in resp.context['error_message']

    @pytest.mark.parametrize('params', [
        {'start_date': '2026-13-45', 'end_date': '2026-12-31', 'bill_type': '!'},
        {'bill_type': '!'},
        {**WINDOW, 'bill_type': 'nonsense'},
    ])
    def test_malformed_params_fail_gracefully(self, client, corpus, params):
        assert _failed(client.get('/bill/search/', params))

    @pytest.mark.parametrize('url, param', [('/bill/search/', 'bill_subjects'), ('/vote/search/', 'vote_subjects')])
    @pytest.mark.parametrize('value', ['abc', '1,abc', '1,', '-1', '1.5', '1;2'])
    def test_non_numeric_subjects_rejected(self, client, corpus, url, param, value):
        assert client.get(url, {**WINDOW, 'bill_type': '!', param: value}).status_code == 400

    def test_multiple_numeric_subjects(self, client, corpus):
        ids = ','.join(str(s.id) for s in corpus['subjects'].values())
        resp = client.get('/bill/search/', {**WINDOW, 'bill_type': '!', 'bill_subjects': ids})
        assert set(_bill_ids(resp)) == {corpus['water_hr'].id, corpus['vets'].id}


class TestPagination:
    @pytest.fixture
    def many(self):
        sponsor = make_membership(congress=make_congress(119))
        return [make_bill(119, 4, n, sponsor=sponsor, latest_action=JAN) for n in range(1, 61)]

    def test_fifty_per_page(self, client, many):
        page1 = client.get('/bill/search/', {**WINDOW, 'bill_type': '!'})
        page2 = client.get('/bill/search/', {**WINDOW, 'bill_type': '!', 'page': 2})
        assert len(_bill_ids(page1)) == 50
        assert len(_bill_ids(page2)) == 10
        assert not set(_bill_ids(page1)) & set(_bill_ids(page2))

    @pytest.mark.parametrize('page', ['abc', '0', '999'])
    def test_bad_page_falls_back_to_first(self, client, many, page):
        resp = client.get('/bill/search/', {**WINDOW, 'bill_type': '!', 'page': page})
        assert resp.context['page_obj'].number == 1




class TestVoteSearch:
    @pytest.fixture
    def votes(self, corpus):
        when = timezone.make_aware(datetime.datetime(2026, 1, 15, 12))
        return {
            'water_house': make_vote(corpus['water_hr'], house=True, num=1, when=when),
            'water_senate': make_vote(corpus['water_s'], house=False, num=2, when=when),
            'vets_senate': make_vote(corpus['vets'], house=False, num=3, when=when),
            'nomination': make_vote(None, house=False, num=4, when=when, question='On the Nomination',
                                    title='Confirmation of a Water Commissioner'),
        }

    def test_range_search(self, client, votes):
        ids = _vote_ids(client.get('/vote/search/', {**WINDOW, 'bill_type': '!'}))
        assert set(ids) == {v.id for v in votes.values()}

    def test_chamber_filter(self, client, votes):
        ids = _vote_ids(client.get('/vote/search/', {**WINDOW, 'bill_type': 'h'}))
        assert ids == [votes['water_house'].id]

    def test_billless_vote_serialized(self, client, votes):
        rows = client.get('/vote/search/', {**WINDOW, 'bill_type': '!'}).context['votes_json']
        nom = next(r for r in rows if r['vote_id'] == votes['nomination'].id)
        assert (nom['bill_id'], nom['bill_title']) == (None, 'Unknown Bill')




    def test_dates_out_of_order(self, client, votes):
        assert _failed(client.get('/vote/search/', {'start_date': '2026-02-01', 'end_date': '2026-01-01', 'bill_type': '!'}))


class TestHelpers:
    @pytest.mark.parametrize('s_d, e_d, expected', [
        ('2026-01-02', '2026-01-01', True),
        ('2026-01-01', '2026-01-01', False),
        ('2026-01-01', None, False),
        (None, None, False),
    ])
    def test_dates_out_of_order(self, s_d, e_d, expected):
        assert BQviews._dates_out_of_order(s_d, e_d) is expected

    def test_as_iso(self):
        assert BQviews._as_iso(datetime.date(2026, 3, 4)) == '2026-03-04'
        assert BQviews._as_iso(None) is None

    @pytest.mark.parametrize('today, expected', [
        ('2026-10-11', ('2025-01-03', '2027-01-03')),
        ('2025-01-01', ('2025-01-03', '2027-01-03')),
        ('2027-02-01', ('2027-01-03', '2029-01-03')),
    ])
    def test_resolve_date_window(self, today, expected):
        with freeze_time(today):
            assert BQviews._resolve_date_window(None, None) == expected

    def test_resolve_date_window_keeps_given_dates(self):
        with freeze_time('2026-10-11'):
            assert BQviews._resolve_date_window('2026-01-01', None) == ('2026-01-01', '2027-01-03')
            assert BQviews._resolve_date_window('2020-01-01', '2020-02-01') == ('2020-01-01', '2020-02-01')

    def test_congress_nums_in_range(self):
        make_congress(117, start_year=2021, end_year=2023)
        make_congress(118, start_year=2023, end_year=2025)
        make_congress(119, start_year=2025)
        assert BQviews._congress_nums_in_range('2025-06-01', '2026-01-01') == [119, 118]
        assert BQviews._congress_nums_in_range('2021-06-01', '2021-07-01') == [117]

    def test_paginate_ranked_ids(self):
        req = RequestFactory().get('/', {'page': 2})
        page, ids = BQviews._paginate_ranked_ids(req, list(range(120)), 50)
        assert isinstance(page, Page) and ids == list(range(50, 100))
        _, ids = BQviews._paginate_ranked_ids(RequestFactory().get('/', {'page': 'x'}), list(range(5)), 50)
        assert ids == list(range(5))
