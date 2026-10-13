from datetime import datetime, timezone as dt_timezone
from types import SimpleNamespace
from xml.etree import ElementTree as ET

import pytest
from django.test import RequestFactory

from app import utils
from BillQuery.bill_reference import encode_bill_id


def test_etree_to_dict():
    root = ET.fromstring('<a x="1"><b>t</b><b>u</b><c/></a>')
    assert utils.etree_to_dict(root) == {'a': {'b': ['t', 'u'], 'c': None, '@x': '1'}}


def test_etree_to_dict_text_with_attributes():
    root = ET.fromstring('<a x="1">hello</a>')
    assert utils.etree_to_dict(root) == {'a': {'@x': '1', '#text': 'hello'}}


class TestCacheKeys:
    def test_stable_and_short(self):
        key = utils.make_cache_key('https://x/y', {'a': 1})
        assert key == utils.make_cache_key('https://x/y', {'a': 1})
        assert len(key) == 8

    def test_header_order_irrelevant(self):
        assert (utils.make_cache_key('u', {'a': 1, 'b': 2})
                == utils.make_cache_key('u', {'b': 2, 'a': 1}))

    def test_url_and_headers_change_key(self):
        base = utils.make_cache_key('u', {'a': 1})
        assert utils.make_cache_key('v', {'a': 1}) != base
        assert utils.make_cache_key('u', {'a': 2}) != base

    async def test_async_key(self):
        key = await utils.make_cache_keyASYNC('u', '?a=1')
        assert key == await utils.make_cache_keyASYNC('u', '?a=1')
        assert key != await utils.make_cache_keyASYNC('u', '?a=2')

    def test_cache_version_prefix(self):
        assert utils.API_CACHE_VER == 'v2:'


def test_json_or_error():
    with pytest.raises(RuntimeError, match='failed after retries'):
        utils._json_or_error(None, 'https://x')
    assert utils._json_or_error(SimpleNamespace(json=lambda: {'ok': 1}), 'u') == {'ok': 1}


class TestNames:
    @pytest.mark.parametrize('name, expected', [
        ('Smith, John', ['John', 'Smith']),
        ('Smith,John', ['John', 'Smith']),
        ('Smith,   John A.', ['John', 'Smith']),
        ('Ocasio-Cortez, Alexandria', ['Alexandria', 'Ocasio-Cortez']),
    ])
    def test_first_and_last(self, name, expected):
        assert utils.getFirstAndLastName(name) == expected

    def test_no_comma_returns_exception_class(self):
        # Current behavior: returns (not raises) the ValueError class.
        assert utils.getFirstAndLastName('Cher') is ValueError


@pytest.mark.parametrize('num, suffix', [
    (1, 'st'), (2, 'nd'), (3, 'rd'), (4, 'th'), (11, 'th'), (12, 'th'), (13, 'th'),
    (21, 'st'), (22, 'nd'), (23, 'rd'), (101, 'st'), (111, 'th'), (112, 'th'), (119, 'th'),
])
def test_num_suffix(num, suffix):
    assert utils.getNumSuffix(num) == suffix


class TestVoteDatetime:
    """Clerk/LIS times are Eastern wall clock; stored values must be real UTC."""

    @staticmethod
    def house(date, time):
        return {'rollcall-vote': {'vote-metadata': {'action-date': date, 'action-time': {'@time-etz': time}}}}

    @staticmethod
    def senate(raw):
        return {'roll_call_vote': {'vote_date': raw}}

    @pytest.mark.parametrize('date, time, expected', [
        ('23-Jul-2026', '14:15', datetime(2026, 7, 23, 18, 15)),   # EDT, UTC-4
        ('15-Jan-2026', '14:15', datetime(2026, 1, 15, 19, 15)),   # EST, UTC-5
        ('23-Jul-2026', '21:30', datetime(2026, 7, 24, 1, 30)),    # evening vote crosses UTC midnight
        ('3-Mar-2026', '09:05', datetime(2026, 3, 3, 14, 5)),
    ])
    def test_house(self, date, time, expected):
        assert utils._vote_datetime(self.house(date, time), True) == expected.replace(tzinfo=dt_timezone.utc)

    @pytest.mark.parametrize('raw, expected', [
        ('July 23, 2026,  02:15 PM', datetime(2026, 7, 23, 18, 15)),
        ('January 5, 2026,  12:15 AM', datetime(2026, 1, 5, 5, 15)),
        ('January 5, 2026, 12:30 PM', datetime(2026, 1, 5, 17, 30)),
        ('September 30, 2026,  11:59 PM', datetime(2026, 10, 1, 3, 59)),
    ])
    def test_senate(self, raw, expected):
        assert utils._vote_datetime(self.senate(raw), False) == expected.replace(tzinfo=dt_timezone.utc)

    def test_vote_shows_eastern_date(self):
        from BillQuery.models import Vote
        vote = Vote(dateTime=utils._vote_datetime(self.house('23-Jul-2026', '21:30'), True))
        assert vote.getDate() == '2026-07-23'
        assert vote.localDateTime().hour == 21


def test_find_role_index():
    roles = [
        {'congress': '118', 'chamber': 'House of Representatives'},
        {'congress': '119', 'chamber': 'House of Representatives'},
        {'congress': '119', 'chamber': 'Senate'},
    ]
    assert utils.findIndexOfRoleByChamberAndCongress(roles, 119, 'Senate') == 2
    assert utils.findIndexOfRoleByChamberAndCongress(roles, 119, 'House of Representatives') == 1
    assert utils.findIndexOfRoleByChamberAndCongress(roles, 117, 'Senate') == -1


@pytest.mark.parametrize('num, fips', [(1, '01'), (6, '06'), (10, '10'), (56, '56')])
def test_int_to_fips(num, fips):
    assert utils.intToFIPS(num) == fips


class TestClientIp:
    def test_remote_addr(self):
        req = RequestFactory().get('/', REMOTE_ADDR='10.0.0.5')
        assert utils.get_client_ip(req) == '10.0.0.5'

    def test_forwarded_for_takes_first_hop(self):
        req = RequestFactory().get('/', HTTP_X_FORWARDED_FOR='1.2.3.4,5.6.7.8', REMOTE_ADDR='10.0.0.5')
        assert utils.get_client_ip(req) == '1.2.3.4'


@pytest.mark.parametrize('type_str, code', [
    ('s', 0), ('sres', 1), ('sjres', 2), ('sconres', 3),
    ('hr', 4), ('hres', 5), ('hjres', 6), ('hconres', 7),
])
@pytest.mark.parametrize('num', [1, 9999, 10000, 99999])
def test_make_bill_id_matches_bill_reference_encoding(type_str, code, num):
    assert utils._make_bill_id(119, type_str, num) == encode_bill_id(119, code, num)


@pytest.mark.parametrize('year, session', [(2025, 1), (2026, 2), (2027, 1)])
def test_session_for_year(year, session):
    assert utils._session_for_year(year) == session


@pytest.mark.parametrize('raw, expected', [
    ('23-Jul', '2026-07-23'),
    ('3-Jan', '2026-01-03'),
    (' 1-Dec ', '2026-12-01'),
])
def test_parse_day_mon_date(raw, expected):
    assert utils._parse_day_mon_date(raw, 2026) == expected
