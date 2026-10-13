"""SenateQuery model display helpers, on unsaved instances (no DB)."""

import pytest

from SenateQuery.models import Congress, Member, Membership


def _member():
    return Member(id='S000001', full_name='Jane Smith', first_name='Jane', last_name='Smith')


class TestCongress:
    def test_open_range(self):
        assert Congress(congress_num=119, start_year=2025).getRange() == '(2025-Present)'

    def test_closed_range(self):
        c = Congress(congress_num=118, start_year=2023, end_year=2025)
        assert c.getRange() == '(2023-2025)'
        assert str(c) == '118 (2023-2025)'


class TestMembership:
    def test_house_str(self):
        m = Membership(member=_member(), house=True, state='CA', district_num=12, party='Democratic')
        assert m.getStr() == 'Jane Smith [D] (CA-12)'
        assert m.getChamber() == 'House of Representatives'

    def test_senate_str_omits_district(self):
        m = Membership(member=_member(), house=False, state='TX', party='Republican')
        assert m.getStr() == 'Jane Smith [R] (TX)'
        assert m.getChamber() == 'Senate'

    def test_empty_party_raises(self):
        # Current behavior: party[0] on '' raises. Pinned so a fix is noticed.
        m = Membership(member=_member(), house=False, state='TX', party='')
        with pytest.raises(IndexError):
            m.getStr()


def test_member_api_url():
    assert _member().getAPIURL() == 'https://api.congress.gov/v3/member/S000001'
