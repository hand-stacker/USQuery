"""Bill detail, vote detail, member vote table, on-demand summaries.

utils.billHtml (Congress.gov fan-out) and utils.getSummaryAI (Claude) are
patched; everything else runs against the test DB.
"""

import datetime
from unittest import mock

import pytest
from freezegun import freeze_time

from app import siteutils, utils
from app.models import UserProfile
from BillQuery.models import BillPrediction
from notifications.models import StarredBill
from tests.factories import make_bill, make_congress, make_member, make_membership, make_user, make_vote

pytestmark = pytest.mark.django_db

BASE_CONTEXT = {'title': 'CONGRESS: 119, HR-1', 'summary': '', 'AI_generated_content': 'NONE',
                'show_generate_button': True}


@pytest.fixture(autouse=True)
def frozen_today():
    with freeze_time('2026-06-01'):
        yield


@pytest.fixture
def bill_html():
    with mock.patch.object(utils, 'billHtml', mock.AsyncMock(side_effect=lambda *a: dict(BASE_CONTEXT))) as m:
        yield m


@pytest.fixture
def bill():
    return make_bill(119, 4, 1)


def _ctx(client, url='/bill/119/hr/1'):
    resp = client.get(url)
    assert resp.status_code == 200
    return resp.context


class TestBillDetail:
    def test_unknown_bill(self, client, bill_html):
        resp = client.get('/bill/119/hr/999')
        assert 'BillQuery/search_failed.html' in [t.name for t in resp.templates]
        bill_html.assert_not_awaited()

    def test_upstream_unavailable_is_503(self, client, bill):
        with mock.patch.object(utils, 'billHtml', mock.AsyncMock(side_effect=utils.BillUpstreamUnavailable('down'))):
            assert client.get('/bill/119/hr/1').status_code == 503

    def test_guest(self, client, bill, bill_html):
        ctx = _ctx(client)
        assert (ctx['loggedIn'], ctx['chat_enabled'], ctx['isStarred']) == (False, False, False)
        assert (ctx['show_generate_button'], ctx['show_login_for_summary']) == (False, True)
        assert (ctx['vp_user_tier'], ctx['vp_pred_state']) == ('guest', 'empty')
        assert ctx['bill_id'] == bill.id

    def test_free(self, client, bill, bill_html, free_user):
        client.force_login(free_user)
        ctx = _ctx(client)
        assert (ctx['loggedIn'], ctx['chat_enabled'], ctx['vp_user_tier']) == (True, False, 'free')
        assert ctx['show_generate_button'] is True

    def test_plus_starred(self, client, bill, bill_html, plus_user):
        StarredBill.objects.create(user_profile=plus_user.userprofile, bill_id=str(bill.id))
        client.force_login(plus_user)
        ctx = _ctx(client)
        assert (ctx['chat_enabled'], ctx['isStarred'], ctx['vp_user_tier'], ctx['vp_pred_credits']) == (True, True, 'plus', 10)
        assert ctx['vp_pred_credit_limit'] == 10

    def test_plus_pro_uses_metered_ui_with_its_own_limit(self, client, bill, bill_html, plus_pro_user):
        client.force_login(plus_pro_user)
        ctx = _ctx(client)
        assert (ctx['vp_user_tier'], ctx['vp_pred_credits'], ctx['vp_pred_credit_limit']) == ('plus', 30, 30)

    def test_premium_has_no_credit_limit(self, client, bill, bill_html, premium_user):
        client.force_login(premium_user)
        ctx = _ctx(client)
        assert (ctx['vp_user_tier'], ctx['vp_pred_credits'], ctx['vp_pred_credit_limit']) == ('premium', None, None)

    def test_premium_with_prediction(self, client, bill, bill_html, premium_user):
        BillPrediction.objects.create(id=bill.id, creation_date=datetime.date(2026, 6, 1))
        client.force_login(premium_user)
        with mock.patch.object(siteutils, 'getPredictionBatch', side_effect=lambda bid, house, n: [1, 2, 2]):
            ctx = _ctx(client)
        assert (ctx['vp_pred_state'], ctx['vp_member_unlocked']) == ('ready', True)
        assert ctx['vp_house_dist'] == {'1': 1, '2': 2}
        assert ctx['vp_bill_display'] == 'H.R. 1 · 119th'

    def test_prediction_error_state(self, client, bill, bill_html):
        BillPrediction.objects.create(id=bill.id, creation_date=datetime.date(2026, 6, 1))
        with mock.patch.object(siteutils, 'getPredictionBatch',
                               side_effect=siteutils.PredictionDataError('x', 'y')):
            assert _ctx(client)['vp_pred_state'] == 'error'

    def test_previous_congress_not_eligible(self, client, bill_html):
        make_bill(118, 4, 1)
        ctx = _ctx(client, '/bill/118/hr/1')
        assert ctx['eligible_for_prediction'] is False
        assert 'vp_user_tier' not in ctx

    def test_enacted_not_eligible(self, client, bill_html):
        make_bill(119, 4, 2, status=True)
        assert _ctx(client, '/bill/119/hr/2')['eligible_for_prediction'] is False

    def test_wide_bill_number(self, client, bill_html):
        wide = make_bill(119, 4, 10001)
        assert _ctx(client, '/bill/119/hr/10001')['bill_id'] == wide.id

    def test_logged_in_user_without_profile(self, client, bill, bill_html):
        # Accounts created before registration made profiles still lack one.
        from django.contrib.auth.models import User
        user = User.objects.create_user('np@example.com', 'np@example.com', 'x')
        client.force_login(user)
        assert _ctx(client)['vp_user_tier'] == 'free'
        assert UserProfile.objects.filter(user=user, user_type=0).exists()


class TestRequestPrediction:
    @pytest.fixture
    def staff(self, client):
        user = make_user()
        user.is_staff = True
        user.save()
        client.force_login(user)
        return client

    def test_staff_only(self, client, free_user):
        make_bill(119, 4, 1)
        client.force_login(free_user)
        with mock.patch.object(siteutils, 'getPredictionBatch') as batch:
            resp = client.get('/bill/prediction-request/119/hr/1')
        assert resp.status_code == 302 and '/admin/login/' in resp['Location']
        batch.assert_not_called()

    def test_past_congress_forbidden(self, staff):
        make_bill(118, 4, 1)
        with mock.patch.object(siteutils, 'getPredictionBatch') as batch:
            assert staff.get('/bill/prediction-request/118/hr/1').status_code == 403
        batch.assert_not_called()

    def test_passed_bill_forbidden(self, staff):
        make_bill(119, 4, 1, status=True)
        with mock.patch.object(siteutils, 'getPredictionBatch') as batch:
            assert staff.get('/bill/prediction-request/119/hr/1').status_code == 403
        batch.assert_not_called()

    def test_open_current_bill_generates_then_redirects(self, staff):
        make_bill(119, 4, 1)
        with mock.patch.object(siteutils, 'getPredictionBatch', return_value=None) as batch:
            resp = staff.get('/bill/prediction-request/119/hr/1')
        assert resp.status_code == 302 and resp['Location'] == '/bill/119/hr/1'
        batch.assert_called_once()


class TestVoteDetail:
    @pytest.fixture
    def senate_vote(self, bill):
        congress = make_congress(119)
        yea = make_membership(congress=congress, member=make_member(first='Yea'), house=False,
                              state='CA', party='Democratic', geoid='06')
        nay = make_membership(congress=congress, member=make_member(first='Nay'), house=False,
                              state='TX', party='Republican', geoid='48')
        vote = make_vote(bill, house=False, num=7)
        vote.yeas.add(yea)
        vote.nays.add(nay)
        return vote

    def test_unknown(self, client):
        assert 'BillQuery/search_failed.html' in [t.name for t in client.get('/vote/1').templates]

    def test_senate_vote(self, client, senate_vote):
        ctx = _ctx(client, f'/vote/{senate_vote.id}')
        assert ctx['bill'] == 'HR 1'
        assert 'Yea Member' not in ctx['nays_list']
        assert '[D] (CA)' in ctx['yeas_list'] and '[R] (TX)' in ctx['nays_list']



class TestMemberVoteTable:
    """Regression for 2b9df7f: a member who switched chambers within one
    Congress has two Memberships, so the table must use the one passed in."""

    def test_uses_given_membership(self, bill):
        congress = make_congress(119)
        member = make_member(first='Switcher')
        house_m = make_membership(congress=congress, member=member, house=True, state='OH')
        senate_m = make_membership(congress=congress, member=member, house=False, state='OH')
        house_vote = make_vote(bill, house=True, num=1)
        senate_vote = make_vote(bill, house=False, num=2)
        house_vote.nays.add(house_m)
        senate_vote.yeas.add(senate_m)

        senate_table = utils.voteTable([house_vote, senate_vote], senate_m)
        house_table = utils.voteTable([house_vote, senate_vote], house_m)
        assert senate_table.count('>Yea<') == 1 and '>Nay<' not in senate_table
        assert house_table.count('>Nay<') == 1 and '>Yea<' not in house_table

    def test_no_membership(self, bill):
        table = utils.voteTable([make_vote(bill, num=3)], None)
        assert '>No Vote<' in table


class TestGenerateSummary:
    URL = '/bill/generate-summary/119/hr/1/'

    def _post(self, client, user, result=None, error=None):
        client.force_login(user)
        with mock.patch.object(utils, 'getSummaryAI', mock.AsyncMock(return_value=result, side_effect=error)):
            return client.post(self.URL)

    def test_anonymous(self, client, bill):
        resp = client.post(self.URL)
        assert resp.status_code == 302 and '/login/' in resp['Location']

    def test_get_not_allowed(self, client, bill, free_user):
        client.force_login(free_user)
        assert client.get(self.URL).status_code == 405

    def test_unknown_bill(self, client, free_user):
        assert self._post(client, free_user, 'x').status_code == 404

    def test_success(self, client, bill, free_user):
        resp = self._post(client, free_user, '<p>Summary</p>')
        assert resp.json() == {'status': 'ok', 'summary': '<p>Summary</p>', 'generated_at': None}

    @pytest.mark.parametrize('result, status', [
        (utils.SUMMARY_TOO_LARGE, 413), (utils.SUMMARY_OVERLOADED, 503), ('', 500), (None, 500),
    ])
    def test_failure_modes(self, client, bill, free_user, result, status):
        assert self._post(client, free_user, result).status_code == status

    def test_exception(self, client, bill, free_user):
        assert self._post(client, free_user, error=RuntimeError('boom')).status_code == 500
